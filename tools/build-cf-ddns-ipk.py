#!/usr/bin/env python3
"""Build a deterministic Cloudflare DDNS plugin for SR1010 nativeC."""

import argparse
import gzip
import io
import tarfile
from pathlib import Path


CONTROL = """Package: sr1010-cf-ddns
Version: 0.1.2
Architecture: all
Maintainer: local
Description: Cloudflare IPv4 DDNS updater for SR1010 nativeC
StartCMD: /opt/sr1010-cf-ddns/start.sh
StopCMD: /opt/sr1010-cf-ddns/stop.sh
StartMode: 0
"""

ENV_TEMPLATE = """# Non-secret template. Values are installed locally on the router.
CF_ZONE_ID=
CF_RECORD_ID=
CF_RECORD_NAME=
INTERVAL=120
MAX_BACKOFF=1800
"""

UPDATE = r'''#!/bin/sh
set -u
BASE=/opt/sr1010-cf-ddns
CFG=$BASE/config/ddns.env
AUTH=$BASE/config/curl-auth.conf
CA=$BASE/cacert.pem
STATE=$BASE/state
mkdir -p "$STATE"
. "$CFG"

record_result() {
    result=$1 detail=$2
    printf '%s\n' "$result" >"$STATE/last_result.tmp"
    printf '%s\n' "$detail" >"$STATE/last_error.tmp"
    mv "$STATE/last_result.tmp" "$STATE/last_result"
    mv "$STATE/last_error.tmp" "$STATE/last_error"
    date '+%Y-%m-%dT%H:%M:%S%z' >"$STATE/last_attempt" 2>/dev/null || true
}
fail() { record_result FAIL "$1"; echo "result=FAIL detail=$1"; exit 1; }

"$BASE/validate.sh" || fail config_invalid

valid_ipv4() {
    printf '%s\n' "$1" | awk -F. '
        BEGIN { ok=1 }
        NF != 4 { ok=0 }
        { for (i=1; i<=4; i++) if ($i !~ /^[0-9]+$/ || $i < 0 || $i > 255) ok=0 }
        END { exit !ok }
    '
}

get_ip() {
    for url in https://api.ipify.org https://checkip.amazonaws.com https://icanhazip.com; do
        ip=$(curl --cacert "$CA" -4 -fsS --connect-timeout 10 "$url" 2>/dev/null | tr -d '\r\n ')
        valid_ipv4 "$ip" && { echo "$ip"; return 0; }
    done
    return 1
}

ip=$(get_ip) || fail public_ip_unavailable
last=$(cat "$STATE/last_ip" 2>/dev/null || true)
if test "${1:-}" != --force && test "$last" = "$ip"; then
    record_result PASS none
    echo "result=PASS action=unchanged ip=$ip"
    exit 0
fi

payload="$STATE/payload.json"
response="$STATE/response.json"
printf '{"type":"A","name":"%s","content":"%s","ttl":60,"proxied":false}\n' \
    "$CF_RECORD_NAME" "$ip" >"$payload"
chmod 600 "$payload"
url="https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/dns_records/$CF_RECORD_ID"
curl_rc=0
http=$(curl --cacert "$CA" --config "$AUTH" -sS -o "$response" -w '%{http_code}' -X PATCH --data-binary "@$payload" "$url") || curl_rc=$?
chmod 600 "$response"
case "$http" in
    200) ;;
    401|403) rm -f "$payload" "$response"; fail cloudflare_auth ;;
    404) rm -f "$payload" "$response"; fail cloudflare_record_not_found ;;
    429) rm -f "$payload" "$response"; fail cloudflare_rate_limited ;;
    5??) rm -f "$payload" "$response"; fail cloudflare_server ;;
    000|'') rm -f "$payload" "$response"; fail cloudflare_transport ;;
    *) rm -f "$payload" "$response"; fail cloudflare_http ;;
esac
test "$curl_rc" -eq 0 || { rm -f "$payload" "$response"; fail cloudflare_transport; }
if ! grep -q '"success":true' "$response"; then
    rm -f "$payload" "$response"
    fail cloudflare_api
fi
printf '%s\n' "$ip" >"$STATE/last_ip.tmp"
mv "$STATE/last_ip.tmp" "$STATE/last_ip"
date '+%Y-%m-%dT%H:%M:%S%z' >"$STATE/last_success" 2>/dev/null || true
record_result PASS none
rm -f "$payload" "$response"
echo "result=PASS action=updated ip=$ip"
'''

LOOP = r'''#!/bin/sh
BASE=/opt/sr1010-cf-ddns
. "$BASE/config/ddns.env"
interval=${INTERVAL:-120}
max_backoff=${MAX_BACKOFF:-1800}
case "$interval" in ''|*[!0-9]*) interval=120;; esac
case "$max_backoff" in ''|*[!0-9]*) max_backoff=1800;; esac
test "$interval" -ge 60 || interval=60
test "$max_backoff" -ge "$interval" || max_backoff=$interval
STATE=$BASE/state
mkdir -p "$STATE"
failures=0
heartbeat() {
    now=$(date +%s 2>/dev/null || echo 0)
    printf '%s\n' "$now" >"$STATE/heartbeat_epoch.tmp"
    mv "$STATE/heartbeat_epoch.tmp" "$STATE/heartbeat_epoch"
}
while :; do
    heartbeat
    if "$BASE/update.sh" >>"$STATE/events.log" 2>&1; then
        failures=0
        delay=$interval
    else
        failures=$((failures + 1))
        shift_count=$failures
        test "$shift_count" -le 4 || shift_count=4
        delay=$interval
        while test "$shift_count" -gt 0; do delay=$((delay * 2)); shift_count=$((shift_count - 1)); done
        test "$delay" -le "$max_backoff" || delay=$max_backoff
    fi
    printf '%s\n' "$failures" >"$STATE/consecutive_failures.tmp"
    mv "$STATE/consecutive_failures.tmp" "$STATE/consecutive_failures"
    now=$(date +%s 2>/dev/null || echo 0)
    printf '%s\n' "$((now + delay))" >"$STATE/next_retry_epoch.tmp"
    mv "$STATE/next_retry_epoch.tmp" "$STATE/next_retry_epoch"
    size=$(wc -c <"$BASE/state/events.log" 2>/dev/null || echo 0)
    if test "$size" -gt 65536; then
        tail -n 200 "$BASE/state/events.log" >"$BASE/state/events.log.tmp"
        mv "$BASE/state/events.log.tmp" "$BASE/state/events.log"
    fi
    remaining=$delay
    while test "$remaining" -gt 0; do
        heartbeat
        chunk=30
        test "$remaining" -ge "$chunk" || chunk=$remaining
        sleep "$chunk"
        remaining=$((remaining - chunk))
    done
done
'''

VALIDATE = r'''#!/bin/sh
set -u
BASE=/opt/sr1010-cf-ddns
CFG=${1:-$BASE/config}
ENV=$CFG/ddns.env
AUTH=$CFG/curl-auth.conf
test -s "$ENV" && test -s "$AUTH" || { echo result=FAIL detail=config_missing; exit 1; }
test "$(stat -c '%a' "$ENV" 2>/dev/null)" = 600 || { echo result=FAIL detail=env_mode; exit 1; }
test "$(stat -c '%a' "$AUTH" 2>/dev/null)" = 600 || { echo result=FAIL detail=auth_mode; exit 1; }
if grep -Ev '^(#.*|[[:space:]]*|CF_ZONE_ID=[0-9A-Fa-f]{32}|CF_RECORD_ID=[0-9A-Fa-f]{32}|CF_RECORD_NAME=[A-Za-z0-9._-]+|INTERVAL=[0-9]+|MAX_BACKOFF=[0-9]+)$' "$ENV" | grep -q .; then
    echo result=FAIL detail=env_format; exit 1
fi
for key in CF_ZONE_ID CF_RECORD_ID CF_RECORD_NAME; do
    test "$(grep -c "^$key=" "$ENV")" -eq 1 || { echo result=FAIL detail=env_duplicate_or_missing; exit 1; }
done
if grep -Ev '^([[:space:]]*header[[:space:]]*=[[:space:]]*"Authorization: Bearer [A-Za-z0-9._-]+"[[:space:]]*|[[:space:]]*header[[:space:]]*=[[:space:]]*"Content-Type: application/json"[[:space:]]*|silent|show-error|fail|[[:space:]]*)$' "$AUTH" | grep -q .; then
    echo result=FAIL detail=auth_format; exit 1
fi
test "$(grep -Ec '^[[:space:]]*header[[:space:]]*=[[:space:]]*"Authorization: Bearer [A-Za-z0-9._-]+"[[:space:]]*$' "$AUTH")" -eq 1 || { echo result=FAIL detail=auth_format; exit 1; }
test "$(grep -Ec '^[[:space:]]*header[[:space:]]*=[[:space:]]*"Content-Type: application/json"[[:space:]]*$' "$AUTH")" -eq 1 || { echo result=FAIL detail=auth_format; exit 1; }
for option in silent show-error fail; do
    test "$(grep -c "^$option$" "$AUTH")" -eq 1 || { echo result=FAIL detail=auth_format; exit 1; }
done
. "$ENV"
for v in CF_ZONE_ID CF_RECORD_ID CF_RECORD_NAME; do
    eval value=\${$v:-}
    test -n "$value" || { echo "result=FAIL detail=missing_$v"; exit 1; }
done
case "$CF_ZONE_ID$CF_RECORD_ID" in *[!0-9a-fA-F]*) echo result=FAIL detail=id_format; exit 1;; esac
test "${#CF_ZONE_ID}" -eq 32 && test "${#CF_RECORD_ID}" -eq 32 || { echo result=FAIL detail=id_length; exit 1; }
case "$CF_RECORD_NAME" in *[!A-Za-z0-9._-]*|'') echo result=FAIL detail=record_name; exit 1;; esac
grep -q 'Authorization:' "$AUTH" || { echo result=FAIL detail=auth_header_missing; exit 1; }
echo result=PASS
'''

START = r'''#!/bin/sh
set -u
BASE=/opt/sr1010-cf-ddns
STATE=$BASE/state
mkdir -p "$STATE"
"$BASE/validate.sh" >/dev/null || exit 1
candidate=
for path in /proc/[0-9]*; do
    test -r "$path/cmdline" || continue
    pid=${path#/proc/}
    tr '\000' ' ' <"$path/cmdline" 2>/dev/null | grep -q "$BASE/loop.sh" || continue
    candidate=$pid
    break
done
if test -n "$candidate"; then
    sleep 2
    if kill -0 "$candidate" 2>/dev/null &&
       tr '\000' ' ' <"/proc/$candidate/cmdline" 2>/dev/null | grep -q "$BASE/loop.sh"; then
        echo "$candidate" >"$STATE/loop.pid"
        exit 0
    fi
fi
if test -s "$STATE/loop.pid"; then
    pid=$(cat "$STATE/loop.pid")
    if kill -0 "$pid" 2>/dev/null &&
       tr '\000' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q "$BASE/loop.sh"; then
        exit 0
    fi
    rm -f "$STATE/loop.pid"
fi
"$BASE/loop.sh" </dev/null >/dev/null 2>&1 &
echo $! >"$STATE/loop.pid"
exit 0
'''

STOP = r'''#!/bin/sh
BASE=/opt/sr1010-cf-ddns
PID=$BASE/state/loop.pid
signal_loops() {
    signal=$1
    found=0
    for path in /proc/[0-9]*; do
        test -r "$path/cmdline" || continue
        pid=${path#/proc/}
        tr '\000' ' ' <"$path/cmdline" 2>/dev/null | grep -q "$BASE/loop.sh" || continue
        found=1
        kill "-$signal" "$pid" 2>/dev/null || true
    done
    return "$found"
}
signal_loops TERM || true
round=0
while test "$round" -lt 5; do
    signal_loops 0 && break
    sleep 1
    round=$((round + 1))
done
signal_loops KILL || true
rm -f "$PID" "$BASE/state/heartbeat_epoch"
exit 0
'''

HEALTH = r'''#!/bin/sh
BASE=/opt/sr1010-cf-ddns
STATE=$BASE/state
echo 'package=sr1010-cf-ddns'
running=0
if test -s "$STATE/loop.pid" && kill -0 "$(cat "$STATE/loop.pid")" 2>/dev/null; then
    pid=$(cat "$STATE/loop.pid")
    tr '\000' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q "$BASE/loop.sh" && running=1
fi
if test "$running" = 0 && test -s "$STATE/heartbeat_epoch"; then
    heartbeat=$(cat "$STATE/heartbeat_epoch" 2>/dev/null || echo 0)
    now=$(date +%s 2>/dev/null || echo 0)
    case "$heartbeat$now" in *[!0-9]*) ;; *) test "$((now - heartbeat))" -le 45 && running=1;; esac
fi
test "$running" = 1 && echo 'loop=running' || echo 'loop=stopped'
test -f "$STATE/last_ip" && echo "last_ip=$(cat "$STATE/last_ip")" || echo 'last_ip=unknown'
test -f "$STATE/last_success" && echo "last_success=$(cat "$STATE/last_success")" || echo 'last_success=never'
test -f "$STATE/last_result" && echo "last_result=$(cat "$STATE/last_result")" || echo 'last_result=unknown'
test -f "$STATE/last_error" && echo "last_error=$(cat "$STATE/last_error")" || echo 'last_error=unknown'
test -f "$STATE/consecutive_failures" && echo "consecutive_failures=$(cat "$STATE/consecutive_failures")" || echo 'consecutive_failures=0'
test -f "$STATE/next_retry_epoch" && echo "next_retry_epoch=$(cat "$STATE/next_retry_epoch")" || echo 'next_retry_epoch=unknown'
'''

BACKUP = r'''#!/bin/sh
set -eu
BASE=/opt/sr1010-cf-ddns
CFG=$BASE/config
DEST=/opt/sr1010-cf-ddns-backups
mkdir -p "$DEST"; chmod 700 "$DEST"
test -s "$CFG/ddns.env"; test -s "$CFG/curl-auth.conf"
"$BASE/validate.sh" >/dev/null
stamp=$(date '+%Y%m%d-%H%M%S' 2>/dev/null || echo unknown)
tmp="$DEST/.backup-$stamp-$$"; mkdir -m 700 "$tmp"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
cp "$CFG/ddns.env" "$CFG/curl-auth.conf" "$tmp/"; chmod 600 "$tmp"/*
(cd "$tmp" && sha256sum ddns.env curl-auth.conf) >"$tmp/manifest"
echo sr1010-cf-ddns-backup-v1 >"$tmp/format"
tar -C "$tmp" -czf "$DEST/config-$stamp.tar.gz.tmp" ddns.env curl-auth.conf manifest format
chmod 600 "$DEST/config-$stamp.tar.gz.tmp"; mv "$DEST/config-$stamp.tar.gz.tmp" "$DEST/config-$stamp.tar.gz"
ls -1t "$DEST"/config-*.tar.gz 2>/dev/null | awk 'NR>10' | while read old; do rm -f "$old"; done
echo "$DEST/config-$stamp.tar.gz"
'''

RESTORE = r'''#!/bin/sh
set -eu
BASE=/opt/sr1010-cf-ddns; CFG=$BASE/config; DEST=/opt/sr1010-cf-ddns-backups
archive=${1:-latest}; mode=${2:-apply}
test "$archive" != latest || archive=$(ls -1t "$DEST"/config-*.tar.gz 2>/dev/null | sed -n '1p')
case "$archive" in "$DEST"/config-*.tar.gz) ;; *) echo invalid_archive >&2; exit 1;; esac
tmp="$DEST/.restore-$$"; old="$DEST/.rollback-$$"; mkdir -m 700 "$tmp" "$old"; trap 'rm -rf "$tmp" "$old"' EXIT HUP INT TERM
tar -tzf "$archive" | awk 'BEGIN{ok=1} /^\//{ok=0} /(^|\/)\.\.($|\/)/{ok=0} END{exit !ok}'
tar -C "$tmp" -xzf "$archive"; grep -q '^sr1010-cf-ddns-backup-v1$' "$tmp/format"
(cd "$tmp" && sha256sum -c manifest >/dev/null)
chmod 600 "$tmp/ddns.env" "$tmp/curl-auth.conf"
"$BASE/validate.sh" "$tmp" >/dev/null
test "$mode" = check && { echo result=PASS; exit 0; }; test "$mode" = apply
old_present=0
if test -s "$CFG/ddns.env" && test -s "$CFG/curl-auth.conf"; then
    cp "$CFG/ddns.env" "$CFG/curl-auth.conf" "$old/"
    old_present=1
fi
"$BASE/stop.sh" >/dev/null 2>&1 || true
cp "$tmp/ddns.env" "$tmp/curl-auth.conf" "$CFG/"; chmod 600 "$CFG/ddns.env" "$CFG/curl-auth.conf"
if "$BASE/validate.sh" >/dev/null && "$BASE/start.sh" >/dev/null 2>&1; then echo result=PASS; exit 0; fi
if test "$old_present" = 1; then
    cp "$old/ddns.env" "$old/curl-auth.conf" "$CFG/"
    chmod 600 "$CFG/ddns.env" "$CFG/curl-auth.conf"
else
    rm -f "$CFG/ddns.env" "$CFG/curl-auth.conf"
fi
"$BASE/start.sh" >/dev/null 2>&1 || true
echo restore_failed_rolled_back >&2
exit 1
'''

POST_HEALTH = r'''#!/bin/sh
mode=${1:-check}; BASE=/opt/sr1010-cf-ddns
"$BASE/validate.sh" >/dev/null || { echo result=FAIL detail=config_invalid; exit 1; }
chmod 600 "$BASE/config/ddns.env" "$BASE/config/curl-auth.conf" 2>/dev/null || true
test "$("$BASE/health.sh" 2>/dev/null | grep '^loop=running$')" = loop=running && { echo result=PASS; exit 0; }
test "$mode" = apply && "$BASE/start.sh" >/dev/null 2>&1 && echo result=PASS action=restarted && exit 0
echo result=FAIL detail=loop_stopped; exit 1
'''

POSTINST = r'''#!/bin/sh
BASE=/opt/sr1010-cf-ddns
chmod 700 "$BASE/config" 2>/dev/null || true
chmod 600 "$BASE/config/ddns.env" 2>/dev/null || true
chmod 600 "$BASE/config/curl-auth.conf" 2>/dev/null || true
if ls /opt/sr1010-cf-ddns-backups/config-*.tar.gz >/dev/null 2>&1; then "$BASE/restore.sh" latest apply >/dev/null 2>&1 || true; fi
exit 0
'''

PRERM = r'''#!/bin/sh
BASE=/opt/sr1010-cf-ddns
test -x "$BASE/backup.sh" && "$BASE/backup.sh" >/dev/null 2>&1 || true
test -x "$BASE/stop.sh" && "$BASE/stop.sh" >/dev/null 2>&1 || true
exit 0
'''


def tgz(entries):
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tf:
            for name, body, mode, is_dir in entries:
                info = tarfile.TarInfo(name)
                info.mode = mode
                info.mtime = info.uid = info.gid = 0
                info.uname = info.gname = "root"
                if is_dir:
                    info.type = tarfile.DIRTYPE
                    info.size = 0
                    tf.addfile(info)
                else:
                    data = body if isinstance(body, bytes) else body.encode()
                    info.size = len(data)
                    tf.addfile(info, io.BytesIO(data))
    return raw.getvalue()


def build(output, cacert):
    control = tgz([("control", CONTROL, 0o644, False), ("postinst", POSTINST, 0o755, False), ("prerm", PRERM, 0o755, False)])
    entries = [
        ("opt/", None, 0o755, True),
        ("opt/sr1010-cf-ddns/", None, 0o755, True),
        ("opt/sr1010-cf-ddns/config/", None, 0o700, True),
        ("opt/sr1010-cf-ddns/state/", None, 0o700, True),
        ("opt/sr1010-cf-ddns/cacert.pem", cacert.read_bytes(), 0o644, False),
        ("opt/sr1010-cf-ddns/config/ddns.env", ENV_TEMPLATE, 0o600, False),
        ("opt/sr1010-cf-ddns/update.sh", UPDATE, 0o755, False),
        ("opt/sr1010-cf-ddns/validate.sh", VALIDATE, 0o755, False),
        ("opt/sr1010-cf-ddns/loop.sh", LOOP, 0o755, False),
        ("opt/sr1010-cf-ddns/start.sh", START, 0o755, False),
        ("opt/sr1010-cf-ddns/stop.sh", STOP, 0o755, False),
        ("opt/sr1010-cf-ddns/health.sh", HEALTH, 0o755, False),
        ("opt/sr1010-cf-ddns/backup.sh", BACKUP, 0o755, False),
        ("opt/sr1010-cf-ddns/restore.sh", RESTORE, 0o755, False),
        ("opt/sr1010-cf-ddns/post-upgrade-health.sh", POST_HEALTH, 0o755, False),
    ]
    data = tgz(entries)
    output.write_bytes(tgz([
        ("debian-binary", b"2.0\n", 0o644, False),
        ("control.tar.gz", control, 0o644, False),
        ("data.tar.gz", data, 0o644, False),
    ]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cacert", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    build(args.output, args.cacert)
    print(args.output)
