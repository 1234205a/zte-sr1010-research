#!/bin/sh
set -u
BASE=/opt/sr1010-net-runtime
. "$BASE/lib/common.sh"
load_env || exit 1
for pf in dashboard.pid dashboard-wg.pid dashboard-lan.pid dashboard-collector.pid; do if test -s "$STATE/$pf"; then kill "$(cat "$STATE/$pf")" 2>/dev/null || true; rm -f "$STATE/$pf"; fi; done
PORT=51888
LAN_IF=br0
LAN_NET=192.168.50.0/24
WAN_IF=ppp0
rc=0
iptables -D INPUT -i "$WAN_IF" -p udp --dport "$PORT" -j ACCEPT >/dev/null 2>&1 || true
iptables -D FORWARD -i "$INTERFACE" -o "$LAN_IF" -d "$LAN_NET" -j ACCEPT >/dev/null 2>&1 || true
iptables -D FORWARD -i "$LAN_IF" -o "$INTERFACE" -s "$LAN_NET" -m state --state RELATED,ESTABLISHED -j ACCEPT >/dev/null 2>&1 || true
if test -s "$STATE/ip_forward.previous"; then cat "$STATE/ip_forward.previous" >/proc/sys/net/ipv4/ip_forward 2>/dev/null || true; rm -f "$STATE/ip_forward.previous"; fi
if managed_pid; then kill "$pid" 2>/dev/null || rc=1; n=0; while kill -0 "$pid" 2>/dev/null && test "$n" -lt 20; do sleep 1; n=$((n+1)); done; kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true; fi
rm -f "$STATE/wireguard-go.pid"
remove_iface "$INTERFACE" || rc=1
rm -f "/var/run/wireguard/$INTERFACE.sock"
if test "$rc" -eq 0; then write_status stopped clean; else write_status error stop_cleanup_failed; fi
exit "$rc"
