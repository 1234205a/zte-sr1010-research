# ZXSLC SR1010 NAND 固件软件逆向（2026-08-06）

> 样本来源与致谢：本阶段的初始离线研究基于 cnjn 公开分享的 [SR1010 NAND 固件](https://github.com/cnjn/ZXSLC_SR1010/releases/tag/1)，相关发布背景见[恩山无线论坛原帖](https://www.right.com.cn/forum/forum.php?mod=viewthread&tid=8462464&highlight=%E6%98%9F%E4%BA%91max)，后续完整研究见 cnjn 的[《星云max全分析》](https://github.com/cnjn/ZXSLC_SR1010/blob/main/%E6%98%9F%E4%BA%91max%E5%85%A8%E5%88%86%E6%9E%90.md)。该样本用于建立固件拆解和恢复工具链。

## 状态

用户决定先不动硬件，改为对公开NAND dump做纯软件逆向。暂停点：已完成固件校验、NAND几何确认、DTB/FIT解析、分区表还原、`usercfg` JFFS2最小提取和第一轮字符串/熵扫描；正在拆解双槽位内的私有加密rootfs。

原始文件仅留本机，不提交Git：

```text
C:\Users\USER\Downloads\ZXSLC_SR1010-1\ZXSLC_SR1010-1\dump.bin
C:\Users\USER\Downloads\ZXSLC_SR1010-1\ZXSLC_SR1010-1\dump_raw.bin
```

## 原始镜像

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `dump.bin` | 134217728（128MiB） | `334ED096AF0B93215BCD3C665283728F2CB3B91519D8E418FDB391319C31DC4E` |
| `dump_raw.bin` | 138412032 | `09A98D715A20BE04F28194698AC3768398598F27B1711288FD63562E6166B60F` |

`dump_raw.bin = 65536 × (2048数据+64 OOB)`，与W25N01KV的128MiB NAND页布局吻合。

## DTB/FIT与分区表

- 第一槽FIT：`0x006E3D10`，大小`0x290`；第一槽DTB：`0x006E3FA0`，大小`0x9296`。
- 第二槽对应副本：`0x02FE3D10` / `0x02FE3FA0`。
- FIT描述：`U-Boot uImage source file for 133 project`；配置：`zx279133`。
- 启动参数：`console=ttyAMA0,115200n8`、`root=/dev/mtdblock7`、`rootfstype=jffs2`、`bootcmd=zxboot`。

| 分区 | 起始 | 大小 |
|---|---:|---:|
| bootloader | `0x0000000` | `0x100000` |
| tags | `0x0100000` | `0x100000` |
| usercfg | `0x0200000` | `0x200000` |
| defcfg | `0x0400000` | `0x200000` |
| kernel1/rootfs1 | `0x0600000` | `0x2900000` |
| kernel2/rootfs2 | `0x2F00000` | `0x2900000` |
| Plugin | `0x5800000` | `0x2800000` |

这是A/B双槽位布局。每槽开头先出现可反汇编的ARM64 CSPBOOT/U-Boot代码与板级DTB；从约`0x800000`（第二槽对应`0x3100000`）开始是近满熵数据，未见JFFS2/UBI/SquashFS明文魔数，初判内层kernel/rootfs经过加密或ZTE私有封装。

## usercfg实测：纠正旧结论

`usercfg`首个有效JFFS2节点位于`0x320000`。自写最小解析器恢复出：`db_user_cfg.xml`、`db_backup_cfg.xml`、`diagnose_info.bin`、`env_parm.bin`、`ftest_result`、`logconf`及日志占位文件。

**关键纠正：`db_user_cfg.xml`并非明文XML。** 它以`01 02 03 04`开始，后续为高熵加密内容，大小28728字节；备份同类。旧进度第9节“物理读取NAND即可直接得到明文XML”的判断已被真实dump推翻。读取本机NAND仍能取得本机配置密文、OOB和状态，但不能绕过配置解密。

## Bootloader与安全启动初扫

可见字符串：`cspboot`、`secure_image_verify ,kernel magic is ok.`、`The security aes secret key has been set!!!`、`Safety boot aes secrect key write protected!!!`、`Safety boot aes secrect key read protected!!!`、`AES KEY check fail!`、`AES KEY write and check PASS!`、`MTD_ROOTFS/MTD_ROOTFS1`、`nand flash adapt to zbi->zmtd`。

这说明槽位CSPBOOT明确使用安全启动/AES/efuse路径。后续需沿`zxboot → secure_image_verify → AES`调用链判断内层密钥是公共密钥、设备efuse密钥，还是组合派生。

候选密码`5cE080@fyBD`、`Boot4128s!`、`Boot47516!`及三条完整密码提示未在ECC镜像中明文出现。可能不适用、位于一级启动代码、被哈希/混淆或设备派生。

## 本机产物与下一步

分析产物在`C:\Users\USER\Downloads\ZXSLC_SR1010-1\analysis\`。当前机器没有可用WSL发行版/binwalk/jefferson，使用Python 3.13、标准库和已有capstone，没有安装新软件。

后续顺序：①双槽位比较与边界；②切出CSPBOOT并追踪`zxboot/secure_image_verify/AES`；③识别`0x800000`密文结构；④解rootfs后重建配置解密；⑤Bootloader密码、OOB/ECC、完整JFFS2、DTS/恢复流程、统一工具。

