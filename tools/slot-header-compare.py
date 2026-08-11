#!/usr/bin/env python3
"""Compare the two SR1010 slot-header records in an offline flash dump."""

import argparse
import struct
import zlib
from pathlib import Path


def cstr(data: bytes, offset: int, limit: int) -> str:
    return data[offset:offset + limit].split(b"\0", 1)[0].decode("ascii", "replace")


def runs(a: bytes, b: bytes):
    start = None
    for pos, pair in enumerate(zip(a, b)):
        if pair[0] != pair[1] and start is None:
            start = pos
        elif pair[0] == pair[1] and start is not None:
            yield start, pos
            start = None
    if start is not None:
        yield start, min(len(a), len(b))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("flash", type=Path)
    ap.add_argument("--current", type=lambda x: int(x, 0), default=0x02460000)
    ap.add_argument("--backup", type=lambda x: int(x, 0), default=0x04D60000)
    ap.add_argument("--length", type=lambda x: int(x, 0), default=0x510)
    args = ap.parse_args()
    with args.flash.open("rb") as stream:
        stream.seek(args.current); current = stream.read(args.length)
        stream.seek(args.backup); backup = stream.read(args.length)
    if len(current) != args.length or len(backup) != args.length:
        raise SystemExit("header range exceeds flash image")

    for name, data in (("current", current), ("backup", backup)):
        print(f"{name}.key1=0x{struct.unpack_from('<I', data, 8)[0]:08x}")
        print(f"{name}.key2=0x{struct.unpack_from('<I', data, 12)[0]:08x}")
        print(f"{name}.version={cstr(data, 0x10, 64)}")
        print(f"{name}.product={cstr(data, 0x6c, 48)}")
        print(f"{name}.build={cstr(data, 0xa8, 32)}")
        print(f"{name}.kernel_length=0x{struct.unpack_from('<I', data, 0x34)[0]:08x}")
        print(f"{name}.kernel_file_offset=0x{struct.unpack_from('<I', data, 0x38)[0]:08x}")
        print(f"{name}.kernel_crc=0x{struct.unpack_from('<I', data, 0x3c)[0]:08x}")
        print(f"{name}.fs_length=0x{struct.unpack_from('<I', data, 0x40)[0]:08x}")
        print(f"{name}.fs_file_offset=0x{struct.unpack_from('<I', data, 0x44)[0]:08x}")
        print(f"{name}.fs_crc=0x{struct.unpack_from('<I', data, 0x48)[0]:08x}")
        common_crc = struct.unpack_from("<I", data, 0xa4)[0]
        print(f"{name}.common_crc=0x{common_crc:08x}")
        print(f"{name}.common_crc_ok={common_crc == (zlib.crc32(data[:0xa4]) & 0xffffffff)}")
        print(f"{name}.low_start=0x{struct.unpack_from('<I', data, 0x1e0)[0]:08x}")
        print(f"{name}.low_end=0x{struct.unpack_from('<I', data, 0x1e4)[0]:08x}")
        print(f"{name}.high_start=0x{struct.unpack_from('<I', data, 0x1e8)[0]:08x}")
        print(f"{name}.high_end=0x{struct.unpack_from('<I', data, 0x1ec)[0]:08x}")
        print(f"{name}.slot_base=0x{struct.unpack_from('<I', data, 0x1f0)[0]:08x}")
        stored_crc = struct.unpack_from("<I", data, 0x1fc)[0]
        calculated_crc = zlib.crc32(data[:0x1fc]) & 0xffffffff
        print(f"{name}.header_crc=0x{stored_crc:08x}")
        print(f"{name}.header_crc_ok={stored_crc == calculated_crc}")
        slot_base = struct.unpack_from("<I", data, 0x1f0)[0]
        with args.flash.open("rb") as stream:
            stream.seek(slot_base)
            boot_prefix = stream.read(0x180000)
        boot_crc = zlib.crc32(boot_prefix) & 0xffffffff
        stored_boot_crc = struct.unpack_from("<I", data, 0x98)[0]
        print(f"{name}.boot_prefix_crc=0x{stored_boot_crc:08x}")
        print(f"{name}.boot_prefix_crc_ok={len(boot_prefix) == 0x180000 and stored_boot_crc == boot_crc}")
    differences = list(runs(current, backup))
    print("different_ranges=" + ",".join(f"0x{s:x}..0x{e:x}" for s, e in differences))
    return 1 if not differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
