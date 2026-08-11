# SR1010 WireGuard 服务端在线里程碑（2026-08-07）

## 结论

SR1010 已直接运行 WireGuard 服务端，并完成手机移动网络实测。无需依赖 Asus 路由器承载该隧道。

## 当前配置

- 接口：`wg-nrt0`
- 隧道地址：服务端 `10.77.0.1/24`，首个客户端 `10.77.0.2/32`
- Endpoint：`sr1010.example.invalid:51888`
- WAN：`ppp0`
- LAN：`br0` / `192.168.50.0/24`
- MTU：`1420`
- 客户端 AllowedIPs：`192.168.50.0/24, 10.77.0.0/24`
- 服务端公钥：`<SERVER_PUBLIC_KEY>`
- 客户端公钥：`<CLIENT_PUBLIC_KEY>`

## 已部署内容

- `/opt/sr1010-net-runtime/config/wg0.conf`，权限 `0600`
- `/opt/sr1010-net-runtime/config/runtime.env`，`ENABLE=1`
- `wireguard-go` 服务与一个客户端 Peer
- WAN UDP 51888 放行
- `wg-nrt0 -> br0` 转发及返回流量规则
- IPv4 forwarding 已开启
- start/stop 脚本会添加、清理规则，并保存/恢复原始 forwarding 状态
- 防火墙规则添加逻辑已经修正为幂等，重复规则已清除

## 在线验证

- 手机经移动网络完成握手
- 服务端识别到公网 UDP Endpoint
- 服务端到 `10.77.0.2`：2/2 成功，0% 丢包
- 往返延迟约 9.6 ms
- UDP 51888 规则计数实际增长
- 修复幂等规则后再次 ping 手机成功

因此 DDNS、公网 UDP、SR1010 防火墙、WireGuard 加密隧道均已贯通。

## 凭据处理

明文客户端配置与加密产物密码保存在 Vaultwarden：`WireGuard/SR1010 WireGuard phone-1`。Git 仅保存 AES-256-GCM 加密客户端配置：

- `sr1010/private-artifacts/phone-1.conf.enc.json`
- SHA-256：`ca6ad7d4fc851cc0154ac8968253a8b1fdd6b9bcec8005552665bffee0820137`
- KDF：PBKDF2-HMAC-SHA256，600000 次迭代

服务端私钥、客户端私钥和 PSK 均不以明文进入 Git。

## 注意

本次未重启路由器。现有 Asus 与 NAS WireGuard 端口及配置未修改，可继续作为回滚路径。
