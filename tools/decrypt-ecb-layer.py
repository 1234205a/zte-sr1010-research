#!/usr/bin/env python3
"""Decrypt an SR1010 AES-128-ECB layer and report common filesystem magics."""
import argparse,re,hashlib
from pathlib import Path
from Cryptodome.Cipher import AES
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--key',required=True,help='16-byte ASCII or 32 hex digits');a=p.parse_args()
k=bytes.fromhex(a.key) if len(a.key)==32 and all(c in '0123456789abcdefABCDEF' for c in a.key) else a.key.encode()
if len(k)!=16:raise SystemExit('key must be 16 bytes')
d=a.input.read_bytes();q=AES.new(k,AES.MODE_ECB).decrypt(d+b'\0'*((-len(d))%16))[:len(d)];a.output.write_bytes(q)
print('sha256',hashlib.sha256(q).hexdigest())
for n,m in {'jffs2':b'\x85\x19','squashfs':b'hsqs','fit':b'\xd0\x0d\xfe\xed','gzip':b'\x1f\x8b','elf':b'\x7fELF'}.items():
 h=[x.start() for x in re.finditer(re.escape(m),q)];print(n,[hex(x) for x in h[:16]],'count',len(h))
