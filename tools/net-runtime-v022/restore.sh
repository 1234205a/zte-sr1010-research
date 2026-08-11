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
format=$(cat "$tmp/format")
case "$format" in
    sr1010-net-runtime-backup-v1) files="runtime.env wg0.conf" ;;
    sr1010-net-runtime-backup-v2) files="runtime.env wg0.conf dashboard.token"; test -s "$tmp/dashboard.token" ;;
    *) echo unsupported_backup_format >&2; exit 1 ;;
esac
(cd "$tmp" && sha256sum -c manifest >/dev/null)
if test "$mode" = check; then echo "result=PASS archive=$archive format=$format"; exit 0; fi
test "$mode" = apply
for file in runtime.env wg0.conf dashboard.token; do test ! -f "$CFG/$file" || cp "$CFG/$file" "$old/$file"; done
"$BASE/stop.sh" >/dev/null 2>&1 || true
for file in $files; do cp "$tmp/$file" "$CFG/$file"; done
chmod 600 "$CFG/runtime.env" "$CFG/wg0.conf"
test ! -f "$CFG/dashboard.token" || chmod 600 "$CFG/dashboard.token"
if "$BASE/start.sh" >/dev/null 2>&1; then echo "result=PASS archive=$archive format=$format"; exit 0; fi
for file in runtime.env wg0.conf dashboard.token; do
    if test -f "$old/$file"; then cp "$old/$file" "$CFG/$file"; else rm -f "$CFG/$file"; fi
done
chmod 600 "$CFG/runtime.env" "$CFG/wg0.conf"
test ! -f "$CFG/dashboard.token" || chmod 600 "$CFG/dashboard.token"
"$BASE/start.sh" >/dev/null 2>&1 || true
echo restore_failed_rolled_back >&2
exit 1

