# SR1010 WireGuard 整机重启持久化验证（2026-08-07）

## 操作

在用户明确授权后执行一次 SR1010 整机重启。Telnet 端口约在 2 秒后离线，约 55 秒后重新上线。

## 重启后结果

启动约 94 秒时检查：

```text
nativeC=RUNNING
wg-nrt0=present
UDP 51888=listen
WAN UDP 51888 rule=present
WG to LAN rule=present
net.ipv4.ip_forward=1
state=running
detail=configured
PluginInfo Enable=1
PluginInfo Status=2
PluginInfo StartMode=0
```

这确认密钥配置、WireGuard 用户态进程、接口地址、监听端口、IPv4 forwarding 与防火墙规则都由 Plugin Manager 在真实整机启动后自动恢复。

## DDNS

Cloudflare DDNS 同样在重启后恢复：

```text
package=sr1010-cf-ddns
loop=running
last_ip=PUBLIC_IP_B
```

## 客户端状态

检查时客户端尚未重新握手，服务端 handshake/transfer 计数为 0。这表示手机当时没有向新启动的服务端发包，不影响服务端持久化结论。手机重新开启隧道或触发流量后应建立新握手。

## 结论

SR1010 的 WireGuard 服务端和 Cloudflare DDNS 已通过真实重启持久化验证。现有 Asus 与 NAS 配置未修改。
