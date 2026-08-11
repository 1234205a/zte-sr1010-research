#!/usr/bin/env python3
"""Predict SR1010 inactive-slot selection and next version counter."""

import argparse, re
from pathlib import Path


def fields(text):
    out={}
    for line in text.splitlines():
        if ":" not in line: continue
        key,value=(part.strip() for part in line.split(":",1))
        match=re.search(r"0x[0-9a-f]+|\b\d+\b",value,re.I)
        if match: out[key]=int(match.group(0),0)
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument("versionstates",type=Path);args=ap.parse_args()
    v=fields(args.versionstates.read_text(encoding="utf-8",errors="replace"))
    required=("currentverphyaddr","curverheader_highstart","curverheader_lowstart","curverheader_lowendstart","curverheader_highendStart","maxversionum")
    missing=[x for x in required if x not in v]
    if missing: raise SystemExit("missing fields: "+", ".join(missing))
    if v["currentverphyaddr"] >= v["curverheader_highstart"]:
        slot="low";start=v["curverheader_lowstart"];end=v["curverheader_lowendstart"];selector=1
    else:
        slot="high";start=v["curverheader_highstart"];end=v["curverheader_highendStart"];selector=2
    print(f"running_image=0x{v['currentverphyaddr']:08x}")
    print(f"target_slot={slot}")
    print(f"target_start=0x{start:08x}")
    print(f"target_end=0x{end:08x}")
    print(f"flashing_selector={selector}")
    print(f"next_version_counter={v['maxversionum']+1}")
    return 0


if __name__=="__main__":raise SystemExit(main())
