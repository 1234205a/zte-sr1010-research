# SR1010 网络插件实机升级验证（2026-08-07）

## 结论

已在实机上完成正式升级和运行验证，路由器未重启：

- `sr1010-net-runtime`：`0.2.0` → `0.2.1`
- `sr1010-cf-ddns`：`0.1.0` → `0.1.1`
- WireGuard 接口重新启动后恢复为 `running/configured`
- Cloudflare DDNS 循环保持 `running`
- 生命周期审计：13 PASS、0 FAIL
- LAN 状态面板返回 HTTP 200
- 升级后健康检查与 DDNS 备份恢复校验均为 PASS

## 实机操作

1. 从可信构建产物校验 SHA-256 后，经 NAS 临时 HTTP 服务传入 nativeC `/tmp`。
2. 升级前生成 WireGuard 配置备份，并为旧版 DDNS 手工生成兼容 `backup-v1` 的配置归档。
3. 使用 nativeC 的 `opkg install` 原地升级两个包。
4. 由于运行中的旧 WireGuard 可执行文件在包覆盖后显示为旧映像，首次启动保护正确报告 `unmanaged_interface_exists`；随后执行一次插件级 `stop/start`，没有重启路由器。
5. 升级完成后执行健康检查、生命周期审计、配置权限检查、备份校验及 LAN 面板访问测试。
6. 删除路由器 `/tmp` 中的 IPK，并关闭、清理 NAS 临时传输服务。

## 验证证据（脱敏）

```text
opkg sr1010-net-runtime Version: 0.2.1
opkg sr1010-cf-ddns Version: 0.1.1
net-runtime state=running detail=configured
cf-ddns loop=running
lifecycle audit: pass_count=13 fail_count=0
post-upgrade-health: PASS wireguard running
post-upgrade-health: PASS ddns running
DDNS restore check: result=PASS
LAN dashboard: HTTP 200
runtime.env: 0600
wg0.conf: 0600
ddns.env: 0600
curl-auth.conf: 0600
```

没有记录公网 IP、WireGuard 密钥、公钥、Cloudflare Token、Telnet/root 凭据或 DDNS 主机名。

## 意义

这次不再只是离线脚本验证，而是证明了两套正式 IPK 能在当前 `V1.0.0.2B5.8000` 实机上完成：升级前备份、原地升级、配置保留、服务恢复、运行审计和临时文件清理。以后重新安装或版本升级时，有可重复的备份/恢复和健康检查路径。

## 已知事项

- 本轮没有重启路由器，因此“整机重启后自动恢复”仍沿用此前持久化验证结论，本轮只验证插件级重启。
- 原厂 `PluginInfo` 数据库中的展示版本可能仍需与 `opkg` 版本同步；实际安装版本与运行状态已由 `opkg`、进程、接口和健康检查共同确认。
