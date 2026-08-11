#!/usr/bin/env python3
"""Build SR1010 WireGuard runtime 0.2.0 without embedding live secrets."""
import argparse, importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("v010", HERE / "build-net-runtime-ipk.py")
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)

CONTROL = """Package: sr1010-net-runtime
Version: 0.2.0
Architecture: arm
Maintainer: local
Description: persistent WireGuard server and tunnel-only read-only dashboard
StartCMD: /opt/sr1010-net-runtime/start.sh
StopCMD: /opt/sr1010-net-runtime/stop.sh
StartMode: 0
"""

POSTINST = r'''#!/bin/sh
BASE=/opt/sr1010-net-runtime
mkdir -p "$BASE/config" "$BASE/state"
chmod 700 "$BASE/config"
if ! test -f "$BASE/config/runtime.env"; then
cat >"$BASE/config/runtime.env" <<'EOF'
ENABLE=0
INTERFACE=wg-nrt0
CONFIG=/opt/sr1010-net-runtime/config/wg0.conf
ADDRESS=
ROUTES=
MTU=1420
EOF
fi
if ! test -f "$BASE/config/wg0.conf"; then
cat >"$BASE/config/wg0.conf" <<'EOF'
# Add WireGuard Interface/Peer configuration locally before enabling.
EOF
fi
chmod 600 "$BASE/config/runtime.env" "$BASE/config/wg0.conf"
exit 0
'''

PRERM = r'''#!/bin/sh
BASE=/opt/sr1010-net-runtime
test -x "$BASE/backup.sh" && "$BASE/backup.sh" >/dev/null 2>&1 || true
test -x "$BASE/stop.sh" && "$BASE/stop.sh" >/dev/null 2>&1 || true
exit 0
'''

POSTRM = r'''#!/bin/sh
iptables -D INPUT -i ppp0 -p udp --dport 51888 -j ACCEPT >/dev/null 2>&1 || true
iptables -D FORWARD -i wg-nrt0 -o br0 -d 192.168.50.0/24 -j ACCEPT >/dev/null 2>&1 || true
iptables -D FORWARD -i br0 -o wg-nrt0 -s 192.168.50.0/24 -m state --state RELATED,ESTABLISHED -j ACCEPT >/dev/null 2>&1 || true
ip link show dev wg-nrt0 >/dev/null 2>&1 && ip link delete dev wg-nrt0 >/dev/null 2>&1 || true
rm -f /var/run/wireguard/wg-nrt0.sock
exit 0
'''

def build(out, wireguard_go, wg, dashboard):
    control = old.tgz([
        ("control", CONTROL, 0o644, False),
        ("postinst", POSTINST, 0o755, False),
        ("prerm", PRERM, 0o755, False),
        ("postrm", POSTRM, 0o755, False),
    ])
    dirs = ["opt/", "opt/sr1010-net-runtime/", "opt/sr1010-net-runtime/bin/",
            "opt/sr1010-net-runtime/config/", "opt/sr1010-net-runtime/lib/",
            "opt/sr1010-net-runtime/state/"]
    entries = [(d, None, 0o700 if d.endswith("config/") else 0o755, True) for d in dirs]
    entries += [
        ("opt/sr1010-net-runtime/bin/wireguard-go", wireguard_go.read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/bin/wg", wg.read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/bin/dashboard", dashboard.read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/lib/common.sh", old.COMMON, 0o755, False),
        ("opt/sr1010-net-runtime/start.sh", (HERE/"start.sh").read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/stop.sh", (HERE/"stop.sh").read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/health.sh", old.HEALTH, 0o755, False),
        ("opt/sr1010-net-runtime/selftest.sh", old.SELFTEST, 0o755, False),
        ("opt/sr1010-net-runtime/dashboard-collect.sh", (HERE/"dashboard-collect.sh").read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/dashboard-loop.sh", (HERE/"dashboard-loop.sh").read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/dashboard-start.sh", (HERE/"dashboard-start.sh").read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/backup.sh", (HERE/"backup.sh").read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/restore.sh", (HERE/"restore.sh").read_bytes(), 0o755, False),
        ("opt/sr1010-net-runtime/lifecycle-audit.sh", (HERE/"lifecycle-audit.sh").read_bytes(), 0o755, False),
    ]
    data = old.tgz(entries)
    out.write_bytes(old.tgz([
        ("debian-binary", b"2.0\n", 0o644, False),
        ("control.tar.gz", control, 0o644, False),
        ("data.tar.gz", data, 0o644, False),
    ]))

if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("wireguard_go",type=Path);p.add_argument("wg",type=Path);p.add_argument("dashboard",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    build(a.output,a.wireguard_go,a.wg,a.dashboard);print(a.output)
