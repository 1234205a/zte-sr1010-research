#!/usr/bin/env python3
"""解密并解包 SR1010 Type-4 配置文件。不会在终端打印配置正文。"""
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


def be32(buf, offset):
    return struct.unpack_from(">I", buf, offset)[0]


def derive(model, product="0510", variant="0001"):
    model = "".join(model.split())
    suffix = product.removeprefix("0x") + variant.removeprefix("0x")
    key = hashlib.sha256(f"{model}Key{suffix}".encode()).digest()
    iv = hashlib.sha256(f"{model}Iv{suffix}".encode()).digest()[:16]
    return key, iv


def decrypt_type4(blob, model):
    if len(blob) < 0x58 or be32(blob, 0) != MAGIC or be32(blob, 4) != 4:
        raise ValueError("不是已识别的Type-4外层")
    used = be32(blob, 0x3C)
    encrypted = be32(blob, 0x40)
    if encrypted % 16 or 0x48 + encrypted > len(blob):
        raise ValueError("外层密文长度异常")
    key, iv = derive(model)
    inner = AES.new(key, AES.MODE_CBC, iv).decrypt(blob[0x48:0x48 + encrypted])
    inner = inner[:used]
    if be32(inner, 0) != MAGIC:
        raise ValueError("内层magic不匹配：检查ModelName")

    expected_total = be32(inner, 8)
    pos = 0x40
    expected_block = be32(inner, 0x10)
    chunks = []
    index = 0
    while pos:
        if index == 0:
            compressed, next_pos = struct.unpack_from(">II", inner, pos)
            zoff = pos + 8
        else:
            expected_block, compressed, next_pos = struct.unpack_from(">III", inner, pos)
            zoff = pos + 12
        if zoff + compressed > len(inner):
            raise ValueError(f"块{index}越界")
        chunk = zlib.decompress(inner[zoff:zoff + compressed])
        if len(chunk) != expected_block:
            raise ValueError(f"块{index}长度不匹配")
        chunks.append(chunk)
        if next_pos and next_pos <= pos:
            raise ValueError("块链产生回环")
        pos = next_pos
        index += 1
    plain = b"".join(chunks)
    if len(plain) != expected_total:
        raise ValueError("解包总长度不匹配")
    return plain, index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--model", default="SR1010")
    args = ap.parse_args()
    plain, blocks = decrypt_type4(args.input.read_bytes(), args.model)
    args.output.write_bytes(plain)
    print(f"blocks={blocks} bytes={len(plain)} sha256={hashlib.sha256(plain).hexdigest()}")


if __name__ == "__main__":
    main()
