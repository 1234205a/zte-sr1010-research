#!/bin/sh
set -eu
BASE=/opt/sr1010-net-runtime
TOKEN=$BASE/config/dashboard.token
BACKUPS=/opt/sr1010-net-runtime-backups

if test -s "$TOKEN"; then
    chmod 600 "$TOKEN"
    exit 0
fi
rm -f "$TOKEN"

archive=$(ls -1t "$BACKUPS"/config-*.tar.gz 2>/dev/null | sed -n '1p' || true)
if test -n "$archive"; then
    tmp="$BACKUPS/.token-restore-$$"
    mkdir -m 700 "$tmp"
    trap 'rm -rf "$tmp"' EXIT HUP INT TERM
    if tar -tzf "$archive" | awk 'BEGIN{ok=1} /^\//{ok=0} /(^|\/)\.\.($|\/)/{ok=0} END{exit !ok}' &&
       tar -C "$tmp" -xzf "$archive" &&
       grep -q '^sr1010-net-runtime-backup-v2$' "$tmp/format" 2>/dev/null &&
       (cd "$tmp" && sha256sum -c manifest >/dev/null 2>&1) &&
       test -s "$tmp/dashboard.token"; then
        cp "$tmp/dashboard.token" "$TOKEN"
    fi
    rm -rf "$tmp"
    trap - EXIT HUP INT TERM
fi

if ! test -s "$TOKEN"; then
    umask 077
    tmp="$TOKEN.tmp.$$"
    dd if=/dev/urandom bs=32 count=1 2>/dev/null | sha256sum | awk '{print $1}' >"$tmp"
    test -s "$tmp"
    mv "$tmp" "$TOKEN"
fi
chmod 600 "$TOKEN"

