#!/usr/bin/env python3
"""SR1010 dump/raw consistency and dual-slot comparison."""
import argparse, hashlib
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('dump', type=Path)
p.add_argument('--raw', type=Path)
p.add_argument('--page-size', type=lambda x:int(x,0), default=2048)
p.add_argument('--oob-size', type=lambda x:int(x,0), default=64)
a=p.parse_args(); data=a.dump.read_bytes()
print('dump_size',len(data)); print('dump_sha256',hashlib.sha256(data).hexdigest())
parts={'bootloader':(0,0x100000),'tags':(0x100000,0x100000),'usercfg':(0x200000,0x200000),'defcfg':(0x400000,0x200000),'kernel1':(0x600000,0x2900000),'kernel2':(0x2f00000,0x2900000),'Plugin':(0x5800000,0x2800000)}
for n,(o,s) in parts.items(): print(n,hex(o),hex(s),hashlib.sha256(data[o:o+s]).hexdigest())
a1=data[0x600000:0x2f00000];a2=data[0x2f00000:0x5800000]
diff=[]
for o in range(0,len(a1),0x20000):
 x,y=a1[o:o+0x20000],a2[o:o+0x20000]
 if x!=y: diff.append((hex(o),sum(i!=j for i,j in zip(x,y))))
print('slot_different_eraseblocks',diff)
if a.raw:
 raw=a.raw.read_bytes(); stride=a.page_size+a.oob_size
 stripped=b''.join(raw[i:i+a.page_size] for i in range(0,len(raw),stride))
 ds=[i for i,(x,y) in enumerate(zip(data,stripped)) if x!=y]
 bad=[];ppb=0x20000//a.page_size
 for b in range((len(raw)//stride)//ppb):
  marks=[raw[(b*ppb+p)*stride+a.page_size] for p in (0,1)]
  if any(x!=0xff for x in marks):bad.append((b,marks))
 print('raw_stripped_sha256',hashlib.sha256(stripped).hexdigest())
 print('raw_vs_dump_diff_bytes',len(ds),'diff_pages',len(set(i//a.page_size for i in ds)))
 print('bad_block_markers',bad)
