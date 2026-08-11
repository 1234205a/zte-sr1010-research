#!/usr/bin/env python3
"""Locate SR1010 slot headers, validate CRC32, and carve encrypted layers."""
import argparse,struct,zlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('dump',type=Path);p.add_argument('-o','--out',type=Path);a=p.parse_args();d=a.dump.read_bytes()
hits=[]
for base in range(0,len(d)-0x510,4):
 if struct.unpack_from('<I',d,base+8)[0]!=0x510:continue
 stored=struct.unpack_from('<I',d,base+0x1fc)[0];calc=zlib.crc32(d[base:base+0x1fc])&0xffffffff
 if stored==calc:hits.append(base)
print('headers',[hex(x) for x in hits])
for h in hits:
 slot=struct.unpack_from('<I',d,h+0x1f0)[0];slot_size=struct.unpack_from('<I',d,h+0x50)[0]
 kernel_off=0x180000;kernel_size=struct.unpack_from('<I',d,h+0x34)[0]
 rootfs_rel=((kernel_off+kernel_size+0x1ffff)//0x20000)*0x20000
 rootfs_size=struct.unpack_from('<I',d,h+0x40)[0]
 print({'header':hex(h),'version':d[h+0x10:h+0x20].split(b'\0')[0].decode(errors='replace'),'slot':hex(slot),'slot_size':hex(slot_size),'kernel':(hex(slot+kernel_off),hex(kernel_size)),'rootfs':(hex(slot+rootfs_rel),hex(rootfs_size)),'header_crc32':hex(struct.unpack_from('<I',d,h+0x1fc)[0])})
 if a.out:
  a.out.mkdir(parents=True,exist_ok=True);tag=f'{slot:08x}'
  (a.out/f'{tag}-header.bin').write_bytes(d[h:h+0x510])
  (a.out/f'{tag}-kernel.enc').write_bytes(d[slot+kernel_off:slot+kernel_off+kernel_size])
  (a.out/f'{tag}-rootfs.enc').write_bytes(d[slot+rootfs_rel:slot+rootfs_rel+rootfs_size])
