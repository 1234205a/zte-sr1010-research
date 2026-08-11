#!/usr/bin/env python3
"""构建不改网络、不监听端口的nativeC状态采集插件。"""
import argparse, gzip, io, tarfile
from pathlib import Path

CONTROL = """Package: sr1010-net-status
Version: 0.1.0
Architecture: all
Maintainer: local
Description: read-only SR1010 network runtime status collector
StartCMD: /opt/sr1010-net-status/start.sh
StopCMD: /opt/sr1010-net-status/stop.sh
StartMode: 0
"""

COLLECT = r'''#!/bin/sh
BASE=/opt/sr1010-net-status
STATE=$BASE/state
mkdir -p "$STATE"
now=$(date '+%Y-%m-%dT%H:%M:%S%z' 2>/dev/null || echo unknown)
wg_tool=no; command -v wg >/dev/null 2>&1 && wg_tool=yes
wg_iface=no; grep -q 'wg0:' /proc/net/dev 2>/dev/null && wg_iface=yes
tun=no; test -c /dev/net/tun && tun=yes
route=$(ip route 2>/dev/null | grep '^default ' | sed -n '1p')
mem=$(grep '^MemAvailable:' /proc/meminfo 2>/dev/null | awk '{print $2}')
test -n "$mem" || mem=unknown
tmp="$STATE/status.json.tmp"
cat >"$tmp" <<EOF
{"timestamp":"$now","tun":"$tun","wg_tool":"$wg_tool","wg0":"$wg_iface","mem_available_kb":"$mem","default_route_present":"$(test -n "$route" && echo yes || echo no)","ddns":"not_configured"}
EOF
mv "$tmp" "$STATE/status.json"
exit 0
'''

START = r'''#!/bin/sh
BASE=/opt/sr1010-net-status
STATE=$BASE/state
mkdir -p "$STATE"
test -f "$STATE/collector.pid" && kill -0 "$(cat "$STATE/collector.pid")" 2>/dev/null && exit 0
(
  while :; do
    "$BASE/collect.sh"
    sleep 60
  done
) </dev/null >/dev/null 2>&1 &
echo $! >"$STATE/collector.pid"
exit 0
'''

STOP = r'''#!/bin/sh
PID=/opt/sr1010-net-status/state/collector.pid
if test -f "$PID"; then
  kill "$(cat "$PID")" 2>/dev/null || true
  rm -f "$PID"
fi
exit 0
'''

HEALTH = r'''#!/bin/sh
BASE=/opt/sr1010-net-status
"$BASE/collect.sh"
cat "$BASE/state/status.json"
'''

PANEL = '''<!doctype html><meta charset="utf-8"><title>SR1010 Status</title>
<style>body{font:16px system-ui;background:#111827;color:#e5e7eb;margin:2rem}main{max-width:720px;margin:auto}pre{background:#1f2937;padding:1rem;border-radius:12px;white-space:pre-wrap}.ok{color:#34d399}</style>
<main><h1>SR1010 网络状态</h1><p>只读原型；不会修改路由或防火墙。</p><pre id="out">读取中…</pre></main>
<script>fetch('state/status.json',{cache:'no-store'}).then(r=>r.json()).then(x=>{out.textContent=JSON.stringify(x,null,2);out.className='ok'}).catch(e=>out.textContent='状态文件不可用：'+e)</script>'''

def tgz(entries):
    raw=io.BytesIO()
    with gzip.GzipFile(fileobj=raw,mode="wb",mtime=0) as gz:
        with tarfile.open(fileobj=gz,mode="w",format=tarfile.GNU_FORMAT) as tf:
            for name,body,mode,kind in entries:
                info=tarfile.TarInfo(name); info.mtime=info.uid=info.gid=0; info.uname=info.gname="root"; info.mode=mode
                if kind=="dir": info.type=tarfile.DIRTYPE; info.size=0; tf.addfile(info)
                else:
                    data=body.encode(); info.size=len(data); tf.addfile(info,io.BytesIO(data))
    return raw.getvalue()

def build(out):
    control=tgz([("control",CONTROL,0o644,"file")])
    data=tgz([
        ("opt/",None,0o755,"dir"),("opt/sr1010-net-status/",None,0o755,"dir"),
        ("opt/sr1010-net-status/state/",None,0o755,"dir"),
        ("opt/sr1010-net-status/start.sh",START,0o755,"file"),
        ("opt/sr1010-net-status/stop.sh",STOP,0o755,"file"),
        ("opt/sr1010-net-status/collect.sh",COLLECT,0o755,"file"),
        ("opt/sr1010-net-status/health.sh",HEALTH,0o755,"file"),
        ("opt/sr1010-net-status/panel.html",PANEL,0o644,"file")])
    # 外层成员包含二进制tar.gz，直接写入。
    raw=io.BytesIO()
    with gzip.GzipFile(fileobj=raw,mode="wb",mtime=0) as gz:
        with tarfile.open(fileobj=gz,mode="w",format=tarfile.GNU_FORMAT) as tf:
            for name,blob,mode in [("debian-binary",b"2.0\n",0o644),("control.tar.gz",control,0o644),("data.tar.gz",data,0o644)]:
                i=tarfile.TarInfo(name);i.size=len(blob);i.mode=mode;i.mtime=i.uid=i.gid=0;i.uname=i.gname="root";tf.addfile(i,io.BytesIO(blob))
    out.write_bytes(raw.getvalue())

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("output",nargs="?",type=Path,default=Path("sr1010-net-status_0.1.0_all.ipk"));a=ap.parse_args();build(a.output);print(a.output)
