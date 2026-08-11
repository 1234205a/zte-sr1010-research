#!/usr/bin/env python3
"""自动识别并提取 SR1010 全闪存中的双槽头、kernel 与 rootfs。"""
import argparse
import hashlib
import json
import mmap
import re
import struct
import zlib
from pathlib import Path

HEADER_SIZE = 0x510
HEADER_CRC_END = 0x1FC
SIGNATURES = {
    "jffs2_le": b"\x85\x19", "fdt_fit": b"\xd0\x0d\xfe\xed",
    "uimage": b"\x27\x05\x19\x56", "squashfs_le": b"hsqs",
    "gzip": b"\x1f\x8b\x08", "xz": b"\xfd7zXZ\x00", "lzma": b"\x5d\x00\x00",
}


def u32(data, off): return struct.unpack_from("<I", data, off)[0]
def cstr(data, off, size): return data[off:off + size].split(b"\0", 1)[0].decode("ascii", "replace")
def sha(data): return hashlib.sha256(data).hexdigest()


def scan_signatures(data, limit=16):
    found = {}
    for name, magic in SIGNATURES.items():
        positions, start = [], 0
        while len(positions) < limit:
            pos = data.find(magic, start)
            if pos < 0: break
            positions.append(pos); start = pos + 1
        if positions: found[name] = positions
    return found


def find_headers(raw):
    candidates = []
    for match in re.finditer(rb"ZXSLC SR1010\0", raw):
        start = match.start() - 0x6C
        if start < 0 or start + HEADER_SIZE > len(raw): continue
        h = raw[start:start + HEADER_SIZE]
        if u32(h, 8) != 0x510 or u32(h, 0x0C) != 1: continue
        if zlib.crc32(h[:HEADER_CRC_END]) & 0xFFFFFFFF != u32(h, HEADER_CRC_END): continue
        base = u32(h, 0x1F0)
        low_start, low_end, high_start, high_end = (u32(h, x) for x in (0x1E0, 0x1E4, 0x1E8, 0x1EC))
        if base not in (low_start, high_start) or not (0 <= base < len(raw)): continue
        candidates.append((start, h))
    return candidates


def component(raw, start, length):
    if start < 0 or length < 0 or start + length > len(raw): raise ValueError("组件范围越界")
    data = raw[start:start + length]
    return {"offset": start, "length": length, "sha256": sha(data),
            "signatures": scan_signatures(data)}, data


def analyze(raw):
    slots = []
    for header_offset, h in find_headers(raw):
        base = u32(h, 0x1F0)
        kernel_rel = u32(h, 0x38) & ~0xFFFF
        rootfs_rel = u32(h, 0x44) & ~0xFFFF
        kernel, _ = component(raw, base + kernel_rel, u32(h, 0x34))
        rootfs, rootdata = component(raw, base + rootfs_rel, u32(h, 0x40))
        boot = raw[base:base + 0x180000]
        slots.append({
            "header_offset": header_offset, "header_size": HEADER_SIZE,
            "header_crc32": f"{u32(h, HEADER_CRC_END):08x}", "header_crc_valid": True,
            "version": cstr(h, 0x10, 64), "product": cstr(h, 0x6C, 48),
            "build": cstr(h, 0xA8, 32), "slot_base": base,
            "slot_bounds": [u32(h, 0x1E0), u32(h, 0x1E4)] if base == u32(h, 0x1E0) else [u32(h, 0x1E8), u32(h, 0x1EC)],
            "common_crc_valid": (zlib.crc32(h[:0xA4]) & 0xFFFFFFFF) == u32(h, 0xA4),
            "boot_prefix_crc_valid": len(boot) == 0x180000 and (zlib.crc32(boot) & 0xFFFFFFFF) == u32(h, 0x98),
            "kernel": kernel, "rootfs": rootfs,
            "rootfs_plain_jffs2": rootdata.startswith(b"\x85\x19"),
        })
    slots.sort(key=lambda x: x["slot_base"])
    return {"flash_bytes": len(raw), "flash_sha256": sha(raw), "slots": slots,
            "slot_count": len(slots), "valid": len(slots) == 2}


def write_component(raw, info, output):
    output.write_bytes(raw[info["offset"]:info["offset"] + info["length"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flash", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--extract", type=Path)
    a = ap.parse_args()
    with a.flash.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as raw:
        report = analyze(raw)
        if a.extract:
            a.extract.mkdir(parents=True, exist_ok=True)
            for index, slot in enumerate(report["slots"], 1):
                (a.extract / f"slot{index}-header.bin").write_bytes(raw[slot["header_offset"]:slot["header_offset"] + HEADER_SIZE])
                write_component(raw, slot["kernel"], a.extract / f"slot{index}-kernel.bin")
                write_component(raw, slot["rootfs"], a.extract / f"slot{index}-rootfs.bin")
            (a.extract / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if a.json: a.json.write_text(text + "\n", encoding="utf-8")
        else: print(text)
    return 0 if report["valid"] else 2


if __name__ == "__main__": raise SystemExit(main())
