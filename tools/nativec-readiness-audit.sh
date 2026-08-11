#!/bin/sh
# SR1010 nativeC只读能力盘点；不创建接口、不改路由/防火墙。
set -u
echo "kernel=$(uname -r) machine=$(uname -m)"
echo "tun=$(test -c /dev/net/tun && echo yes || echo no)"
echo "wireguard_module=$(grep -q '^wireguard ' /proc/modules && echo loaded || echo absent)"
for x in wg wg-quick ip iptables ip6tables curl wget openssl nslookup crond flock logger; do
    p=$(command -v "$x" 2>/dev/null || true)
    echo "tool.$x=${p:-absent}"
done
if command -v curl >/dev/null 2>&1; then curl -V | sed -n '1,3p'; fi
echo "dns_servers=$(grep '^nameserver' /etc/resolv.conf | wc -l)"
echo "ca_file=$(find /etc -maxdepth 4 -type f 2>/dev/null | grep -E 'ca-bundle|cert.pem|cacert' | sed -n '1p')"
df -k /Plugin 2>/dev/null || true
grep -E 'MemTotal|MemAvailable' /proc/meminfo
