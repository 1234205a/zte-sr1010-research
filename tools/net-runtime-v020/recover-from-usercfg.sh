#!/bin/sh
set -eu
BASE=/opt/sr1010-net-runtime
REC=/usercfg/sr1010-recovery
IPK=$REC/sr1010-net-runtime_0.2.0_arm.ipk
CFG=$REC/config-latest.tar.gz
test -s "$IPK"
test -s "$CFG"
tmp=/tmp/sr1010-net-runtime-recover-$$
mkdir -p "$tmp/control" "$tmp/outer"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
tar -C "$tmp/outer" -xzf "$IPK"
test -s "$tmp/outer/data.tar.gz" && test -s "$tmp/outer/control.tar.gz"
tar -C / -xzf "$tmp/outer/data.tar.gz"
tar -C "$tmp/control" -xzf "$tmp/outer/control.tar.gz"
test -x "$tmp/control/postinst" && "$tmp/control/postinst"
mkdir -p /opt/sr1010-net-runtime-backups
cp "$CFG" /opt/sr1010-net-runtime-backups/recovery-import.tar.gz
chmod 600 /opt/sr1010-net-runtime-backups/recovery-import.tar.gz
$BASE/restore.sh /opt/sr1010-net-runtime-backups/recovery-import.tar.gz apply
$BASE/lifecycle-audit.sh
