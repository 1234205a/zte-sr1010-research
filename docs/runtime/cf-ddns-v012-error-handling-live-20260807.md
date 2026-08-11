# sr1010-cf-ddns 0.1.2 错误处理与实机部署

日期：2026-08-07  
固件：`V1.0.0.2B5.8000`  
结论：无整机重启完成升级，DDNS、WireGuard 和双地址管理面板均正常。

## 0.1.2 改动

- 配置在启动、更新、备份和恢复前统一经过 `validate.sh` 校验。
- `ddns.env` 仅允许已知字段，Zone/Record ID、记录名、数值范围和 `0600` 权限均严格检查。
- curl 配置仅允许 Bearer 授权头、JSON 内容类型及三个固定开关，拒绝未知选项。
- 区分传输失败、401/403 鉴权失败、404 记录不存在、429 限流、5xx、其他 HTTP 错误和 Cloudflare API 失败。
- 状态目录记录最后尝试、结果、错误类别、连续失败数和下次重试时间。
- 连续失败采用指数退避，并受 `MAX_BACKOFF` 上限约束；成功后清零。
- 配置恢复先校验归档、哈希和权限，再事务切换；失败时恢复原配置和服务。
- 循环每 30 秒内更新心跳。管理面板和升级后检查在 PID 不可见的命名空间中使用心跳判断，避免把运行中的服务误报为停止。
- 启停脚本按 `/proc/*/cmdline` 核对真实循环；停止等待退出并在超时后强制终止，启动会复核正在退出的候选进程，避免重复循环和停启竞态。

日志中的公网地址暂未脱敏，按本轮要求留到后续统一处理。

## 离线验证

`test-cf-ddns-v012.py` 使用假 curl 覆盖传输失败、401、403、404、429、500、API 失败和成功路径，并检查 IPK 结构、控制字段、退避、恢复及 shell 语法。

```text
package=PASS errors=PASS backoff=PASS rollback=PASS shell_syntax=PASS
```

构建两次得到相同 SHA-256：

```text
2dd391469d0fd317f78c74a6da5fa495953b23119adf0df6b2a117ecc4df6062  sr1010-cf-ddns_0.1.2_all.ipk
```

`plugin-ipk-audit.py` 检查包名、版本、StartCMD、StopCMD、StartMode、父目录和 nativeC 约束，结果为 `PASS`。

## 实机升级经过

1. 升级前执行只读健康检查、配置形状核对、配置备份和恢复预检，均通过。
2. 原厂 `0x2410` 返回 `plugin_rc=0`，但包版本和文件均未变化。这是一次可复现的“成功返回但未安装”，不能只信 IPC 返回码。
3. 首次直接升级到 0.1.2 成功。随后同版本 `--force-reinstall` 打印文件冲突却仍返回 0，并使该包的 opkg 状态条目消失；旧文件和服务仍在。
4. 恢复流程先确认配置备份有效、停止重复循环、保留旧目录，再使用 `--force-overwrite` 干净安装并做后验校验，包数据库和服务恢复正常。
5. 最终构件通过标准 `opkg remove` 加 `opkg install` 重新安装，postinst 从校验过的最新备份恢复配置。

由此增加两条操作规则：

- 原厂 `0x2410` 和本机定制 opkg 的退出码都不是充分条件，必须验证包数据库、关键文件、配置、服务和进程数。
- 同版本更新不要使用 `opkg --force-reinstall`；先备份并校验，再执行标准卸载/安装，保留可独立启动的现场回退目录直到验收结束。

## 最终实机结果

```text
sr1010-net-runtime=0.2.2 installed
sr1010-cf-ddns=0.1.2 installed
DDNS update=PASS unchanged
DDNS config validation=PASS
DDNS config modes=0600/0600
DDNS backup restore check=PASS
WireGuard=running
DDNS=running
DDNS loop processes=1
LAN panel=0.2.2/0.1.2/running
WireGuard panel=0.2.2/0.1.2/running
LAN unauthorized POST=401
WireGuard unauthorized POST=401
authorized stop=200/stopped
authorized start=200/running
authorized repeat start=200/running
```

net-runtime 的 `post-upgrade-health.sh` 已在实机覆盖为心跳兼容版本，并保留原文件备份。该覆盖应在下一个 net-runtime IPK 中正式收编。

全程未重启路由器，未修改 Telnet/root 凭据或访问策略，未把 Token、私钥、真实记录 ID 或恢复机密写入 Git。
