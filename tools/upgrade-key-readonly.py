#!/usr/bin/env python3
"""Read SR1010 upgrade-key state from a saved procfs snapshot."""

import argparse
import re
from pathlib import Path

FIELD_RE = re.compile(
    r"(?im)^\s*(curUpgradeKey[12])\s*(?:[:=]|\s)\s*(0x[0-9a-f]+|[0-9a-f]+)\s*$"
)


def parse(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for name, raw in FIELD_RE.findall(text):
        base = 16 if raw.lower().startswith("0x") or re.search(r"[a-f]", raw, re.I) else 10
        result[name] = int(raw, base)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect a saved SR1010 versionstates file")
    ap.add_argument("snapshot", type=Path)
    args = ap.parse_args()
    values = parse(args.snapshot.read_text(encoding="utf-8", errors="replace"))
    missing = [x for x in ("curUpgradeKey1", "curUpgradeKey2") if x not in values]
    if missing:
        print("未找到字段：" + ", ".join(missing))
        return 2
    k1, k2 = values["curUpgradeKey1"], values["curUpgradeKey2"]
    print(f"curUpgradeKey1=0x{k1:08x}")
    print(f"curUpgradeKey2=0x{k2:08x}")
    if k1 in (0, 0xFFFF):
        print("策略：key1 为哨兵值，cspd 跳过 upgrade-key 比较。")
    else:
        print("策略：升级包 key1/key2 必须同时与设备当前值相等。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
