#!/usr/bin/env python3
"""Offline structural validator for an SR1010 CSP web-upgrade package."""

import argparse
import struct
import zlib
from pathlib import Path

MAGIC = (0x99999999, 0x44444444, 0x55555555, 0xAAAAAAAA)


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("package", type=Path)
    args = ap.parse_args()
    data = args.package.read_bytes()
    errors = []
    if len(data) < 0x108:
        raise SystemExit("package too short")
    if struct.unpack_from("<4I", data, 0) != MAGIC:
        errors.append("CSP magic mismatch")
    skipped = u32(data, 0x10)
    common_at = 0x14 + skipped
    common = data[common_at:common_at + 0xF4]
    if len(common) != 0xF4:
        errors.append("common header outside package")
    else:
        stored = u32(common, 0xA4)
        if stored != (zlib.crc32(common[:0xA4]) & 0xFFFFFFFF):
            errors.append("common header CRC mismatch")
        for label, lo, oo, co in (("kernel", 0x34, 0x38, 0x3C), ("fs", 0x40, 0x44, 0x48)):
            length, offset, expected = u32(common, lo), u32(common, oo), u32(common, co)
            if offset + length > len(data):
                errors.append(f"{label} outside package")
            elif (zlib.crc32(data[offset:offset + length]) & 0xFFFFFFFF) != expected:
                errors.append(f"{label} CRC mismatch")
        boot_offset = common_at + 0xF4
        if boot_offset + 0x180000 > len(data):
            errors.append("boot prefix outside package")
        elif (zlib.crc32(data[boot_offset:boot_offset + 0x180000]) & 0xFFFFFFFF) != u32(common, 0x98):
            errors.append("boot prefix CRC mismatch")
        print(f"sign_size={u32(common, 0)}")
        print(f"key1=0x{u32(common, 8):08x}")
        print(f"key2=0x{u32(common, 12):08x}")
        print("version=" + common[0x10:0x50].split(b"\0", 1)[0].decode("ascii", "replace"))
        print("product=" + common[0x6C:0x9C].split(b"\0", 1)[0].decode("ascii", "replace"))
    print(f"skipped_header_size=0x{skipped:x}")
    print(f"common_header_offset=0x{common_at:x}")
    print("result=" + ("PASS" if not errors else "FAIL"))
    for error in errors:
        print("error=" + error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
