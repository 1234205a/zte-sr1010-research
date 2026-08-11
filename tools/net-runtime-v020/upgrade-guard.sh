#!/bin/sh
set -eu
BASE=/opt/sr1010-net-runtime
REC=/usercfg/sr1010-recovery
mkdir -p "$REC"
chmod 700 "$REC"
archive=$($BASE/backup.sh)
cp "$archive" "$REC/config-latest.tar.gz.tmp"
chmod 600 "$REC/config-latest.tar.gz.tmp"
mv "$REC/config-latest.tar.gz.tmp" "$REC/config-latest.tar.gz"
missing=
for f in start.sh stop.sh backup.sh restore.sh bin/wireguard-go bin/wg; do
    test -s "$BASE/$f" || missing="$missing $f"
done
if test -n "$missing"; then
    echo "state=degraded missing=$missing" >"$REC/guard.status"
    exit 1
fi
echo "state=ready backup=$REC/config-latest.tar.gz" >"$REC/guard.status.tmp"
mv "$REC/guard.status.tmp" "$REC/guard.status"
chmod 600 "$REC/guard.status"
cat "$REC/guard.status"
