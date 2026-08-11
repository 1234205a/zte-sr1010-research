#!/usr/bin/env python3
"""Reproduce the SR1010 SBus connection-key derivation.

Inputs are supplied locally. Nothing is read from router configuration and the
default output is fingerprints only. Use --show-derived only in a private shell.
"""

import argparse
import hashlib


def derive(psk: str, device_id: str) -> bytes:
    # Firmware: snprintf(buf, 0x101, "%.*s%s", 16, psk, deviceId)
    material = (psk[:16] + device_id).encode("utf-8")
    return hashlib.sha256(material).digest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psk", required=True)
    ap.add_argument("--device-id", required=True)
    ap.add_argument("--show-derived", action="store_true")
    args = ap.parse_args()
    digest = derive(args.psk, args.device_id)
    print("material_sha256=" + hashlib.sha256(
        (args.psk[:16] + args.device_id).encode("utf-8")
    ).hexdigest())
    print("aes_key_fingerprint=" + hashlib.sha256(digest[:16]).hexdigest())
    print("ctr_state_fingerprint=" + hashlib.sha256(digest[16:]).hexdigest())
    if args.show_derived:
        print("derived_hex=" + digest.hex())


if __name__ == "__main__":
    main()
