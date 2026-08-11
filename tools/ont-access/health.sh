#!/bin/sh
BASE=/opt/sr1010-ont-access
STATE=$BASE/state
echo 'package=sr1010-ont-access'
test -f "$STATE/status" && cat "$STATE/status" || echo 'state=never_started'
for name in web telnet; do
    pid=
    test ! -s "$STATE/$name.pid" || pid=$(cat "$STATE/$name.pid")
    if test -n "$pid" && test -d "/proc/$pid" &&
       test "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$BASE/bin/ont-forwarder"; then
        echo "$name=running"
    else
        echo "$name=stopped"
    fi
done
ip addr show dev eth0 2>/dev/null | grep -q 'inet 192.168.100.3/32' && echo 'address=present' || echo 'address=missing'
ip route show 192.168.100.1/32 2>/dev/null | grep -q 'dev eth0' && echo 'route=present' || echo 'route=missing'
if wget -q -T 4 -O /dev/null http://192.168.50.1:8088/login.htm; then
    echo 'ont_web=reachable'
else
    echo 'ont_web=unreachable'
fi
