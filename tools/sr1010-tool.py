#!/usr/bin/env python3
"""Unified SR1010 offline analysis and recovery command line."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SLOTS = {
    "current": (0x00600000, 0x02F00000, 0x02460000),
    "backup": (0x02F00000, 0x05800000, 0x04D60000),
}


def delegate(script: str, rest: list[str]) -> int:
    return subprocess.call([sys.executable, str(HERE / script), *rest])


def digest(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            h.update(block)
    return size, h.hexdigest()


def cmd_manifest(args) -> int:
    size, sha = digest(args.file)
    result = {"file": args.file.name, "size": size, "sha256": sha}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


def cmd_extract_header(args) -> int:
    _, _, offset = SLOTS[args.slot]
    with args.flash.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(0x510)
    if len(data) != 0x510:
        raise SystemExit("flash image is too short for selected header")
    args.output.write_bytes(data)
    print(f"offset=0x{offset:08x}")
    print("size=0x510")
    return 0


def cmd_extract_slot(args) -> int:
    start, end, _ = SLOTS[args.slot]
    with args.flash.open("rb") as source, args.output.open("wb") as target:
        source.seek(start)
        remaining = end - start
        while remaining:
            block = source.read(min(1024 * 1024, remaining))
            if not block:
                raise SystemExit("flash image is too short for selected slot")
            target.write(block)
            remaining -= len(block)
    print(f"range=0x{start:08x}..0x{end:08x}")
    print(f"size=0x{end-start:x}")
    return 0


def cmd_flash_report(args) -> int:
    size, sha = digest(args.flash)
    print(f"flash.size={size}")
    print(f"flash.sha256={sha}")
    if size != 0x08000000:
        print("flash.size_ok=False")
        return 2
    print("flash.size_ok=True")
    return delegate("slot-header-compare.py", [str(args.flash)])


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="SR1010 offline recovery toolkit")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("manifest", help="hash a local artifact")
    p.add_argument("file", type=Path); p.add_argument("--output", type=Path); p.set_defaults(func=cmd_manifest)
    p = sub.add_parser("flash-report", help="validate full-flash size and both slot headers")
    p.add_argument("flash", type=Path); p.set_defaults(func=cmd_flash_report)
    p = sub.add_parser("extract-header", help="extract a 0x510-byte slot header")
    p.add_argument("flash", type=Path); p.add_argument("slot", choices=SLOTS); p.add_argument("output", type=Path); p.set_defaults(func=cmd_extract_header)
    p = sub.add_parser("extract-slot", help="extract one complete 41 MiB slot")
    p.add_argument("flash", type=Path); p.add_argument("slot", choices=SLOTS); p.add_argument("output", type=Path); p.set_defaults(func=cmd_extract_slot)
    delegated = {
        "nand-check": "nand-layout-check.py", "header-compare": "slot-header-compare.py",
        "header-rebase": "slot-header-rebase.py", "versionstates": "versionstates-readonly.py",
        "web-build": "build-current-web-firmware.py", "web-check": "web-firmware-preflight.py",
        "config-decrypt": "config-bin-decrypt.py", "config-pack": "config-bin-pack.py",
        "config-audit": "config-audit.py",
        "jffs2-extract": "jffs2-extract.py",
        "rootfs-compare": "slot-rootfs-compare.py",
        "firmware-layout": "firmware-layout.py",
        "recovery-kit": "recovery-kit.py",
        "config-tool": "config-bin-tool.py",
        "config-transaction": "config-transaction.py",
        "plugin-survival": "plugin-survival-audit.py",
        "upgrade-policy": "upgrade-policy-audit.py",
        "offline-selftest": "offline-selftest.py",
        "upgrade-plan": "upgrade-target-plan.py",
        "upgrade-control-audit": "upgrade-control-audit.py",
        "plugin-ipk-audit": "plugin-ipk-audit.py",
        "build-net-status": "build-net-runtime-status-ipk.py",
    }
    for name, script in delegated.items():
        p = sub.add_parser(name, help=f"run {script}", add_help=False)
        p.add_argument("args", nargs=argparse.REMAINDER)
        p.set_defaults(delegate_script=script)
    return ap


def main() -> int:
    args, unknown = build_parser().parse_known_args()
    if hasattr(args, "delegate_script"):
        # argparse with REMAINDER can split option values into ``unknown``;
        # preserve the user's exact order for delegated tools.
        return delegate(args.delegate_script, sys.argv[2:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
