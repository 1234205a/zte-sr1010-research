#!/usr/bin/env python3
"""Offline decoder for SBus CoAP datagrams; never sends network traffic."""

import argparse
import json
from pathlib import Path


def extended(data, pos, nibble):
    if nibble < 13:
        return nibble, pos
    if nibble == 13:
        return 13 + data[pos], pos + 1
    if nibble == 14:
        return 269 + int.from_bytes(data[pos:pos + 2], "big"), pos + 2
    raise ValueError("reserved CoAP option nibble 15")


def decode(data):
    if len(data) < 4:
        raise ValueError("datagram shorter than CoAP header")
    first, code, msg_id = data[0], data[1], int.from_bytes(data[2:4], "big")
    version, msg_type, token_len = first >> 6, (first >> 4) & 3, first & 15
    if version != 1 or token_len > 8 or len(data) < 4 + token_len:
        raise ValueError("invalid CoAP header")
    pos = 4 + token_len
    token = data[4:pos]
    options, number = [], 0
    while pos < len(data) and data[pos] != 0xFF:
        head = data[pos]
        pos += 1
        delta, pos = extended(data, pos, head >> 4)
        length, pos = extended(data, pos, head & 15)
        number += delta
        value = data[pos:pos + length]
        if len(value) != length:
            raise ValueError("truncated CoAP option")
        pos += length
        options.append((number, value))
    payload = b""
    if pos < len(data) and data[pos] == 0xFF:
        payload = data[pos + 1:]
    return {
        "version": version,
        "type": msg_type,
        "code": f"{code >> 5}.{code & 31:02d}",
        "message_id": msg_id,
        "token_hex": token.hex(),
        "options": options,
        "payload": payload,
    }


def safe_json(value, show):
    if isinstance(value, dict):
        return {k: safe_json(v, show) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_json(v, show) for v in value]
    return value if show else f"<{type(value).__name__}>"


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", type=Path)
    src.add_argument("--hex")
    ap.add_argument("--show-values", action="store_true")
    args = ap.parse_args()
    raw = args.file.read_bytes() if args.file else bytes.fromhex(args.hex)
    packet = decode(raw)
    uri = "/".join(v.decode("utf-8", "replace") for n, v in packet["options"] if n == 11)
    print(f"coap version={packet['version']} type={packet['type']} code={packet['code']}")
    print(f"message_id={packet['message_id']} token={packet['token_hex']} uri_path=/{uri}")
    print("options=" + ",".join(f"{n}:{len(v)}" for n, v in packet["options"]))
    try:
        obj = json.loads(packet["payload"].decode("utf-8"))
        print(json.dumps(safe_json(obj, args.show_values), ensure_ascii=False, indent=2))
    except Exception:
        print(f"payload_len={len(packet['payload'])} payload_json=false")
        if args.show_values:
            print("payload_hex=" + packet["payload"].hex())


if __name__ == "__main__":
    main()

