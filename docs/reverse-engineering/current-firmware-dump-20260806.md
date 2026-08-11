# SR1010 V1.0.0.2B5.8000 在线只读固件转储

日期：2026-08-06  
方式：通过受控管理通道执行 root Telnet 只读 `/dev/mtd*`，将输出流式写入本地存储，并在两端复核 SHA-256。全程未调用任何MTD擦除或写入命令。

## 保存位置

- 本地存储：`ARTIFACT_DIR/sr1010-current-V1.0.0.2B5.8000/`
- 本机whole flash：`C:\Users\USER\Downloads\sr1010_analysis\current-V1.0.0.2B5.8000-whole-flash.bin`
- 原始转储未提交Git。

## 分区与哈希

| MTD | 名称 | 大小 | SHA256 |
|---|---|---:|---|
| mtd0 | whole flash | 134217728 | `EFE0C1B7BF98BD53FD2CB12A6DEE75577C62B80207CA1113965B8F352C961710` |
| mtd1 | bootloader | 1048576 | `4625409FC9C6145EB7BEEFA3956B28BD68B34A1E01DC5675F35331C48620C269` |
| mtd2 | tags | 1048576 | `30CEA3389CAAC82DB1828FA83DB371D4277107E635A3CCFBE803E470BFB8CD5C` |
| mtd3 | usercfg | 2097152 | `0DB3364F1CA7DFCF327A12396AA3DDBF92797B540378EC42F5476B5F69796BDA9` |
| mtd4 | defcfg | 2097152 | `EF08DAA1B0A7610AD8CD49069B69AC9F6ED1086E3D7A6FF48B208A14839E893D` |
| mtd5 | kernel1 | 42991616 | `C7A5CDC87786FFC4C2380AF8D4F1872C1B519363B02CFF664DB4EC934EC0ADB8` |
| mtd6 | kernel2 | 42991616 | `149F945B00E97CF8DE42C9276ED9DB9129288D77460075CD163B14F182E31DFF` |
| mtd7 | rootfs1 | 24641536 | `E7295BB6AA714A62C9856413C18CFEDF492FCA4D08C49CFC2D8E4E5C19991127` |
| mtd8 | rootfs2别名 | 42991616 | 与mtd6完全相同 |
| mtd9 | Plugin | 41943040 | `C9A8D05851242F1CB9C5B405A8CB3021E38F16E0BAD069091316945F0AF9D729` |

`mtd8`不是独立切片，而是与整个`kernel2`相同的重叠别名；`mtd7`则直接映射当前活动rootfs1范围。

## 当前槽位结构

两个槽尾头都报告`V1.0.0.2B5.8000`：

| 槽 | header | kernel | rootfs |
|---|---:|---:|---:|
| slot1 | `0x2460000` | `0x0780000`, `0x54DC00` | `0x0CE0000`, `0x1780000` |
| slot2 | `0x4D60000` | `0x3080000`, `0x54DC00` | `0x35E0000`, `0x1780000` |

两槽kernel逐字节相同；两槽rootfs不同。关键新发现：

- slot1 rootfs开头直接是JFFS2 magic `85 19`，即当前活动rootfs在flash中为明文JFFS2。
- slot2 rootfs仍包一层旧AES-128-ECB；使用`SR1010V102020030`解密后与slot1 rootfs逐字节相同。
- 当前系统挂载`/dev/mtdblock7`为只读JFFS2，与slot1明文状态完全吻合。

因此旧转储“两槽rootfs均加密”不适用于升级后的活动状态。更合理的模型是：升级/首次启动流程把活动槽rootfs解密为明文，备用槽保留加密封装；kernel仍保持相同封装。

## 当前rootfs恢复

- JFFS2：993个目录项、993个inode、927个普通文件。
- `kmodule.img`：19,673,088字节，SHA256 `3FBB2E29FE7A94124ABA084217C372D2694C880C8657781C9C641F7D0D1FAD46`。
- 当前`cspd`：3,329,124字节，SHA256 `8B8477E2598660653C27D796FCAAA5484F879CD263FB6CAA5E0A982B1CEE5AC1`。
- 当前`mqtt`：584,936字节，SHA256 `4AFD7A47A324ADBF2881E2C4265128F0D9C809EF4EEB68412542F839EFA615A3`。

相较旧样本，bootloader和tags各只有1个128 KiB擦除块变化，Plugin有21/320个擦除块变化；主要版本变化集中在两个固件槽。

## 下一步

1. 对当前`cspd`、`mqtt`、`fw_flashing`、`boot_flashing`做符号和字符串差异。
2. 恢复`pluginmgr`启动/清单协议。
3. 解析bootloader/tags变化块中的活动槽、升级和回滚字段。
4. 当前不进行任何flash写入；涉及启动槽或固件修改必须等现场可救援时再做。


