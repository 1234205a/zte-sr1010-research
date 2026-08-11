#!/usr/bin/env python3
"""Build the SR1010 ONT access plugin without device credentials."""

import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "ont-access"
spec = importlib.util.spec_from_file_location("base", HERE / "build-net-runtime-ipk.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

CONTROL = """Package: sr1010-ont-access
Version: 0.1.1
Architecture: arm
Maintainer: local
Description: persistent local web and telnet access to the V2802RH ONT
StartCMD: /opt/sr1010-ont-access/start.sh
StopCMD: /opt/sr1010-ont-access/stop.sh
StartMode: 0
"""

POSTINST = """#!/bin/sh
mkdir -p /opt/sr1010-ont-access/state
exit 0
"""

PRERM = """#!/bin/sh
test -x /opt/sr1010-ont-access/stop.sh && /opt/sr1010-ont-access/stop.sh >/dev/null 2>&1 || true
exit 0
"""


def build(binary: Path, output: Path) -> None:
    control = base.tgz([
        ("control", CONTROL, 0o644, False),
        ("postinst", POSTINST, 0o755, False),
        ("prerm", PRERM, 0o755, False),
    ])
    entries = [
        ("opt/", None, 0o755, True),
        ("opt/sr1010-ont-access/", None, 0o755, True),
        ("opt/sr1010-ont-access/bin/", None, 0o755, True),
        ("opt/sr1010-ont-access/state/", None, 0o755, True),
        ("opt/sr1010-ont-access/bin/ont-forwarder", binary.read_bytes(), 0o755, False),
    ]
    for name in ("start.sh", "stop.sh", "health.sh"):
        body = (SOURCE / name).read_bytes().replace(b"\r\n", b"\n")
        entries.append((f"opt/sr1010-ont-access/{name}", body, 0o755, False))
    data = base.tgz(entries)
    output.write_bytes(base.tgz([
        ("debian-binary", b"2.0\n", 0o644, False),
        ("control.tar.gz", control, 0o644, False),
        ("data.tar.gz", data, 0o644, False),
    ]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not args.binary.is_file():
        parser.error(f"missing binary: {args.binary}")
    build(args.binary, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
