#!/bin/sh
set -u
BASE=/opt/sr1010-net-runtime
. "$BASE/lib/common.sh"
load_env || exit 1
PORT=51888
LAN_IF=br0
LAN_NET=192.168.50.0/24
WAN_IF=ppp0
ensure_rule() { chain=$1; shift; iptables -C "$chain" "$@" >/dev/null 2>&1 || iptables -I "$chain" 1 "$@"; }
ensure_firewall() {
    test -f "$STATE/ip_forward.previous" || cat /proc/sys/net/ipv4/ip_forward >"$STATE/ip_forward.previous"
    echo 1 >/proc/sys/net/ipv4/ip_forward
    ensure_rule INPUT -i "$WAN_IF" -p udp --dport "$PORT" -j ACCEPT
    ensure_rule FORWARD -i "$INTERFACE" -o "$LAN_IF" -d "$LAN_NET" -j ACCEPT
    ensure_rule FORWARD -i "$LAN_IF" -o "$INTERFACE" -s "$LAN_NET" -m state --state RELATED,ESTABLISHED -j ACCEPT
}
if test "${ENABLE:-0}" != 1; then write_status disabled enable_is_zero; exit 0; fi
test -c /dev/net/tun || { write_status error tun_missing; exit 1; }
test -s "$CONFIG" || { write_status error config_missing_or_empty; exit 1; }
mode=$(stat -c '%a' "$CONFIG" 2>/dev/null || echo unknown)
test "$mode" = 600 || { write_status error config_mode_must_be_600; exit 1; }
if ip link show dev "$INTERFACE" >/dev/null 2>&1; then
    if managed_pid && "$BASE/bin/wg" show "$INTERFACE" >/dev/null 2>&1; then ensure_firewall || { write_status error firewall_failed; exit 1; }; "$BASE/dashboard-start.sh" >/dev/null 2>&1 || true; write_status running already_started; exit 0; fi
    write_status error unmanaged_interface_exists; exit 1
fi
rollback=1
trap 'test "$rollback" = 0 || "$BASE/stop.sh" >/dev/null 2>&1 || true' EXIT HUP INT TERM
WG_PROCESS_FOREGROUND=1 "$BASE/bin/wireguard-go" -f "$INTERFACE" </dev/null >>"$STATE/wireguard-go.log" 2>&1 &
echo $! >"$STATE/wireguard-go.pid"
n=0
while ! "$BASE/bin/wg" show "$INTERFACE" >/dev/null 2>&1; do n=$((n+1)); test "$n" -lt 10 || { write_status error interface_timeout; exit 1; }; sleep 1; done
"$BASE/bin/wg" setconf "$INTERFACE" "$CONFIG" || { write_status error setconf_failed; exit 1; }
ip link set mtu "${MTU:-1420}" dev "$INTERFACE" || { write_status error mtu_failed; exit 1; }
test -z "${ADDRESS:-}" || ip address add "$ADDRESS" dev "$INTERFACE" || { write_status error address_failed; exit 1; }
ip link set dev "$INTERFACE" up || { write_status error link_up_failed; exit 1; }
for route in ${ROUTES:-}; do ip route add "$route" dev "$INTERFACE" || { write_status error route_failed; exit 1; }; done
ensure_firewall || { write_status error firewall_failed; exit 1; }
"$BASE/dashboard-start.sh" >/dev/null 2>&1 || true
rollback=0
write_status running configured
exit 0
