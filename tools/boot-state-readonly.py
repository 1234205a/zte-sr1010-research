#!/usr/bin/env python3
"""Read-only SR1010 boot environment and boot-parameter audit."""

import argparse
import hashlib
import struct
import zlib
from pathlib import Path

FLASH_SIZE = 0x8000000
ENV_OFF = 0x80000
ENV_SIZE = 0x20000
TAGS_OFF = 0x100000
TAGS_SIZE = 0x100000
UBOOT_SIZE = 0xE3D10
SLOTS = (0x600000, 0x2F00000)
BOOTPARA_SIZE = 0x578
BOOTPARA_SUM_OFF = 0xC0


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_env(block: bytes):
    stored = struct.unpack_from("<I", block)[0]
    calculated = zlib.crc32(block[4:]) & 0xFFFFFFFF
    variables = {}
    for item in block[4:].split(b"\0\0", 1)[0].split(b"\0"):
        if b"=" in item:
            key, value = item.split(b"=", 1)
            variables[key.decode("ascii", "replace")] = value.decode("ascii", "replace")
    return stored, calculated, variables


def scan_bootpara_aligned(data: bytes):
    hits = []
    for off in range(0, len(data) - BOOTPARA_SIZE + 1, 0x200):
        chunk = data[off : off + BOOTPARA_SIZE]
        stored = struct.unpack_from("<I", chunk, BOOTPARA_SUM_OFF)[0]
        if stored in (0, 0xFFFFFFFF):
            continue
        calculated = sum(chunk[:BOOTPARA_SUM_OFF]) + sum(chunk[BOOTPARA_SUM_OFF + 4 :])
        if stored == calculated:
            hits.append(off)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flash", type=Path)
    args = ap.parse_args()
    data = args.flash.read_bytes()
    if len(data) != FLASH_SIZE:
        raise SystemExit(f"unexpected flash size: {len(data):#x}")

    stored, calculated, env = parse_env(data[ENV_OFF : ENV_OFF + ENV_SIZE])
    print(f"flash_sha256={sha256(data)}")
    print(f"env_crc_stored={stored:08x}")
    print(f"env_crc_calculated={calculated:08x}")
    print(f"env_crc_ok={stored == calculated}")
    print("env_names=" + ",".join(sorted(env)))
    for key in ("bootdelay", "stdin", "stdout", "stderr", "ipaddr", "serverip", "memsize"):
        if key in env:
            print(f"env_{key}={env[key]}")

    tags = data[TAGS_OFF : TAGS_OFF + TAGS_SIZE]
    print(f"tags_sha256={sha256(tags)}")
    print(f"tags_magic={tags[:4].hex()}")
    print(f"tags_declared_length={struct.unpack_from('<I', tags, 4)[0]:#x}")

    slot_hashes = []
    for index, off in enumerate(SLOTS, 1):
        digest = sha256(data[off : off + UBOOT_SIZE])
        slot_hashes.append(digest)
        print(f"slot{index}_uboot_sha256={digest}")
    print(f"slot_uboot_equal={slot_hashes[0] == slot_hashes[1]}")

    hits = scan_bootpara_aligned(data)
    print("bootpara_aligned_candidates=" + (",".join(hex(x) for x in hits) or "none"))


if __name__ == "__main__":
    main()
