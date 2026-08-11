#!/bin/sh
set -eu
BASE=/opt/sr1010-net-runtime
CFG=$BASE/config
DEST=/opt/sr1010-net-runtime-backups
FILES="runtime.env wg0.conf dashboard.token"
mkdir -p "$DEST"
chmod 700 "$DEST"
for file in $FILES; do
    test -s "$CFG/$file"
    test "$(stat -c '%a' "$CFG/$file")" = 600
done
stamp=$(date '+%Y%m%d-%H%M%S' 2>/dev/null || echo unknown)
tmp="$DEST/.backup-$stamp-$$"
mkdir -m 700 "$tmp"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
for file in $FILES; do cp "$CFG/$file" "$tmp/$file"; done
chmod 600 "$tmp"/*
echo 'sr1010-net-runtime-backup-v2' >"$tmp/format"
(cd "$tmp" && sha256sum $FILES) >"$tmp/manifest"
chmod 600 "$tmp/format" "$tmp/manifest"
out="$DEST/config-$stamp.tar.gz"
tar -C "$tmp" -czf "$out.tmp" $FILES format manifest
chmod 600 "$out.tmp"
mv "$out.tmp" "$out"
ls -1t "$DEST"/config-*.tar.gz 2>/dev/null | awk 'NR>10' | while read old; do rm -f "$old"; done
echo "$out"

