#!/usr/bin/env python3
"""Build a deterministic, default-disabled SR1010 nativeC WireGuard package."""

import argparse
import gzip
import io
import tarfile
from pathlib import Path


CONTROL = """Package: sr1010-net-runtime
Version: 0.1.0
Architecture: arm
Maintainer: local
Description: default-disabled WireGuard runtime for SR1010 nativeC
StartCMD: /opt/sr1010-net-runtime/start.sh
StopCMD: /opt/sr1010-net-runtime/stop.sh
StartMode: 0
"""

RUNTIME_ENV = """# No secrets belong in this file or in Git.
ENABLE=0
INTERFACE=wg-nrt0
CONFIG=/opt/sr1010-net-runtime/config/wg0.conf
ADDRESS=
ROUTES=
MTU=1420
"""

WG_CONFIG = """# Install-time placeholder only. Keep mode 0600.
# Add Interface/Peer data locally on the router, then set ENABLE=1.
"""

COMMON = r'''#!/bin/sh
BASE=/opt/sr1010-net-runtime
STATE=$BASE/state
ENV=$BASE/config/runtime.env
mkdir -p "$STATE"

write_status() {
    tmp="$STATE/status.tmp"
    {
        echo "state=$1"
        echo "detail=$2"
        date '+timestamp=%Y-%m-%dT%H:%M:%S%z' 2>/dev/null || true
    } >"$tmp"
    mv "$tmp" "$STATE/status"
}

valid_iface() {
    case "$1" in
        ''|*[!A-Za-z0-9_.-]*|*/*) return 1 ;;
        *) test "${#1}" -le 15 ;;
    esac
}

load_env() {
    test -f "$ENV" || { write_status error missing_runtime_env; return 1; }
    # The shipped file contains assignments only and is root-owned package data.
    . "$ENV"
    valid_iface "$INTERFACE" || { write_status error invalid_interface; return 1; }
}

managed_pid() {
    test -s "$STATE/wireguard-go.pid" || return 1
    pid=$(cat "$STATE/wireguard-go.pid")
    test -d "/proc/$pid" || return 1
    exe=$(readlink "/proc/$pid/exe" 2>/dev/null || true)
    test "$exe" = "$BASE/bin/wireguard-go"
}

remove_iface() {
    iface=$1
    ip link show dev "$iface" >/dev/null 2>&1 || return 0
    ip link delete dev "$iface"
}
'''

STOP = r'''#!/bin/sh
set -u
BASE=/opt/sr1010-net-runtime
. "$BASE/lib/common.sh"
load_env || exit 1
rc=0
if managed_pid; then
    kill "$pid" 2>/dev/null || rc=1
    n=0
    while kill -0 "$pid" 2>/dev/null && test "$n" -lt 20; do
        sleep 1; n=$((n + 1))
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
fi
rm -f "$STATE/wireguard-go.pid"
remove_iface "$INTERFACE" || rc=1
rm -f "/var/run/wireguard/$INTERFACE.sock"
if test "$rc" -eq 0; then write_status stopped clean; else write_status error stop_cleanup_failed; fi
exit "$rc"
'''

START = r'''#!/bin/sh
set -u
BASE=/opt/sr1010-net-runtime
. "$BASE/lib/common.sh"
load_env || exit 1

if test "${ENABLE:-0}" != 1; then
    write_status disabled enable_is_zero
    exit 0
fi
test -c /dev/net/tun || { write_status error tun_missing; exit 1; }
test -s "$CONFIG" || { write_status error config_missing_or_empty; exit 1; }
mode=$(stat -c '%a' "$CONFIG" 2>/dev/null || echo unknown)
test "$mode" = 600 || { write_status error config_mode_must_be_600; exit 1; }

if ip link show dev "$INTERFACE" >/dev/null 2>&1; then
    if managed_pid && "$BASE/bin/wg" show "$INTERFACE" >/dev/null 2>&1; then
        write_status running already_started
        exit 0
    fi
    write_status error unmanaged_interface_exists
    exit 1
fi

rollback=1
trap 'test "$rollback" = 0 || "$BASE/stop.sh" >/dev/null 2>&1 || true' EXIT HUP INT TERM
WG_PROCESS_FOREGROUND=1 "$BASE/bin/wireguard-go" -f "$INTERFACE" \
    </dev/null >>"$STATE/wireguard-go.log" 2>&1 &
echo $! >"$STATE/wireguard-go.pid"

n=0
while ! "$BASE/bin/wg" show "$INTERFACE" >/dev/null 2>&1; do
    n=$((n + 1)); test "$n" -lt 10 || { write_status error interface_timeout; exit 1; }
    sleep 1
done
"$BASE/bin/wg" setconf "$INTERFACE" "$CONFIG" || { write_status error setconf_failed; exit 1; }
ip link set mtu "${MTU:-1420}" dev "$INTERFACE" || { write_status error mtu_failed; exit 1; }
test -z "${ADDRESS:-}" || ip address add "$ADDRESS" dev "$INTERFACE" || { write_status error address_failed; exit 1; }
ip link set dev "$INTERFACE" up || { write_status error link_up_failed; exit 1; }
for route in ${ROUTES:-}; do
    ip route add "$route" dev "$INTERFACE" || { write_status error route_failed; exit 1; }
done
rollback=0
write_status running configured
exit 0
'''

HEALTH = r'''#!/bin/sh
BASE=/opt/sr1010-net-runtime
. "$BASE/lib/common.sh"
load_env || exit 1
echo "package=sr1010-net-runtime"
echo "enabled=${ENABLE:-0}"
echo "interface=$INTERFACE"
test -c /dev/net/tun && echo "tun=yes" || echo "tun=no"
"$BASE/bin/wg" --version 2>/dev/null || exit 1
"$BASE/bin/wireguard-go" --version 2>/dev/null || exit 1
if test -f "$STATE/status"; then cat "$STATE/status"; else echo "state=never_started"; fi
'''

SELFTEST = r'''#!/bin/sh
set -u
BASE=/opt/sr1010-net-runtime
. "$BASE/lib/common.sh"
TEST_IF=wg-nrt-test
PIDFILE=$STATE/selftest.pid
cleanup() {
    if test -s "$PIDFILE"; then
        p=$(cat "$PIDFILE"); kill "$p" 2>/dev/null || true; rm -f "$PIDFILE"
    fi
    remove_iface "$TEST_IF" >/dev/null 2>&1 || true
    rm -f "/var/run/wireguard/$TEST_IF.sock"
}
trap cleanup EXIT HUP INT TERM

"$BASE/bin/wg" --version || exit 1
"$BASE/bin/wireguard-go" --version || exit 1
test -c /dev/net/tun || exit 1
test "${1:-}" = --tun || { echo 'selftest=tools_and_tun_ok'; exit 0; }
ip link show dev "$TEST_IF" >/dev/null 2>&1 && { echo 'selftest=interface_already_exists'; exit 1; }
WG_PROCESS_FOREGROUND=1 "$BASE/bin/wireguard-go" -f "$TEST_IF" </dev/null >"$STATE/selftest.log" 2>&1 &
echo $! >"$PIDFILE"
n=0
while ! "$BASE/bin/wg" show "$TEST_IF" >/dev/null 2>&1; do
    n=$((n + 1)); test "$n" -lt 10 || exit 1; sleep 1
done
if ip addr show dev "$TEST_IF" | grep -q 'inet '; then
    echo 'selftest=unexpected_address'; exit 1
fi
echo 'selftest=tun_created_without_address'
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


def build(output: Path, wireguard_go: Path, wg: Path):
    control = tgz([("control", CONTROL, 0o644, False)])
    dirs = [
        "opt/", "opt/sr1010-net-runtime/", "opt/sr1010-net-runtime/bin/",
        "opt/sr1010-net-runtime/config/", "opt/sr1010-net-runtime/lib/",
        "opt/sr1010-net-runtime/state/",
    ]
    entries = [(d, None, 0o755 if not d.endswith("config/") else 0o700, True) for d in dirs]
    entries += [
        ("opt/sr1010-net-runtime/bin/wireguard-go", wireguard_go.read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/bin/wg", wg.read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/config/runtime.env", RUNTIME_ENV, 0o600, False),
        ("opt/sr1010-net-runtime/config/wg0.conf", WG_CONFIG, 0o600, False),
        ("opt/sr1010-net-runtime/lib/common.sh", COMMON, 0o755, False),
        ("opt/sr1010-net-runtime/start.sh", START, 0o755, False),
        ("opt/sr1010-net-runtime/stop.sh", STOP, 0o755, False),
        ("opt/sr1010-net-runtime/health.sh", HEALTH, 0o755, False),
        ("opt/sr1010-net-runtime/selftest.sh", SELFTEST, 0o755, False),
    ]
    data = tgz(entries)
    outer = tgz([
        ("debian-binary", b"2.0\n", 0o644, False),
        ("control.tar.gz", control, 0o644, False),
        ("data.tar.gz", data, 0o644, False),
    ])
    output.write_bytes(outer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wireguard_go", type=Path)
    ap.add_argument("wg", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    for item in (args.wireguard_go, args.wg):
        if not item.is_file():
            ap.error(f"missing binary: {item}")
    build(args.output, args.wireguard_go, args.wg)
    print(args.output)


if __name__ == "__main__":
    main()
