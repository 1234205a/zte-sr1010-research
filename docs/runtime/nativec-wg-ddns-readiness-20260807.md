# SR1010 nativeC运行WireGuard与DDNS只读盘点

日期：2026-08-07

## 结论

WireGuard可以实现，但当前固件没有`wg/wg-quick`，也没有发现内核WireGuard模块或可加载
`.ko`。可行路线是把ARM32静态`wireguard-go`和`wg`随插件一起安装，利用现成
`/dev/net/tun`。Cloudflare DDNS更简单，现有curl已经支持HTTPS和IPv6，只需随插件携带CA
证书包并使用`--cacert`。

## nativeC与网络命名空间

`pluginmgr`运行在`/lxc.payload/nativeC`，实测：

```text
host netns    = net:[4026531898]
nativeC netns = net:[4026531898]
host mntns    != nativeC mntns
```

也就是说nativeC有独立文件系统视图，但与宿主共享网络命名空间。插件创建的TUN接口、路由
和iptables规则会直接作用于路由器真实网络，不需要额外容器NAT；相应地，启动/停止脚本必须
精确回滚自己添加的规则。

## WireGuard条件

- 内核：Linux 5.4.196，aarch64；
- 用户空间主体：ARM32 EABI/glibc 2.26，内核提供32位兼容；
- `/dev/net/tun`存在，字符设备`10:200`，权限0666；
- 未加载`wireguard`模块，固件目录未发现wireguard/tun/udp_tunnel/curve25519模块；
- BusyBox 1.35的`ip`只支持address/route/link set/tunnel，不支持`ip link add type wireguard`；
- 没有`wg`或`wg-quick`；
- iptables/ip6tables 1.4.13可用。

因此应使用：

```text
wireguard-go wg0
wg setconf wg0 CONFIG
ip address add ... dev wg0
ip route add ... dev wg0
```

其中`ip`负责地址和路由，接口本身由wireguard-go通过TUN创建。为匹配现有nativeC，优先构建
静态ARMv7/GOARM=7二进制，而不是依赖新的动态glibc。

## Cloudflare DDNS条件

nativeC已有：

```text
curl 7.59.0
OpenSSL 1.1.1c
HTTPS / IPv6 / AsynchDNS
wget, nslookup, crond, flock, logger
```

DNS当前有两个解析器。文件树未找到CA bundle，因此插件必须携带自己的`cacert.pem`，否则
不应依赖`-k/--insecure`。Cloudflare TOKEN、zone和record ID继续只放加密保险箱或设备权限
受限配置，不进入Git。

## 资源

```text
/Plugin 总计约40MiB，可用约38.8MiB
MemTotal约446MiB
MemAvailable约327MiB
```

空间足以放置压缩后的wireguard-go、wg、CA包及少量日志。日志需要轮转，且二进制应去符号
和压缩评估，避免挤占JFFS2。

## 当前状态与下一步

本轮只读取设备状态，没有创建接口、发起DDNS请求、修改iptables/路由、启用插件或重启。
下一步可以离线制作一个`net-runtime`插件骨架：先只包含环境自检、配置权限检查和dry-run，
不携带真实密钥，也不接管现有WireGuard。

只读复查脚本：

```sh
sh tools/nativec-readiness-audit.sh
```
