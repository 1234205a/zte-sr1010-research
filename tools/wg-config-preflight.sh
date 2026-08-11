#!/bin/sh
# Run inside nativeC. Loads a staged config without adding addresses or routes.
set -u

BASE=${BASE:-/opt/sr1010-net-runtime}
CONFIG=${1:-}
IFACE=wg-import-test
PID=

cleanup() {
    test -n "$PID" && kill "$PID" 2>/dev/null || true
    ip link delete dev "$IFACE" 2>/dev/null || true
    rm -f "/var/run/wireguard/$IFACE.sock"
}
trap cleanup EXIT HUP INT TERM

test -n "$CONFIG" && test -f "$CONFIG" || {
    echo "result=FAIL detail=missing_config"
    exit 1
}
mode=$(stat -c '%a' "$CONFIG" 2>/dev/null || echo unknown)
test "$mode" = 600 || {
    echo "result=FAIL detail=config_mode_must_be_600"
    exit 1
}
test -x "$BASE/bin/wireguard-go" && test -x "$BASE/bin/wg" || {
    echo "result=FAIL detail=runtime_missing"
    exit 1
}
test -c /dev/net/tun || {
    echo "result=FAIL detail=tun_missing"
    exit 1
}
ip link show dev "$IFACE" >/dev/null 2>&1 && {
    echo "result=FAIL detail=test_interface_exists"
    exit 1
}

WG_PROCESS_FOREGROUND=1 "$BASE/bin/wireguard-go" -f "$IFACE" \
    </dev/null >"$BASE/state/import-preflight.log" 2>&1 &
PID=$!
n=0
while ! "$BASE/bin/wg" show "$IFACE" >/dev/null 2>&1; do
    n=$((n + 1))
    test "$n" -lt 10 || {
        echo "result=FAIL detail=interface_timeout"
        exit 1
    }
    sleep 1
done

"$BASE/bin/wg" setconf "$IFACE" "$CONFIG" || {
    echo "result=FAIL detail=setconf_failed"
    exit 1
}
if ip addr show dev "$IFACE" | grep -E -q 'inet6? '; then
    echo "result=FAIL detail=unexpected_address"
    exit 1
fi

peers=$("$BASE/bin/wg" show "$IFACE" peers | wc -w)
port=$("$BASE/bin/wg" show "$IFACE" listen-port)
echo "result=PASS"
echo "mode=$mode"
echo "listen_port=$port"
echo "peer_count=$peers"
echo "address=none"
echo "routes_added=none"

