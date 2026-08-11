# SR1010 固件升级与插件存活闭环（2026-08-07）

## 1. /Plugin/apps 保留边界

实机分区和挂载确认：

```text
mtd3  usercfg  2 MiB   -> /usercfg
mtd4  defcfg   2 MiB   -> /defcfg
mtd5  kernel1 41 MiB
mtd6  kernel2 41 MiB
mtd7  rootfs1 23.5 MiB
mtd8  rootfs2 41 MiB
mtd9  Plugin  40 MiB   -> /Plugin
```

`/Plugin` 是独立 JFFS2 分区，不位于 kernel1/kernel2 写入范围。正常双槽固件升级写非活动槽并切换启动槽，不格式化 mtd9；已有真实重启也确认 `/Plugin/apps` 和 PluginInfo 持久。

结论：普通固件升级预期保留插件。整片 NAND 恢复或显式擦除 mtd9 仍会删除插件。mtd3 的剩余容量不足以容纳 2.7 MiB IPK，因此 `/usercfg/sr1010-recovery` 只保存小型配置备份与恢复脚本；IPK 第二副本保存在 mtd9 的独立 sibling 目录，完整离线工具包保存在 Gitea 发布资产和本机。

## 2. 升级流程

```text
Web VersionUpload / MQTT
 -> cspd UpgradeMain, event 0x2605
 -> 完整性、产品、upgrade key、版本策略检查
 -> UpgradeCtl
 -> fw_flashing::SetVersionHeader
 -> 永远选择非活动槽
 -> 写入并回读验证
 -> 更新 header 版本计数、有效标志和 CRC32
 -> CspSwitchVersion
 -> 新槽启动；旧槽保留为回滚底座
```

当前设备从低槽运行，正常下一目标为高槽 `0x02f00000..0x05800000`，selector=2，下一版本计数=5。内部存在 download-only/check-without-flash 分支，但公开 Web 未暴露安全入口，本轮没有上传固件、写 NAND 或切槽。

## 3. 升级保护

新增 `upgrade-guard.sh`：

- 调用正式配置备份；
- 复制最新配置到 `/usercfg/sr1010-recovery/config-latest.tar.gz`；
- 检查 WireGuard 二进制和生命周期脚本；
- 输出 `guard.status`，缺失时明确 degraded。

## 4. 恢复工具包

`sr1010-recovery-toolkit-20260807.zip` 包含：

- `sr1010-net-runtime_0.2.0_arm.ipk`；
- AES-256-GCM 加密配置备份；
- usercfg 恢复脚本；
- Plugin Manager install/enable helper；
- 无破坏模拟器和 SHA-256 清单。

解密密码仅在 Vaultwarden 条目 `SR1010 firmware-upgrade recovery bundle`，不进入 Git/发布资产。

现场容量实测：尝试把 IPK 复制到 2 MiB usercfg 时触发 `ENOSPC`；创建的部分文件随即删除，usercfg 恢复到 30% 使用率。恢复设计因此改成“usercfg 保存配置、mtd9 sibling 保存 IPK、站外保存完整工具包”。

## 5. 无破坏模拟

在本地隔离目录执行：解开正式 IPK、模拟整个插件目录被删除、从相同 IPK 恢复、解开配置备份、逐项校验 SHA-256。结果：

```text
result=PASS payload_delete_restore=yes config_hashes=yes secrets_in_ipk=no
```

实机另已完成配置 backup/check/apply 回放，WireGuard、双地址面板和防火墙规则均恢复。未在实机删除插件目录，也未触发固件升级。
