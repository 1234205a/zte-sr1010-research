#!/bin/sh
set -eu
REC=/usercfg/sr1010-recovery
mkdir -p "$REC"; chmod 700 "$REC"
pid=$(lxc-info -n nativeC -pH)
ROOT=/proc/$pid/root
archive=$(setsid lxc-attach -n nativeC -- /opt/sr1010-net-runtime/backup.sh </dev/null)
test -s "$ROOT$archive"
cp "$ROOT$archive" "$REC/config-latest.tar.gz.tmp"
chmod 600 "$REC/config-latest.tar.gz.tmp"
mv "$REC/config-latest.tar.gz.tmp" "$REC/config-latest.tar.gz"
missing=
for f in start.sh stop.sh backup.sh restore.sh bin/wireguard-go bin/wg; do test -s "$ROOT/opt/sr1010-net-runtime/$f" || missing="$missing $f"; done
if test -n "$missing"; then echo "state=degraded missing=$missing" >"$REC/guard.status"; exit 1; fi
echo 'state=ready backup=/usercfg/sr1010-recovery/config-latest.tar.gz' >"$REC/guard.status"
chmod 600 "$REC/guard.status"
cat "$REC/guard.status"
