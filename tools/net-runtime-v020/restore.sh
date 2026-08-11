#!/bin/sh
set -eu
BASE=/opt/sr1010-net-runtime
CFG=$BASE/config
DEST=/opt/sr1010-net-runtime-backups
archive=${1:-latest}
mode=${2:-apply}
if test "$archive" = latest; then archive=$(ls -1t "$DEST"/config-*.tar.gz 2>/dev/null | sed -n '1p'); fi
test -n "$archive" && test -f "$archive"
case "$archive" in "$DEST"/config-*.tar.gz) ;; *) echo invalid_archive_path >&2; exit 1;; esac
tmp="$DEST/.restore-$$"
old="$DEST/.rollback-$$"
mkdir -m 700 "$tmp" "$old"
trap 'rm -rf "$tmp" "$old"' EXIT HUP INT TERM
tar -tzf "$archive" | awk 'BEGIN{ok=1} /^\//{ok=0} /(^|\/)\.\.($|\/)/{ok=0} END{exit !ok}'
tar -C "$tmp" -xzf "$archive"
test -s "$tmp/runtime.env" && test -s "$tmp/wg0.conf" && test -s "$tmp/format" && test -s "$tmp/manifest"
grep -q '^sr1010-net-runtime-backup-v1$' "$tmp/format"
(cd "$tmp" && sha256sum -c manifest >/dev/null)
if test "$mode" = check; then echo "result=PASS archive=$archive"; exit 0; fi
test "$mode" = apply
cp "$CFG/runtime.env" "$old/runtime.env"
cp "$CFG/wg0.conf" "$old/wg0.conf"
"$BASE/stop.sh" >/dev/null 2>&1 || true
cp "$tmp/runtime.env" "$CFG/runtime.env"
cp "$tmp/wg0.conf" "$CFG/wg0.conf"
chmod 600 "$CFG/runtime.env" "$CFG/wg0.conf"
if "$BASE/start.sh" >/dev/null 2>&1; then echo "result=PASS archive=$archive"; exit 0; fi
cp "$old/runtime.env" "$CFG/runtime.env"
cp "$old/wg0.conf" "$CFG/wg0.conf"
chmod 600 "$CFG/runtime.env" "$CFG/wg0.conf"
"$BASE/start.sh" >/dev/null 2>&1 || true
echo restore_failed_rolled_back >&2
exit 1
