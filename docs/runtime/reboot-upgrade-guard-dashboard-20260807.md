# SR1010 重启持久化、升级保护与管理面板实机闭环（2026-08-07）

## Downloads 整理

已创建 `Downloads/SR1010-Workspace/`：

- `10-firmware/`
- `20-config/`
- `30-recovery/`
- `40-builds/`
- `50-source-dumps/`
- `90-legacy/`

活动目录 `sr1010-dev`、`sr1010_analysis` 与敏感的 `sr1010-wireguard-private` 暂留顶层，避免破坏现有实机脚本路径。没有删除样本。

## 获批重启验证

路由器确实经历离线并在约 63 秒后返回。启动约 98 秒时验证：

```text
sr1010-net-runtime 0.2.1
sr1010-cf-ddns 0.1.1
WireGuard state=running detail=configured
DDNS loop=running
lifecycle audit=13 PASS / 0 FAIL
LAN dashboard=HTTP 200
```

这证明两个插件的文件、配置、原厂登记与自动启动已经跨整机重启保持。

## 任务 1：升级失败保护

`cm-plugin-upgrade-ssend.c` 已增加：

- 只接受两个已知本地插件 ID；
- 在发送 `0x2410` 前检查 URL 是否包含 `scpsign/scptime/key1/key2` 字段名；
- 预检查失败返回 3，不触发原厂升级事务；
- 原厂事务失败时调用对应插件的固定 `start.sh` 恢复服务；
- 不拼接用户输入到恢复命令。

实机用缺少签名字段的 URL 验证：工具在 IPC 前拒绝，WireGuard 始终保持 `running/configured`。

## 任务 2：受保护管理面板

LAN 与 WireGuard 地址上的面板已升级，提供：

- WireGuard 运行状态；
- DDNS 循环状态；
- net-runtime 与 cf-ddns 的 opkg 版本；
- WireGuard/DDNS 配置备份；
- WireGuard 与 DDNS 启动；
- DDNS 停止。

所有修改操作只接受 POST，并要求 `X-SR1010-Token`。管理令牌保存在设备 `0600` 文件和 Vaultwarden 项目 `SR1010 dashboard management token` 中，不进入 Git。浏览器仅在当前 `sessionStorage` 保存用户输入。

实机验证：

```text
GET / = 200
GET /manage.json = 200
未带令牌 POST /action = 401
正确令牌 net-backup = 200
WireGuard running=true
DDNS loop=running
```

旧面板二进制保留为设备本地 `dashboard.pre-v022`，用于一键回滚。临时 NAS HTTP 服务及传输文件已清理。
