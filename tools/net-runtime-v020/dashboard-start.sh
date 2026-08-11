#!/bin/sh
BASE=/opt/sr1010-net-runtime
STATE=$BASE/state
mkdir -p "$STATE"

if test -s "$STATE/dashboard.pid"; then
    kill "$(cat "$STATE/dashboard.pid")" 2>/dev/null || true
    rm -f "$STATE/dashboard.pid"
fi

if ! test -s "$STATE/dashboard-collector.pid" || ! kill -0 "$(cat "$STATE/dashboard-collector.pid")" 2>/dev/null; then
    "$BASE/dashboard-loop.sh" </dev/null >>"$STATE/dashboard-collector.log" 2>&1 &
    echo $! >"$STATE/dashboard-collector.pid"
fi

start_panel() {
    name=$1
    listen=$2
    pidfile="$STATE/dashboard-$name.pid"
    if ! test -s "$pidfile" || ! kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        DASHBOARD_LISTEN="$listen" "$BASE/bin/dashboard" </dev/null >>"$STATE/dashboard-$name.log" 2>&1 &
        echo $! >"$pidfile"
    fi
}

start_panel wg 10.77.0.1:51889
start_panel lan 192.168.50.1:51889
