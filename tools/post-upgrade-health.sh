#!/bin/sh
set -u
MODE=${1:-check}
test "$MODE" = check || test "$MODE" = apply || { echo usage_check_or_apply >&2; exit 2; }
fail=0
say(){ echo "$1 $2"; }
ensure_service(){
 name=$1; base=$2; probe=$3
 if ! test -x "$base/start.sh"; then say FAIL "$name missing"; fail=1; return; fi
 if sh -c "$probe"; then say PASS "$name running"; return; fi
 if test "$MODE" = apply && "$base/start.sh" >/dev/null 2>&1 && sh -c "$probe"; then say FIXED "$name restarted"; return; fi
 say FAIL "$name stopped"; fail=1
}
WG=/opt/sr1010-net-runtime
DDNS=/opt/sr1010-cf-ddns
if test -f "$WG/config/runtime.env"; then
 chmod 600 "$WG/config/runtime.env" "$WG/config/wg0.conf" 2>/dev/null || true
 ensure_service wireguard "$WG" 'ip link show dev wg-nrt0 >/dev/null 2>&1 && /opt/sr1010-net-runtime/bin/wg show wg-nrt0 >/dev/null 2>&1'
else
 say FAIL 'wireguard config missing'; fail=1
fi
if test -f "$DDNS/config/ddns.env" && test -f "$DDNS/config/curl-auth.conf"; then
 chmod 600 "$DDNS/config/ddns.env" "$DDNS/config/curl-auth.conf" 2>/dev/null || true
 ensure_service ddns "$DDNS" 'test "$(/opt/sr1010-cf-ddns/health.sh 2>/dev/null | grep "^loop=running$")" = "loop=running"'
else
 say FAIL 'ddns config missing'; fail=1
fi
test "$fail" -eq 0 && echo result=PASS || echo result=FAIL
exit "$fail"
