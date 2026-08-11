#!/bin/sh
set -eu
REC=/usercfg/sr1010-recovery
IPK=/opt/sr1010-net-runtime-backups/recovery.ipk
CFG=$REC/config-latest.tar.gz
test -s "$CFG"
pid=$(lxc-info -n nativeC -pH); ROOT=/proc/$pid/root
IPK="$ROOT$IPK"
test -s "$IPK"
tmp=/tmp/sr1010-recover-$$
mkdir -p "$tmp/outer" "$tmp/control"; trap 'rm -rf "$tmp"' EXIT HUP INT TERM
tar -C "$tmp/outer" -xzf "$IPK"
tar -C "$ROOT" -xzf "$tmp/outer/data.tar.gz"
tar -C "$tmp/control" -xzf "$tmp/outer/control.tar.gz"
mkdir -p "$ROOT/opt/sr1010-net-runtime-backups"
cp "$CFG" "$ROOT/opt/sr1010-net-runtime-backups/config-recovery-import.tar.gz"
chmod 600 "$ROOT/opt/sr1010-net-runtime-backups/config-recovery-import.tar.gz"
setsid lxc-attach -n nativeC -- /opt/sr1010-net-runtime/restore.sh /opt/sr1010-net-runtime-backups/config-recovery-import.tar.gz apply </dev/null
setsid lxc-attach -n nativeC -- /opt/sr1010-net-runtime/lifecycle-audit.sh </dev/null
