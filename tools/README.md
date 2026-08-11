# SR1010 工具索引

## 配置

- [`config-bin-tool.py`](config-bin-tool.py)：Type-4 检查、解包、重打包、严格验证和往返测试。
- [`test-config-bin-tool.py`](test-config-bin-tool.py)：不含真实配置的回归测试。
- `config-audit.py`：脱敏控制面审计。
- `config-switch-edit.py`：定向开关修改。

## 固件与恢复

- [`upgrade-policy-audit.py`](upgrade-policy-audit.py)：核对 board/version 前缀、VID 与 boot upgrade-key 策略。

- [`firmware-layout.py`](firmware-layout.py)：自动发现双槽头并提取 kernel/rootfs/manifest。

- [`cspd-config-map.py`](cspd-config-map.py)：提取配置导入/导出关键函数与直接调用关系。

其他脚本保持原文件名；后续会按 rootfs、升级、恢复和运行时继续补齐索引。

## 恢复与升级后维护

- [`recovery-kit.py`](recovery-kit.py)：构建并验证只保存在本地的完整恢复包。
- [`config-transaction.py`](config-transaction.py)：配置备份、修改、差异和回滚事务。
- [`plugin-survival-audit.py`](plugin-survival-audit.py)：验证固件槽与 Plugin 分区不重叠。
- [`post-upgrade-health.sh`](post-upgrade-health.sh)：升级后检查并恢复 WireGuard/DDNS。
- [`build-net-runtime-v021.py`](build-net-runtime-v021.py)：构建 net-runtime 0.2.1。
- [`build-net-runtime-v022.py`](build-net-runtime-v022.py)：构建带受保护管理面板和令牌生命周期的 net-runtime 0.2.2。
- [`build-cf-ddns-ipk.py`](build-cf-ddns-ipk.py)：构建带严格配置校验、错误分类、退避和事务恢复的 DDNS 0.1.2。
- [`test-cf-ddns-v012.py`](test-cf-ddns-v012.py)：离线验证 IPK、错误分类、退避、恢复和 shell 语法。

## 统一自检

- [`offline-selftest.py`](offline-selftest.py)：一次检查闪存、配置、网页候选、恢复ZIP、IPK和Plugin边界。
