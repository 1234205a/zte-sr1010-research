# SR1010 原厂 pluginmgr 正式升级登记实机闭环（2026-08-07）

## 最终结果

已在当前固件 `V1.0.0.2B5.8000` 上通过原厂 `0x2410 PluginCmapiUpgrade` 事务完成两个插件的正式升级登记：

| 插件 | 版本 | 原厂响应记录 | 结果 |
|---|---:|---|---|
| sr1010-net-runtime | 0.2.1 | `DEV.PluginInfo4` | `plugin_rc=0` |
| sr1010-cf-ddns | 0.1.1 | `DEV.PluginInfo3` | `plugin_rc=0` |

原厂 `0x2401 PluginCmapiSet` 随后对两个插件返回成功，Enable 已设置为 1。

## 关键逆向结论

### 事件映射

- `0x2409`：安装
- `0x2410`：升级
- `0x2411`：卸载
- `0x2401`：启停/运行状态
- `0x2402`：全局插件操作状态

### `0x2410` 请求布局

请求长度为 `0xBE0`：

- 插件 ID ctype：基址 `0x88`，字符串值位于 `0xA4`；
- 下载 URL ctype：基址 `0x188`，字符串值位于 `0x1A4`；
- ctype present 标志位于字段基址 `+2`。

新增工具：`tools/pluginmgr/cm-plugin-upgrade-ssend.c`。

### 下载 URL 约束

`pluginmgr` 的 `url_contains_authinfo()` 实际不是检查 HTTP Basic Auth，而是要求 URL 同时包含以下四个字段名：

```text
scpsign
scptime
key1
key2
```

缺少时会查询 `/plugin/authlist`；本地 URL 不在该列表时返回 `-105`。实机使用 nativeC 回环的一次性文件服务器，并为四个字段填入本地占位值后，原厂升级事务成功。

## 发现的原厂缺陷

当 `0x2410` 已找到插件记录、停止现有插件，但随后 URL 授权检查返回 `-105` 时，原厂流程不会自动重新启动刚刚停止的插件。本轮两次失败探测后均通过插件自己的 `start.sh` 恢复，未重启路由器。

这意味着以后调用原厂升级事务前必须：

1. 先备份配置；
2. 先验证本地下载 URL；
3. 预置失败后的服务恢复步骤；
4. 不能假设 pluginmgr 会在所有失败路径自动回滚运行状态。

## 最终实机验证

```text
sr1010-net-runtime Version: 0.2.1
sr1010-cf-ddns Version: 0.1.1
WireGuard state=running
WireGuard detail=already_started
DDNS loop=running
lifecycle audit: 13 PASS / 0 FAIL
post-upgrade-health: PASS WireGuard
post-upgrade-health: PASS DDNS
backup restore checks: PASS
LAN dashboard: HTTP 200
```

配置文件权限仍为 `0600`。没有重启路由器，没有修改 Telnet/root 凭据，也没有把公网 IP、域名、Token 或 WireGuard 密钥写入仓库。

## 清理

- 路由器 `/tmp` 中调用器、IPK 和一次性 HTTP 服务文件均已删除；
- NAS 临时 HTTP 服务已停止；
- NAS 临时传输目录已删除；
- 持久化配置备份保留在各插件的备份目录中。
