#!/bin/sh
set -u
BASE=/opt/sr1010-ont-access
STATE=$BASE/state
L2_IF=eth0
WAN_IF=ppp0
LAN_IF=br0
ONT_IP=192.168.100.1
LOCAL_IP=192.168.100.3

managed_pid() {
    test -s "$STATE/$1.pid" || return 1
    pid=$(cat "$STATE/$1.pid")
    test -d "/proc/$pid" || return 1
    test "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$BASE/bin/ont-forwarder"
}

for name in web telnet; do
    if managed_pid "$name"; then
        kill "$pid" 2>/dev/null || true
        n=0
        while kill -0 "$pid" 2>/dev/null && test "$n" -lt 5; do n=$((n + 1)); sleep 1; done
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$STATE/$name.pid"
done
iptables -t nat -D POSTROUTING -s "$ONT_IP/32" -o "$WAN_IF" -j MASQUERADE >/dev/null 2>&1 || true
iptables -D FORWARD -i "$L2_IF" -o "$WAN_IF" -s "$ONT_IP/32" -j ACCEPT >/dev/null 2>&1 || true
iptables -D FORWARD -i "$WAN_IF" -o "$L2_IF" -d "$ONT_IP/32" -m state --state RELATED,ESTABLISHED -j ACCEPT >/dev/null 2>&1 || true
iptables -D INPUT -i "$LAN_IF" -d 192.168.50.1 -p tcp --dport 8088 -j ACCEPT >/dev/null 2>&1 || true
iptables -D INPUT -i "$LAN_IF" -d 192.168.50.1 -p tcp --dport 8023 -j ACCEPT >/dev/null 2>&1 || true
if test -f "$STATE/route.owned"; then
    ip route del "$ONT_IP/32" dev "$L2_IF" >/dev/null 2>&1 || true
    rm -f "$STATE/route.owned"
fi
if test -f "$STATE/address.owned"; then
    ip addr del "$LOCAL_IP/32" dev "$L2_IF" >/dev/null 2>&1 || true
    rm -f "$STATE/address.owned"
fi
echo 'state=stopped' >"$STATE/status"
echo 'detail=clean' >>"$STATE/status"
exit 0
