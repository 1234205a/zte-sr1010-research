#!/usr/bin/env python3
"""Offline package lifecycle simulation for net-runtime 0.2.2."""
import argparse, hashlib, io, shutil, tarfile, tempfile
from pathlib import Path

PAYLOAD = Path("opt/sr1010-net-runtime")
CONFIG = PAYLOAD / "config"

def members(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for item in tf.getmembers():
            path = Path(item.name)
            assert not path.is_absolute() and ".." not in path.parts
        tf.extractall(members=tf.getmembers(), filter="data")

def unpack(ipk, root):
    with tarfile.open(ipk, "r:gz") as outer:
        names = set(outer.getnames())
        assert {"debian-binary", "control.tar.gz", "data.tar.gz"} <= names
        control = outer.extractfile("control.tar.gz").read()
        data = outer.extractfile("data.tar.gz").read()
    old = Path.cwd(); Path(root).mkdir(parents=True, exist_ok=True)
    try:
        import os
        os.chdir(root); members(data)
    finally:
        os.chdir(old)
    return control

def control_text(blob, name):
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        return tf.extractfile(name).read().decode()

def backup(config, out):
    files = ("runtime.env", "wg0.conf", "dashboard.token")
    for name in files:
        assert (config / name).is_file()
    manifest = "".join(f"{hashlib.sha256((config/name).read_bytes()).hexdigest()}  {name}\n" for name in files)
    with tarfile.open(out, "w:gz") as tf:
        for name in files:
            tf.add(config / name, arcname=name)
        for name, data in (("format", b"sr1010-net-runtime-backup-v2\n"), ("manifest", manifest.encode())):
            info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o600
            tf.addfile(info, io.BytesIO(data))

def restore(archive, config):
    with tarfile.open(archive, "r:gz") as tf:
        names = set(tf.getnames())
        assert {"runtime.env", "wg0.conf", "dashboard.token", "format", "manifest"} <= names
        assert tf.extractfile("format").read().strip() == b"sr1010-net-runtime-backup-v2"
        expected = tf.extractfile("manifest").read().decode().splitlines()
        for line in expected:
            digest, name = line.split(None, 1)
            assert hashlib.sha256(tf.extractfile(name).read()).hexdigest() == digest
        for name in ("runtime.env", "wg0.conf", "dashboard.token"):
            (config / name).write_bytes(tf.extractfile(name).read())

def main():
    p = argparse.ArgumentParser(); p.add_argument("old_ipk", type=Path); p.add_argument("new_ipk", type=Path)
    a = p.parse_args()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); old_control = unpack(a.old_ipk, root)
        config = root / CONFIG; config.mkdir(parents=True, exist_ok=True)
        secrets = {"runtime.env": b"ENABLE=1\n", "wg0.conf": b"[Interface]\nPrivateKey=offline-placeholder\n", "dashboard.token": b"offline-token\n"}
        for name, data in secrets.items(): (config / name).write_bytes(data)

        new_control = unpack(a.new_ipk, root)
        assert "Version: 0.2.1" in control_text(old_control, "control")
        assert "Version: 0.2.2" in control_text(new_control, "control")
        assert secrets == {name: (config / name).read_bytes() for name in secrets}
        postinst = control_text(new_control, "postinst")
        assert "token-ensure.sh" in postinst and "chmod 600" in postinst
        assert not any(name.endswith("dashboard.token") for name in tar_names(a.new_ipk))
        assert_shell_lf(a.new_ipk)

        archive = root / "config-v2.tar.gz"; backup(config, archive)
        shutil.rmtree(root / PAYLOAD)
        unpack(a.new_ipk, root)
        config = root / CONFIG; config.mkdir(parents=True, exist_ok=True)
        restore(archive, config)
        assert secrets == {name: (config / name).read_bytes() for name in secrets}

        shutil.rmtree(root / PAYLOAD)
        unpack(a.new_ipk, root)
        config = root / CONFIG; config.mkdir(parents=True, exist_ok=True)
        restore(archive, config)
        assert secrets == {name: (config / name).read_bytes() for name in secrets}
    print("install=PASS upgrade=PASS uninstall_restore=PASS reinstall=PASS token_not_embedded=PASS")

def tar_names(ipk):
    with tarfile.open(ipk, "r:gz") as outer:
        data = outer.extractfile("data.tar.gz").read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        return tf.getnames()

def assert_shell_lf(ipk):
    with tarfile.open(ipk, "r:gz") as outer:
        data = outer.extractfile("data.tar.gz").read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for item in tf.getmembers():
            if item.name.endswith(".sh"):
                assert b"\r\n" not in tf.extractfile(item).read(), item.name

if __name__ == "__main__": main()
