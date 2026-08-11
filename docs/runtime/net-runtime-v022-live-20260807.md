# SR1010 net-runtime 0.2.2 实机升级闭环（2026-08-07）

## 最终结果

在固件 `V1.0.0.2B5.8000` 上通过原厂 `0x2410 PluginCmapiUpgrade` 将
`sr1010-net-runtime` 正式登记并升级为 `0.2.2`，原厂记录为
`DEV.PluginInfo4`，`plugin_rc=0`。全程没有重启路由器，没有修改
Telnet/root 凭据或限制 Telnet。

最终实机状态：

```text
opkg Version: 0.2.2
WireGuard: running/configured
Cloudflare DDNS: running
LAN dashboard: 0.2.2, HTTP 200
WireGuard dashboard: 0.2.2, HTTP 200
unauthorized POST /action: HTTP 401
authorized net-backup: HTTP 200
dashboard token: preserved, mode 0600
backup format: sr1010-net-runtime-backup-v2
lifecycle audit: 15 PASS / 0 FAIL
```

最终 IPK：`sr1010-net-runtime_0.2.2_arm.ipk`

```text
SHA-256 3122A063360360286C92624555BDF062DA3A364CB1E7648067EEBD376E97EE58
```

## 0.2.2 内容

- 将受令牌保护的双地址管理面板正式装入 IPK；
- 令牌不进入包，已有令牌原样保留，缺失时在设备本地原子生成；
- 令牌与 WireGuard 配置一起使用 v2 格式备份，权限均校验为 `0600`；
- 恢复脚本兼容 v1 备份，v1 恢复时保留当前令牌；
- 重装时可从最新 v2 备份恢复令牌；
- 生命周期审计新增令牌文件、大小和权限检查；
- 安全升级调用器在原厂事务结束后总是调用固定 `start.sh`，覆盖原厂成功和失败路径均可能留下插件停止的问题。

## 离线验证

包结构审计通过，生命周期模拟结果：

```text
install=PASS
upgrade=PASS
uninstall_restore=PASS
reinstall=PASS
token_not_embedded=PASS
```

测试还会扫描 IPK 内全部 `.sh`，拒绝 CRLF 换行。

## 实机中发现并修复的问题

首次构建复用了 Windows 工作区中的历史 shell 文件，Git 换行转换导致部分文件以
CRLF 进入 IPK。原厂事务成功后 `start.sh` 的 shebang 被解释为不存在的
`/bin/sh\r`，WireGuard 和面板停止。现场先把包内脚本规范为 LF，再调用固定
`start.sh` 恢复；没有重启路由器，DDNS始终运行。

随后构建器增加强制 LF 规范化和回归检查，重新构建并通过第二次 `0x2410` 覆盖。
升级覆盖运行中 WireGuard 映像后又出现一次已知的 `unmanaged_interface_exists`，按
0.2.1 已验证流程执行插件级 `stop/start` 后收敛为 `running/configured`，最终审计
15/15 通过。

这次实机还确认原厂 `0x2410` 即使返回成功，也不能假定插件已经运行。因此升级调用器
现在无论事务成功或失败都会调用白名单插件的固定启动脚本，并把启动失败计入最终返回码。

## 令牌与备份

升级前把现有令牌单独复制到插件备份目录并设为 `0600`。升级后比较新旧文件的
SHA-256，二者相同；报告不记录实际摘要。随后生成 v2 配置归档，`restore.sh latest
check` 校验通过。管理令牌仍只存在设备和 Vaultwarden，不在 Git 或 Release 中。

## 清理

- 路由器 `/tmp` 中 IPK、升级调用器和输出文件已删除；
- 一次性局域网 HTTP 服务在 Release 上传完成后关闭；
- 设备持久备份目录保留升级前令牌副本和滚动 v2 配置归档。

