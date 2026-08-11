#!/bin/sh
BASE=/opt/sr1010-net-runtime
WG=$BASE/bin/wg
IFACE=wg-nrt0
STATE=$BASE/state
mkdir -p "$STATE"
port=$($WG show "$IFACE" listen-port 2>/dev/null || echo 0)
peers=$($WG show "$IFACE" peers 2>/dev/null | wc -l | tr -d " ")
latest=$($WG show "$IFACE" latest-handshakes 2>/dev/null | awk 'max<$2{max=$2}END{print max+0}')
rx=$($WG show "$IFACE" transfer 2>/dev/null | awk '{sum+=$2}END{print sum+0}')
tx=$($WG show "$IFACE" transfer 2>/dev/null | awk '{sum+=$3}END{print sum+0}')
test "$port" -gt 0 2>/dev/null && running=true || running=false
printf '{"running":%s,"interface":"%s","listen_port":%s,"peer_count":%s,"latest_handshake":%s,"rx_bytes":%s,"tx_bytes":%s}\n' "$running" "$IFACE" "${port:-0}" "${peers:-0}" "${latest:-0}" "${rx:-0}" "${tx:-0}" >"$STATE/dashboard.json.tmp"
mv "$STATE/dashboard.json.tmp" "$STATE/dashboard.json"
