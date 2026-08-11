# SR1010 统一离线入口与自检（2026-08-07）

新增统一入口子命令：

- `firmware-layout`
- `recovery-kit`
- `config-tool`
- `config-transaction`
- `plugin-survival`
- `upgrade-policy`
- `offline-selftest`

同时修复了旧统一入口在转交带选项参数时打乱参数顺序的问题，现在直接保留 `sys.argv[2:]`。

本机完整自检结果：

| 项目 | 结果 |
|---|---|
| 128MiB闪存和双槽CRC | PASS |
| config.bin五块往返 | PASS |
| 网页候选全部CRC | PASS |
| 恢复ZIP五项哈希 | PASS |
| net-runtime 0.2.1 IPK | PASS |
| DDNS 0.1.1 IPK | PASS |
| 固件槽与Plugin边界 | PASS |

最终结果：`PASS`。报告只包含尺寸、哈希和非敏感结构信息，不包含配置正文或凭据。
