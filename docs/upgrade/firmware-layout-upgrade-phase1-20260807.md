# SR1010 自动固件布局与升级程序阶段 1（2026-08-07）

## 自动布局工具

新增 `tools/firmware-layout.py`，不再依赖固定 header 地址。它会：

1. 扫描 `ZXSLC SR1010` 产品记录。
2. 反推 0x510 字节槽头起点。
3. 校验 header CRC、common CRC 和 0x180000 字节启动前导区 CRC。
4. 从槽头恢复槽基址、kernel/rootfs 长度和文件偏移。
5. 自动提取两个 header、kernel、rootfs 并生成 JSON manifest。
6. 扫描 JFFS2、FIT/FDT、uImage、SquashFS、gzip、xz 和 LZMA 特征。

## 当前 128 MiB 转储实测

- 自动发现有效槽头：2 个。
- 两槽版本：`V1.0.0.2B5.8000`。
- 两槽 header/common/boot-prefix CRC：全部通过。
- 自动恢复槽基址：`0x00600000`、`0x02f00000`。
- 每槽 kernel：5561344 字节。
- 每槽 rootfs：24641536 字节。
- 两槽 kernel SHA-256 完全相同。
- 活动槽 rootfs 从偏移 0 开始即为 JFFS2。
- 备用槽 rootfs 起点不是 JFFS2，与仍有加密包装的既有结论一致。

输出文件：

```text
slot1-header.bin
slot1-kernel.bin
slot1-rootfs.bin
slot2-header.bin
slot2-kernel.bin
slot2-rootfs.bin
manifest.json
```

真实固件和提取内容不进入 Git，仅提交工具和脱敏报告。

## 升级程序初步映射

当前 rootfs 中已确认：

- `fw_flashing`：ARM32，80772 字节，527 个符号。
- `boot_flashing`：ARM32，36004 字节，226 个符号。
- `libupgrade_service.so`：18288 字节，160 个符号。

### `fw_flashing`

关键函数包括：

- `CheckBootFile` / `Checkheader` / `CheckFile`
- `check_ver_board`
- `SetVersionHeader` / `WriteVersion`
- `CspUserMtdErase` / `CspUserMtdWrite`
- `CspSwitchVersion`

字符串确认它会检查运行中 board ID、升级包 board ID、运行版本、升级版本、boot/header/content CRC，随后写入非活动槽并调用版本切换。

### `boot_flashing`

`CSPBootCheck` 会比较两个 upgrade key 并验证 boot CRC；存在明确的“No need to check upgrade key”分支，具体触发条件待下一阶段恢复。真实 key/加密常量不写入仓库。

### `libupgrade_service.so`

它是 MQTT/OTA 服务层，负责：

- 获取最新版本
- 上报设备版本和升级进度
- 将包校验失败、包类型不支持、安装失败映射成云端错误描述

## 下一步

1. 逆向 `check_ver_board`，确认是否真正禁止降级，还是只检查格式和 board ID。
2. 逆向 `CSPBootCheck` 的 upgrade-key 跳过条件。
3. 把 NAND raw/OOB 分离、坏块表和 JFFS2 提取接入统一 manifest。
4. 增加 kernel 内部 FIT/DTB 的精确边界识别，而不是只做特征扫描。
