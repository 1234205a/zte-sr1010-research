#!/bin/sh
set -u
BASE=/opt/sr1010-ont-access
STATE=$BASE/state
L2_IF=eth0
WAN_IF=ppp0
LAN_IF=br0
ONT_IP=192.168.100.1
LOCAL_IP=192.168.100.3
WEB_LISTEN=192.168.50.1:8088
TELNET_LISTEN=192.168.50.1:8023
mkdir -p "$STATE"

write_status() {
    {
        echo "state=$1"
        echo "detail=$2"
        date '+timestamp=%Y-%m-%dT%H:%M:%S%z' 2>/dev/null || true
    } >"$STATE/status.tmp"
    mv "$STATE/status.tmp" "$STATE/status"
}

managed_pid() {
    test -s "$STATE/$1.pid" || return 1
    pid=$(cat "$STATE/$1.pid")
    test -d "/proc/$pid" || return 1
    test "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$BASE/bin/ont-forwarder"
}

ensure_rule() {
    table=$1 chain=$2
    shift 2
    iptables -t "$table" -C "$chain" "$@" >/dev/null 2>&1 ||
        iptables -t "$table" -I "$chain" 1 "$@"
}

ensure_network() {
    ip link show dev "$L2_IF" >/dev/null 2>&1 || return 1
    if ! ip addr show dev "$L2_IF" | grep -q "inet $LOCAL_IP/32"; then
        ip addr add "$LOCAL_IP/32" dev "$L2_IF" || return 1
        touch "$STATE/address.owned"
    fi
    route=$(ip route show "$ONT_IP/32")
    case "$route" in
        '') ip route add "$ONT_IP/32" dev "$L2_IF" src "$LOCAL_IP" || return 1; touch "$STATE/route.owned" ;;
        "$ONT_IP dev $L2_IF"*) ;;
        *) return 1 ;;
    esac
    ensure_rule nat POSTROUTING -s "$ONT_IP/32" -o "$WAN_IF" -j MASQUERADE || return 1
    ensure_rule filter FORWARD -i "$L2_IF" -o "$WAN_IF" -s "$ONT_IP/32" -j ACCEPT || return 1
    ensure_rule filter FORWARD -i "$WAN_IF" -o "$L2_IF" -d "$ONT_IP/32" -m state --state RELATED,ESTABLISHED -j ACCEPT || return 1
    ensure_rule filter INPUT -i "$LAN_IF" -d 192.168.50.1 -p tcp --dport 8088 -j ACCEPT || return 1
    ensure_rule filter INPUT -i "$LAN_IF" -d 192.168.50.1 -p tcp --dport 8023 -j ACCEPT || return 1
}

start_forwarder() {
    name=$1 listen=$2 upstream=$3 max_lifetime=$4
    if managed_pid "$name"; then return 0; fi
    rm -f "$STATE/$name.pid"
    "$BASE/bin/ont-forwarder" -listen "$listen" -upstream "$upstream" -max-lifetime "$max_lifetime" >>"$STATE/$name.log" 2>&1 &
    echo $! >"$STATE/$name.pid"
    n=0
    while ! managed_pid "$name"; do
        n=$((n + 1))
        test "$n" -lt 10 || return 1
        sleep 1
    done
}

if ! ensure_network; then
    write_status error network_setup_failed
    "$BASE/stop.sh" >/dev/null 2>&1 || true
    exit 1
fi
if ! start_forwarder web "$WEB_LISTEN" "$ONT_IP:80" 2m ||
   ! start_forwarder telnet "$TELNET_LISTEN" "$ONT_IP:23" 15m; then
    write_status error forwarder_start_failed
    "$BASE/stop.sh" >/dev/null 2>&1 || true
    exit 1
fi
write_status running configured
exit 0
