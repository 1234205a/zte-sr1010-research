#!/usr/bin/env python3
"""离线检查SR1010旧式tar-IPK及nativeC启动字段。"""
import argparse
import io
import tarfile
from pathlib import Path


def parse_control(raw):
    result = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ipk", type=Path)
    args = ap.parse_args()
    with tarfile.open(args.ipk, "r:gz") as outer:
        names = set(outer.getnames())
        required = {"debian-binary", "control.tar.gz", "data.tar.gz"}
        if not required <= names:
            raise SystemExit(f"缺少外层成员: {sorted(required - names)}")
        control_blob = outer.extractfile("control.tar.gz").read()
        data_blob = outer.extractfile("data.tar.gz").read()
    with tarfile.open(fileobj=io.BytesIO(control_blob), mode="r:gz") as archive:
        control = parse_control(archive.extractfile("control").read())
    with tarfile.open(fileobj=io.BytesIO(data_blob), mode="r:gz") as archive:
        members = archive.getmembers()
        data_names = {m.name.rstrip("/") for m in members}
        dirs = {m.name.rstrip("/") for m in members if m.isdir()}

    for key in ("Package", "Version", "StartCMD", "StopCMD", "StartMode"):
        print(f"{key}={control.get(key, '')}")
    start = control.get("StartCMD", "").lstrip("/")
    stop = control.get("StopCMD", "").lstrip("/")
    parent_ok = all(str(Path(x).parent).replace("\\", "/") in dirs for x in (start, stop))
    checks = {
        "start_file": start in data_names,
        "stop_file": stop in data_names,
        "explicit_parent_dirs": parent_ok,
        "nativec_startmode": control.get("StartMode") == "0",
    }
    for key, value in checks.items():
        print(f"{key}={'yes' if value else 'no'}")
    if not all(checks.values()):
        raise SystemExit(2)
    print("result=PASS")


if __name__ == "__main__":
    main()
