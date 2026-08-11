#!/usr/bin/env python3
"""将XML打包成SR1010 Type-4 AES-256-CBC配置。"""
import argparse
import hashlib
import struct
import zlib
from pathlib import Path

try:
    from Cryptodome.Cipher import AES
except ImportError as exc:
    raise SystemExit("需要 pycryptodomex: python -m pip install pycryptodomex") from exc

MAGIC = 0x01020304
BLOCK = 0x10000


def derive(model, product="0510", variant="0001"):
    model = "".join(model.split())
    suffix = product.removeprefix("0x") + variant.removeprefix("0x")
    key = hashlib.sha256(f"{model}Key{suffix}".encode()).digest()
    iv = hashlib.sha256(f"{model}Iv{suffix}".encode()).digest()[:16]
    return key, iv


def build_inner(plain):
    chunks = [plain[i:i + BLOCK] for i in range(0, len(plain), BLOCK)] or [b""]
    packed = [zlib.compress(chunk, 9) for chunk in chunks]
    positions = []
    pos = 0x3C
    for data in packed:
        positions.append(pos)
        pos += 12 + len(data)

    records = bytearray()
    data_crc = 0
    for i, (chunk, data) in enumerate(zip(chunks, packed)):
        next_pos = positions[i + 1] if i + 1 < len(positions) else 0
        records += struct.pack(">III", len(chunk), len(data), next_pos) + data
        data_crc = zlib.crc32(data, data_crc)

    header = bytearray(0x3C)
    struct.pack_into(">IIIII", header, 0, MAGIC, 0, len(plain), positions[-1], BLOCK)
    struct.pack_into(">I", header, 0x14, data_crc & 0xFFFFFFFF)
    struct.pack_into(">I", header, 0x18, zlib.crc32(header[:0x18]) & 0xFFFFFFFF)
    return bytes(header + records)


def pack_type4(plain, model):
    inner = build_inner(plain)
    # 固件总是补到下一个块，恰好对齐时也增加16个零字节。
    padded = inner + b"\0" * (16 - len(inner) % 16)
    key, iv = derive(model)
    encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(padded)
    outer = bytearray(0x48)
    struct.pack_into(">II", outer, 0, MAGIC, 4)
    struct.pack_into(">II", outer, 0x3C, len(inner), len(encrypted))
    return bytes(outer) + encrypted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--model", default="SR1010")
    args = ap.parse_args()
    blob = pack_type4(args.input.read_bytes(), args.model)
    args.output.write_bytes(blob)
    print(f"bytes={len(blob)} sha256={hashlib.sha256(blob).hexdigest()}")


if __name__ == "__main__":
    main()
