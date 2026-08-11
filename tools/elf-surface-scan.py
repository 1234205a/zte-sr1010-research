#!/usr/bin/env python3
"""Batch inventory ELF files and security-relevant strings in an extracted SR1010 tree."""

import argparse
import json
import re
from pathlib import Path

PATTERNS = {
    "auth": rb"(?i)(password|passwd|username|login|authenticate|authorization|credential|shadow)",
    "command": rb"(?i)(system\(|popen|/bin/sh|cmdline|shell|execve|PcStartProgram)",
    "hidden": rb"(?i)(hidden|debug|factory|maintenance|superadmin|rootlogin|telnet|dropbear)",
    "upgrade": rb"(?i)(upgrade|firmware|flashing|verify.?sign|public key|upgrade_key)",
    "cloud": rb"(?i)(mqtt|tr069|cloud|acsurl|reportserver|ztehome)",
    "recovery": rb"(?i)(recovery|failsafe|bootmode|reset.?button|factory.?reset|rollback)",
    "crypto": rb"(?i)(AES_|SHA256|RSA_|DSA_|decrypt|encrypt|hardcode.*key|derive.*key)",
}


def ascii_strings(data: bytes, minimum: int = 4):
    result = []
    start = 0
    while start < len(data):
        end = start
        while end < len(data) and (32 <= data[end] < 127 or data[end] == 9):
            end += 1
        if end - start >= minimum:
            result.append(data[start:end].decode("ascii", "replace"))
        start = max(start + 1, end + 1)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--evidence-limit", type=int, default=120)
    args = parser.parse_args()

    rows = []
    for path in args.root.rglob("*"):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if not data.startswith(b"\x7fELF"):
            continue
        strings = ascii_strings(data)
        joined = "\n".join(strings).encode()
        categories = {name: len(re.findall(pattern, joined)) for name, pattern in PATTERNS.items()}
        evidence = [
            value for value in strings
            if any(re.search(pattern, value.encode()) for pattern in PATTERNS.values())
        ][: args.evidence_limit]
        rows.append({
            "path": path.relative_to(args.root).as_posix(),
            "size": len(data),
            "categories": categories,
            "evidence": evidence,
        })

    rows.sort(key=lambda row: sum(row["categories"].values()), reverse=True)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ELF files: {len(rows)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()

