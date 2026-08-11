#!/usr/bin/env python3
"""Extract a little-endian JFFS2 range and optionally recover deleted dirents."""

import argparse, json, shutil, struct, zlib
from pathlib import Path


def rtime(src, length):
    positions = [0] * 256; out = bytearray(); pos = 0
    while pos + 1 < len(src) and len(out) < length:
        value, repeat = src[pos], src[pos + 1]; pos += 2
        back = positions[value]; positions[value] = len(out); out.append(value)
        for _ in range(min(repeat, len(out) - back, length - len(out))):
            out.append(out[back]); back += 1
    return bytes(out)


def assemble(nodes):
    size = max(node[3] for node in nodes); data = bytearray(size)
    for version, offset, chunk, _, _, _, _ in sorted(nodes):
        data[offset:min(size, offset + len(chunk))] = chunk[:max(0, size - offset)]
    return bytes(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path); ap.add_argument("output", type=Path)
    ap.add_argument("--offset", required=True, type=lambda x: int(x, 0))
    ap.add_argument("--length", required=True, type=lambda x: int(x, 0))
    ap.add_argument("--recover-deleted", action="store_true")
    args = ap.parse_args(); image = args.image.read_bytes(); start=args.offset; end=start+args.length
    if end > len(image): raise SystemExit("range outside image")
    dirents={}; inodes={}; stats={}; cursor=start
    while cursor + 68 <= end:
        magic, nodetype, total = struct.unpack_from("<HHI", image, cursor)
        if magic != 0x1985 or total < 12 or total > 0x20000 or cursor + total > end:
            cursor=(cursor+4)&~3; continue
        stats[hex(nodetype)] = stats.get(hex(nodetype), 0) + 1
        if nodetype == 0xE001 and total >= 40:
            parent, version, inode = struct.unpack_from("<III", image, cursor+12)
            nsize=image[cursor+28]; dtype=image[cursor+29]
            name=image[cursor+40:cursor+40+nsize].decode("utf-8","replace")
            if nsize < 255 and "/" not in name:
                dirents.setdefault((parent,name),[]).append((version,inode,dtype,cursor))
        elif nodetype == 0xE002 and total >= 68:
            inode,version=struct.unpack_from("<II",image,cursor+12); mode=struct.unpack_from("<I",image,cursor+20)[0]
            size=struct.unpack_from("<I",image,cursor+28)[0]; offset,csize,dsize=struct.unpack_from("<III",image,cursor+44); comp=image[cursor+56]
            if inode and size<=0x4000000 and offset<=size and csize<=total-68 and dsize<=0x1000000:
                raw=image[cursor+68:cursor+68+csize]
                try: chunk=raw if comp==0 else zlib.decompress(raw) if comp==6 else rtime(raw,dsize) if comp==2 else None
                except Exception: chunk=None
                if chunk is not None: inodes.setdefault(inode,[]).append((version,offset,chunk,size,mode,cursor,comp))
        cursor=(cursor+total+3)&~3
    selected={key:max(entries) for key,entries in dirents.items()}; paths={1:Path(".")}
    for _ in range(100):
        before=len(paths)
        for (parent,name),(_,inode,_,_) in selected.items():
            if inode and parent in paths and inode not in paths: paths[inode]=paths[parent]/name
        if len(paths)==before: break
    shutil.rmtree(args.output,ignore_errors=True); args.output.mkdir(parents=True)
    files=[]
    for inode,relative in paths.items():
        if inode not in inodes: continue
        mode=max(inodes[inode])[4]
        target=args.output/relative
        if mode & 0o170000 == 0o040000:
            target.mkdir(parents=True,exist_ok=True); continue
        try: target.parent.mkdir(parents=True,exist_ok=True)
        except FileExistsError: target=args.output/f"__inode_{inode}_{relative.name}"
        if target.exists() and target.is_dir(): target=args.output/f"__inode_{inode}_data"
        target.write_bytes(assemble(inodes[inode])); files.append({"inode":inode,"path":str(relative),"size":target.stat().st_size})
    deleted=[]
    if args.recover_deleted:
        recovery=args.output/"__recovered_deleted"; recovery.mkdir(exist_ok=True)
        for (parent,name), entries in dirents.items():
            if max(entries)[1] != 0: continue
            prior=[entry for entry in entries if entry[1] != 0]
            if not prior: continue
            version,inode,_,node=max(prior)
            if inode in inodes:
                safe=f"parent{parent}_v{version}_ino{inode}_{name}"; (recovery/safe).write_bytes(assemble(inodes[inode]))
                deleted.append({"name":name,"parent":parent,"inode":inode,"version":version,"node":node})
    manifest={"offset":start,"length":args.length,"stats":stats,"files":files,"recovered_deleted":deleted}
    (args.output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"files={len(files)} recovered_deleted={len(deleted)} nodes={sum(stats.values())}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
