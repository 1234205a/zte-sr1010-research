# SR1010 WireGuard 开机自启动预检（2026-08-07）

## 结果

`sr1010-net-runtime` 已通过正式 Plugin Manager 事务启用：

```text
Enable=1
Status=2
StartMode=0
StartCMD=/bin/sh /opt/sr1010-net-runtime/start.sh
StopCMD=/bin/sh /opt/sr1010-net-runtime/stop.sh
```

## 无重启启停回放

先经正式 Enable 事务执行禁用，再重新启用：

- 禁用后 `wg-nrt0` 消失，UDP 51888 防火墙规则被清理；
- 启用后 `wg-nrt0`、UDP 51888、IPv4 forwarding 和一个 Peer 全部恢复；
- 状态为 `running/configured`。

## 开机事件模拟

在数据库保持 `Enable=1` 的条件下，直接停止运行时，再向 Plugin Manager 重放开机使用的 `StartupMsg 0x1103`。同步发送工具返回 `-1` 是该事件没有同步应答的既知行为；异步处理结果为：

```text
wg-nrt0: present
UDP 51888 rule: present
state=running
detail=configured
listen-port=51888
```

这证明 `PluginAutoStart -> LXCPcStartProgram -> nativeC -> start.sh` 在当前安装状态下闭环成功。实际整机重启仍是最终验证，但本轮未重启路由器。

## 当前在线状态

- WireGuard 服务已恢复运行；
- Plugin Manager 持久字段已保存为 Enable=1；
- Cloudflare DDNS 仍为 Enable=1；
- 现有 Asus/NAS 配置未修改。
