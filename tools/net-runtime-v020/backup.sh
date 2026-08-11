#!/bin/sh
set -eu
BASE=/opt/sr1010-net-runtime
CFG=$BASE/config
DEST=/opt/sr1010-net-runtime-backups
mkdir -p "$DEST"
chmod 700 "$DEST"
test -s "$CFG/runtime.env"
test -s "$CFG/wg0.conf"
test "$(stat -c '%a' "$CFG/runtime.env")" = 600
test "$(stat -c '%a' "$CFG/wg0.conf")" = 600
stamp=$(date '+%Y%m%d-%H%M%S' 2>/dev/null || echo unknown)
tmp="$DEST/.backup-$stamp-$$"
mkdir -m 700 "$tmp"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
cp "$CFG/runtime.env" "$tmp/runtime.env"
cp "$CFG/wg0.conf" "$tmp/wg0.conf"
chmod 600 "$tmp"/*
echo 'sr1010-net-runtime-backup-v1' >"$tmp/format"
(cd "$tmp" && sha256sum runtime.env wg0.conf) >"$tmp/manifest"
chmod 600 "$tmp/format" "$tmp/manifest"
out="$DEST/config-$stamp.tar.gz"
tar -C "$tmp" -czf "$out.tmp" runtime.env wg0.conf format manifest
chmod 600 "$out.tmp"
mv "$out.tmp" "$out"
ls -1t "$DEST"/config-*.tar.gz 2>/dev/null | awk 'NR>10' | while read old; do rm -f "$old"; done
echo "$out"
