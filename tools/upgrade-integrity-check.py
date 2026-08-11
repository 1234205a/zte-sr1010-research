#!/usr/bin/env python3
"""Reproduce cspd's common upgrade-file integrity decision offline."""

import argparse
import hashlib
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="SR1010 upgrade component preflight")
    ap.add_argument("file", type=Path)
    ap.add_argument("--algorithm", type=int, required=True, choices=(0, 1, 2, 3))
    ap.add_argument("--size", type=int, help="expected byte length from the descriptor")
    ap.add_argument("--checksum", help="expected lowercase/uppercase hexadecimal checksum")
    args = ap.parse_args()

    if args.algorithm <= 1:
        print("result=PASS (cspd algorithm 0/1 does not hash the file)")
        return 0
    actual_size = args.file.stat().st_size
    print(f"size={actual_size}")
    if actual_size == 0:
        print("result=FAIL (empty file)")
        return 1
    if args.size not in (None, 0) and actual_size != args.size:
        print(f"result=FAIL (expected size {args.size})")
        return 1

    h = hashlib.md5() if args.algorithm == 2 else hashlib.sha256()
    with args.file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    digest = h.hexdigest()
    print(f"algorithm={'MD5' if args.algorithm == 2 else 'SHA-256'}")
    print(f"digest={digest}")
    if args.checksum is None:
        print("result=CALCULATED (provide --checksum to compare)")
        return 0
    if digest.lower() == args.checksum.strip().lower():
        print("result=PASS")
        return 0
    print("result=FAIL (checksum mismatch)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
