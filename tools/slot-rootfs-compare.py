#!/usr/bin/env python3
"""Compare plaintext active rootfs with AES-ECB wrapped backup rootfs."""

import argparse, hashlib
from pathlib import Path
from Cryptodome.Cipher import AES


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("flash",type=Path)
    ap.add_argument("--key",required=True,help="16-byte ASCII or 32 hex digits")
    ap.add_argument("--decrypted-output",type=Path)
    args=ap.parse_args(); raw=args.flash.read_bytes()
    current=raw[0x00CE0000:0x02460000]; encrypted=raw[0x035E0000:0x04D60000]
    try: key=bytes.fromhex(args.key) if len(args.key)==32 else args.key.encode("ascii")
    except ValueError: raise SystemExit("invalid key")
    if len(key)!=16: raise SystemExit("key must be 16 bytes")
    backup=AES.new(key,AES.MODE_ECB).decrypt(encrypted)
    if args.decrypted_output: args.decrypted_output.write_bytes(backup)
    print(f"current.sha256={hashlib.sha256(current).hexdigest()}")
    print(f"backup_decrypted.sha256={hashlib.sha256(backup).hexdigest()}")
    print(f"byte_identical={current == backup}")
    print(f"different_bytes={sum(a != b for a,b in zip(current,backup))}")
    return 0 if current==backup else 1


if __name__=="__main__": raise SystemExit(main())
