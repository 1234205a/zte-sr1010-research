#!/bin/sh
BASE=/opt/sr1010-net-runtime
. "$BASE/lib/common.sh"
load_env || exit 1
fail=0
check() { if "$@"; then echo "PASS $*"; else echo "FAIL $*"; fail=1; fi; }
check test -x "$BASE/start.sh"
check test -x "$BASE/stop.sh"
check test -x "$BASE/backup.sh"
check test -x "$BASE/restore.sh"
check test -x "$BASE/token-ensure.sh"
check test -s "$CONFIG"
check test "$(stat -c '%a' "$CONFIG" 2>/dev/null)" = 600
check test "$(stat -c '%a' "$ENV" 2>/dev/null)" = 600
check test -s "$BASE/config/dashboard.token"
check test "$(stat -c '%a' "$BASE/config/dashboard.token" 2>/dev/null)" = 600
check ip link show dev "$INTERFACE"
check "$BASE/bin/wg" show "$INTERFACE"
check iptables -C INPUT -i ppp0 -p udp --dport 51888 -j ACCEPT
check iptables -C FORWARD -i "$INTERFACE" -o br0 -d 192.168.50.0/24 -j ACCEPT
check test -s "$STATE/dashboard-wg.pid"
check test -s "$STATE/dashboard-lan.pid"
exit "$fail"

