#!/usr/bin/env python3
"""Decrypt ZTE enhardcodefile/enwebdhardcodefile and optionally emit a redacted inventory."""

import argparse
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def derive_key(model: str) -> bytes:
    material = f"{model.strip()}0x05100x0001".encode("ascii")
    if len(material) > 32:
        raise ValueError("derived hardcode key material exceeds 32 bytes")
    return material.ljust(32, b"\0")


def decrypt(data: bytes, key: bytes) -> bytes:
    if len(data) % 16:
        raise ValueError("encrypted hardcode file is not AES-block aligned")
    ctx = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return (ctx.update(data) + ctx.finalize()).rstrip(b"\0")


def redacted_inventory(plaintext: bytes) -> str:
    text = plaintext.decode("utf-8", "replace")
    if "-----BEGIN RSA PRIVATE KEY-----" in text:
        return "RSA private key present (PEM value redacted)\n"
    lines = []
    for line in text.splitlines():
        if "=" in line:
            lines.append(line.split("=", 1)[0] + "=<redacted>")
        elif line.strip():
            lines.append(line)
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--model-file", type=Path, required=True,
                        help="plaintext /etc/hardcode file, e.g. SR1010_QD")
    parser.add_argument("--inventory", type=Path,
                        help="write names-only/redacted inventory")
    parser.add_argument("--plaintext", type=Path,
                        help="write sensitive plaintext locally; never commit this output")
    args = parser.parse_args()

    model = args.model_file.read_text(encoding="ascii").strip()
    plaintext = decrypt(args.input.read_bytes(), derive_key(model))
    if args.inventory:
        args.inventory.write_text(redacted_inventory(plaintext), encoding="utf-8")
    if args.plaintext:
        args.plaintext.write_bytes(plaintext)
    if not args.inventory and not args.plaintext:
        print(redacted_inventory(plaintext), end="")
    print(f"model={model} plaintext_bytes={len(plaintext)}")


if __name__ == "__main__":
    main()

