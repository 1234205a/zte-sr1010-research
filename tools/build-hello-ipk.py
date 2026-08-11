#!/usr/bin/env python3
"""Build a deterministic, network-silent SR1010 plugin persistence probe."""

import argparse
import gzip
import io
import tarfile
from pathlib import Path


CONTROL = """Package: sr1010-hello
Version: 0.1.0
Architecture: all
Maintainer: local
Description: network-silent SR1010 PluginAutoStart probe
StartCMD: /opt/sr1010-hello/start.sh
StopCMD: /opt/sr1010-hello/stop.sh
StartMode: 0
"""

START = """#!/bin/sh
set -eu
BASE=/opt/sr1010-hello
STATE="$BASE/state"
mkdir -p "$STATE"
{
  echo "event=start"
  date 2>/dev/null || true
  echo "pid=$$"
  echo "uid=$(id -u 2>/dev/null || echo unknown)"
  echo "mount_plugin=$(mount 2>/dev/null | grep ' /plugin ' || true)"
} >> "$STATE/events.log"
exit 0
"""

STOP = """#!/bin/sh
set -eu
BASE=/opt/sr1010-hello
mkdir -p "$BASE/state"
{
  echo "event=stop"
  date 2>/dev/null || true
  echo "pid=$$"
} >> "$BASE/state/events.log"
exit 0
"""

HEALTH = """#!/bin/sh
BASE=/opt/sr1010-hello
echo "sr1010-hello: installed"
test -f "$BASE/state/events.log" && cat "$BASE/state/events.log"
exit 0
"""


def tar_gz(files):
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tf:
            for name, body, mode in files:
                info = tarfile.TarInfo(name)
                info.mode = mode
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = "root"
                if body is None:
                    info.type = tarfile.DIRTYPE
                    info.size = 0
                    tf.addfile(info)
                else:
                    payload = body.encode()
                    info.size = len(payload)
                    tf.addfile(info, io.BytesIO(payload))
    return raw.getvalue()


def build(output: Path):
    control = tar_gz([("control", CONTROL, 0o644)])
    data = tar_gz([
        ("opt", None, 0o755),
        ("opt/sr1010-hello", None, 0o755),
        ("opt/sr1010-hello/start.sh", START, 0o755),
        ("opt/sr1010-hello/stop.sh", STOP, 0o755),
        ("opt/sr1010-hello/health.sh", HEALTH, 0o755),
    ])
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tf:
            for name, payload, mode in (
                ("debian-binary", b"2.0\n", 0o644),
                ("control.tar.gz", control, 0o644),
                ("data.tar.gz", data, 0o644),
            ):
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                info.mode = mode
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = "root"
                tf.addfile(info, io.BytesIO(payload))
    output.write_bytes(raw.getvalue())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("output", nargs="?", type=Path, default=Path("sr1010-hello_0.1.0_all.ipk"))
    args = ap.parse_args()
    build(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
