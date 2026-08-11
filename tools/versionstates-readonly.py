#!/usr/bin/env python3
"""Summarise an SR1010 /proc/*/versionstates snapshot without exposing serials."""

import argparse
import re
from pathlib import Path


def number(line: str) -> int | None:
    match = re.search(r"0x[0-9a-f]+|\b\d+\b", line, re.I)
    return int(match.group(0), 0) if match else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", type=Path)
    ap.add_argument("--show-serials", action="store_true")
    args = ap.parse_args()
    rows = []
    for line in args.snapshot.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line:
            key, value = (part.strip() for part in line.split(":", 1))
            rows.append((key, value, number(value)))

    values: dict[str, int] = {key: val for key, _, val in rows if val is not None}
    active_flags = [val for key, _, val in rows if key == "IsCurrentVersion"]
    print(f"current.active={active_flags[0] if active_flags else 'unknown'}")
    print(f"backup.active={active_flags[1] if len(active_flags) > 1 else 'unknown'}")
    mapping = (
        ("current.boot", "curverBootStartPhyAddr"),
        ("current.image", "currentverphyaddr"),
        ("current.header", "curverheaderaddr"),
        ("current.jffs", "curverjffs"),
        ("current.sign_size", "curversignsize"),
        ("current.bad", "curverIsBad"),
        ("backup.image", "backverphyaddr"),
        ("backup.header", "backverheaderaddr"),
        ("backup.jffs", "backverjffs"),
        ("backup.bad", "backverIsBad"),
        ("upgrade.key1", "curUpgradeKey1"),
        ("upgrade.key2", "curUpgradeKey2"),
        ("versions.max", "maxversionum"),
    )
    for label, key in mapping:
        if key in values:
            print(f"{label}=0x{values[key]:08x}")
    if args.show_serials:
        for key, raw, _ in rows:
            if "SerialNumber" in key:
                print(f"{key}={raw}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
