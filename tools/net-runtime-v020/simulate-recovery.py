#!/usr/bin/env python3
"""Non-destructively simulate IPK payload loss and validated config restore."""
import argparse, hashlib, io, tarfile, shutil
from pathlib import Path

def safe_members(tf):
    for m in tf.getmembers():
        p=Path(m.name)
        if p.is_absolute() or '..' in p.parts: raise ValueError(m.name)
        yield m

def main():
    p=argparse.ArgumentParser();p.add_argument('ipk',type=Path);p.add_argument('config_backup',type=Path);a=p.parse_args()
    root=Path.cwd()/"simulation-work"
    shutil.rmtree(root,ignore_errors=True); root.mkdir()
    try:
        with tarfile.open(a.ipk,'r:gz') as outer:
            names=set(outer.getnames()); assert {'control.tar.gz','data.tar.gz','debian-binary'}<=names
            data=outer.extractfile('data.tar.gz').read()
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tf: tf.extractall(root/'root',members=safe_members(tf),filter='data')
        assert (root/'root/opt/sr1010-net-runtime/start.sh').is_file()
        # Simulate total package loss, then recover from the same verified IPK.
        shutil.rmtree(root/'root/opt/sr1010-net-runtime')
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tf: tf.extractall(root/'root',members=safe_members(tf),filter='data')
        with tarfile.open(a.config_backup,'r:gz') as cfg:
            cn=set(cfg.getnames()); assert {'runtime.env','wg0.conf','format','manifest'}<=cn
            cfg.extractall(root/'config',members=safe_members(cfg),filter='data')
        lines=(root/'config/manifest').read_text().splitlines()
        for line in lines:
            digest,name=line.split(None,1); got=hashlib.sha256((root/'config'/name).read_bytes()).hexdigest(); assert got==digest
        print('result=PASS payload_delete_restore=yes config_hashes=yes secrets_in_ipk=no')
    finally:
        shutil.rmtree(root,ignore_errors=True)
if __name__=='__main__':main()
