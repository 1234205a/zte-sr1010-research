#!/usr/bin/env python3
"""Build a zero-signature SR1010 web-upgrade candidate from a full flash dump."""

import argparse
import hashlib
import struct
import zlib
from pathlib import Path

MAGIC = struct.pack("<4I", 0x99999999, 0x44444444, 0x55555555, 0xAAAAAAAA)
SIGN_BLOCK_SIZE = 0x20C
COMMON_SIZE = 0xF4
PREFIX_SIZE = 0x314


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("flash", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--slot-base", type=lambda x: int(x, 0), default=0x00600000)
    ap.add_argument("--header", type=lambda x: int(x, 0), default=0x02460000)
    args = ap.parse_args()
    flash = args.flash.read_bytes()
    common = bytearray(flash[args.header:args.header + COMMON_SIZE])
    if len(common) != COMMON_SIZE:
        raise SystemExit("common header outside flash image")
    header_rel = args.header - args.slot_base
    slot_payload = flash[args.slot_base:args.header]
    if len(slot_payload) != header_rel:
        raise SystemExit("slot payload outside flash image")

    kernel_file_offset, kernel_length = u32(common, 0x38), u32(common, 0x34)
    fs_file_offset, fs_length = u32(common, 0x44), u32(common, 0x40)
    kernel_rel = kernel_file_offset - PREFIX_SIZE
    fs_rel = fs_file_offset - PREFIX_SIZE
    if kernel_rel < 0 or fs_rel < 0 or fs_rel + fs_length != len(slot_payload):
        raise SystemExit("component layout does not match the selected slot")
    kernel_crc = zlib.crc32(slot_payload[kernel_rel:kernel_rel + kernel_length]) & 0xFFFFFFFF
    fs_crc = zlib.crc32(slot_payload[fs_rel:fs_rel + fs_length]) & 0xFFFFFFFF
    boot_crc = zlib.crc32(slot_payload[:0x180000]) & 0xFFFFFFFF
    struct.pack_into("<I", common, 0x3C, kernel_crc)
    struct.pack_into("<I", common, 0x48, fs_crc)
    struct.pack_into("<I", common, 0x98, boot_crc)
    struct.pack_into("<I", common, 0xA4, zlib.crc32(common[:0xA4]) & 0xFFFFFFFF)

    outer = MAGIC + struct.pack("<I", SIGN_BLOCK_SIZE)
    package = outer + bytes(SIGN_BLOCK_SIZE) + common + slot_payload
    if len(outer) + SIGN_BLOCK_SIZE + COMMON_SIZE != PREFIX_SIZE:
        raise AssertionError("prefix layout mismatch")
    if len(package) != fs_file_offset + fs_length:
        raise AssertionError("final package length mismatch")
    args.output.write_bytes(package)
    print(f"size=0x{len(package):x}")
    print(f"kernel_crc=0x{kernel_crc:08x}")
    print(f"fs_crc=0x{fs_crc:08x}")
    print(f"boot_crc=0x{boot_crc:08x}")
    print(f"sha256={hashlib.sha256(package).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
