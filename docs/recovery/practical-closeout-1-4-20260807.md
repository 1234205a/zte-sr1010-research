# SR1010 实用收尾 1–4（2026-08-07）

本轮一次性完成：完整恢复包、配置事务工具、Plugin 升级存活审计、WireGuard/DDNS 升级后恢复增强。全程仅处理本地文件，没有连接、写入或重启路由器。

## 1. 完整本地恢复包

新增 `tools/recovery-kit.py`，支持 `build` 和 `verify`。已实际生成：

```text
C:\Users\USER\Downloads\SR1010-V1.0.0.2B5.8000-local-recovery-kit-v2.zip
size: 168994638
sha256: 75BC017A132380486D8F0FE7A16BF525713FF736A28A8ABCA487FC9B9F654A43
```

包内包含 5 项：128 MiB 全闪存、网页恢复候选、原始 config.bin、net-runtime 0.2.1 IPK、DDNS 0.1.1 IPK，以及逐文件 SHA-256 manifest和恢复顺序说明。独立解包复验结果 `PASS`。

该 ZIP 含设备配置和凭据，只保存在本地，不上传 Git。

网页候选重新执行结构预检：magic、common CRC、kernel CRC、rootfs CRC、boot-prefix CRC全部通过。它仍属于候选恢复文件；未向路由器上传。

## 2. 配置备份—修改—回滚事务

新增 `tools/config-transaction.py`：

```powershell
python tools/config-transaction.py prepare config.bin WORKSPACE
python tools/config-transaction.py build WORKSPACE candidate.bin --set TelnetCfg:0:Lan_Enable=1
python tools/config-transaction.py rollback WORKSPACE rollback.bin
```

特点：

- `prepare` 保存不可变原件、工作 XML、哈希和格式元数据；
- `build` 仅允许统一工具白名单内的布尔开关，生成后反向解密、CRC和差异复验；
- `last-diff.json` 默认脱敏；
- `rollback` 恢复最初的 config.bin。

真实样本离线测试结果：二进制可重复；单字段修改只产生 1 项差异；rollback 与原件 SHA-256 完全相同。

## 3. 运营商升级与 Plugin 分区

新增 `tools/plugin-survival-audit.py`。当前全闪存与 `fw_flashing` 实测：

- 低槽写入范围：`0x00600000..0x02f00000`
- 高槽写入范围：`0x02f00000..0x05800000`
- Plugin：`0x05800000..0x08000000`
- 两个正常升级槽均不与 Plugin 重叠；
- `fw_flashing` 使用 `/dev/mtd0` 的受限区间写入，但不引用 `/dev/mtd9` 或 `/Plugin`。

结论：普通 Web/MQTT 双槽固件升级不会覆盖 Plugin 分区。整片 NAND 恢复、显式擦除 mtd9、恢复出厂流程的额外清理动作仍可能删除插件。

## 4. WireGuard/DDNS 升级后恢复

### net-runtime 0.2.1

本地生成：

```text
sr1010-net-runtime_0.2.1_arm.ipk
sha256: 6A968E28F656AF7CA05EA65577AAC8A7C544E3461F735D376D415D1192197959
```

新增：

- `post-upgrade-health.sh check|apply`
- WireGuard启动完成后自动检查 DDNS；
- DDNS停止时尝试重新启动；
- 配置权限自动收敛为0600；
- 保留原有防火墙、面板、备份和回滚逻辑。

### Cloudflare DDNS 0.1.1

本地生成：

```text
sr1010-cf-ddns_0.1.1_all.ipk
sha256: E4D9740328684330A5AA17F8E4F3F8B58E3044ADE528ECD423BA019B4016280E
```

新增：

- 配置和curl认证文件的带哈希备份；
- 安全归档路径检查和恢复；
- `prerm` 卸载前自动备份；
- `postinst` 重装后尝试恢复；
- `post-upgrade-health.sh check|apply`；
- 最多保留10份滚动配置备份。

两个IPK均通过 nativeC Plugin 包结构审计。当前设备仍运行原先版本，本轮没有安装0.2.1/0.1.1。

## 实际意义

现在已经具备：

1. 本地完整救援材料；
2. 不覆盖原件的配置修改事务；
3. 普通升级不会擦除 Plugin 的可重复证据；
4. 固件升级后自动拉起 WireGuard/DDNS 的新版安装包。

下一次实机维护只需先运行健康检查，再决定是否正式升级插件；不需要为了验证这些本地产物重启路由器。
