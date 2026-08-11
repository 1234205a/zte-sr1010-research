#!/usr/bin/env python3
"""用 rdsquashfs --cat 从 SquashFS 精确导出文件，绕过 Windows 全量解包问题。"""
import argparse
import subprocess
from pathlib import Path, PurePosixPath


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rdsquashfs", required=True, type=Path)
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    for name in args.paths:
        rel = PurePosixPath(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise SystemExit(f"拒绝越界路径: {name}")
        proc = subprocess.run(
            [str(args.rdsquashfs), "--cat", name, str(args.image)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode:
            raise SystemExit(proc.stderr.decode("utf-8", "replace"))
        target = args.output.joinpath(*rel.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(proc.stdout)
        print(f"{name}: {len(proc.stdout)} bytes")


if __name__ == "__main__":
    main()
