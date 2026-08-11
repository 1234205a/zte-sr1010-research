#!/usr/bin/env python3
"""复现 SR1010 cspd 的配置 AES-256-CBC 密钥/IV 派生。"""
import argparse
import hashlib


def derive(model: str, product="0510", variant="0001"):
    clean_model = "".join(model.split())
    suffix = (product.removeprefix("0x") + variant.removeprefix("0x"))[:31]
    key_phrase = f"{clean_model}Key{suffix}"
    iv_phrase = f"{clean_model}Iv{suffix}"
    return key_phrase, iv_phrase, hashlib.sha256(key_phrase.encode()).digest(), hashlib.sha256(iv_phrase.encode()).digest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="MODEL")
    ap.add_argument("--product", default="0510")
    ap.add_argument("--variant", default="0001")
    args = ap.parse_args()
    kp, ip, key, ivhash = derive(args.model, args.product, args.variant)
    print("key_phrase =", kp)
    print("iv_phrase  =", ip)
    print("aes256_key =", key.hex())
    print("cbc_iv     =", ivhash[:16].hex())


if __name__ == "__main__":
    main()
