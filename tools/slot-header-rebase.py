#!/usr/bin/env python3
"""Rebase an offline SR1010 0x510-byte slot header and repair its CRC32."""

import argparse
import struct
import zlib
from pathlib import Path

VALID_BASES = (0x00600000, 0x02F00000)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("header", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--slot-base", required=True, type=lambda x: int(x, 0), choices=VALID_BASES)
    args = ap.parse_args()
    data = bytearray(args.header.read_bytes())
    if len(data) != 0x510:
        raise SystemExit("expected exactly 0x510 bytes")
    old_crc = struct.unpack_from("<I", data, 0x1FC)[0]
    if old_crc != (zlib.crc32(data[:0x1FC]) & 0xFFFFFFFF):
        raise SystemExit("input header CRC32 is invalid")
    struct.pack_into("<I", data, 0x1F0, args.slot_base)
    new_crc = zlib.crc32(data[:0x1FC]) & 0xFFFFFFFF
    struct.pack_into("<I", data, 0x1FC, new_crc)
    args.output.write_bytes(data)
    print(f"slot_base=0x{args.slot_base:08x}")
    print(f"header_crc=0x{new_crc:08x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
