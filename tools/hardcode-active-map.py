#!/usr/bin/env python3
"""Cross-reference decrypted hardcode keys with a decrypted DB XML safely.

The report contains key names and match states only; it never emits values.
Decrypted inputs must remain local and must not be committed.
"""

import argparse
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET


def read_hardcode(path: Path):
    result = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def read_db(path: Path):
    root = ET.parse(path).getroot()
    result = {}
    for table in root.findall(".//Tbl"):
        table_name = table.get("name", "")
        for row in table.findall("Row"):
            try:
                instance = int(row.get("No", "0")) + 1
            except ValueError:
                instance = row.get("No", "0")
            for dm in row.findall("DM"):
                name = dm.get("name", "")
                value = dm.get("val", "")
                result[f"{table_name}.{instance}.{name}"] = value
                result.setdefault(f"{table_name}.{name}", value)
                result.setdefault(name, value)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hardcode", type=Path)
    ap.add_argument("config_xml", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    hardcode = read_hardcode(args.hardcode)
    db = read_db(args.config_xml)
    rows = []
    counts = {"equal": 0, "different": 0, "absent": 0}
    for key, expected in sorted(hardcode.items()):
        if key not in db:
            state = "absent"
        elif db[key] == expected:
            state = "equal"
        else:
            state = "different"
        counts[state] += 1
        rows.append((key, state))

    h1 = hashlib.sha256(args.hardcode.read_bytes()).hexdigest()
    h2 = hashlib.sha256(args.config_xml.read_bytes()).hexdigest()
    lines = [
        "# Hardcode/current-config redacted cross-reference",
        "",
        f"- hardcode_sha256: `{h1}`",
        f"- config_sha256: `{h2}`",
        f"- keys: {len(rows)}",
        f"- equal: {counts['equal']}",
        f"- different: {counts['different']}",
        f"- absent: {counts['absent']}",
        "",
        "| key | state |",
        "|---|---|",
    ]
    lines.extend(f"| `{key}` | {state} |" for key, state in rows)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output}: {counts}")


if __name__ == "__main__":
    main()
