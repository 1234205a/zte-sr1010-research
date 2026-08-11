# SR1010 软件逆向阶段报告（2026-08-06）

## 结论摘要

- 已从128 MiB SPI-NAND样本恢复 `usercfg`、`defcfg`、`Plugin` 三个JFFS2区域。
- `db_user_cfg.xml` 与 `db_backup_cfg.xml` 内容相同，但仍是 Type-4（AES-256-CBC）加密容器，并非运行态明文XML。
- 配置容器参数：60字节外头、12字节块头、明文长度28652、密文长度28656。
- 双槽均为 `0x2900000` 字节；328个128 KiB擦除块中只有1块不同，且该块仅6字节不同，属于近乎完全镜像。
- 私有固件密文区约为 `0x780000..0x22e0000`，重复16字节块证明其符合AES-ECB特征。
- 原始NAND为2048字节数据+64字节OOB；没有发现坏块标记。直接剥离OOB后与处理版dump仅差3字节，分布于3页，主dump可信。
- FIT包装DTB位于槽1 `0x6e3d10/0x6e3fa0`，槽2对应位置整体平移 `0x2900000`。
- U-Boot可见硬件AES、eFuse读写保护和 `KEY_RESTORE` 相关分支。离线继续突破的首要目标是逆向该分支和AES寄存器配置。

## 修正旧结论

旧记录认为Flash数据分区中的 `db_user_cfg.xml` 是明文。实际提取验证表明它仍是Type-4密文；明文只可能在进程内存、临时文件或配置服务解密后的接口中存在。

## 已执行的配置解密尝试

- 标准SHA-256与ZTE同平台的错误版SHA-256。
- Tag区字符串、序列字段、MAC、型号、SSID等组合。
- 常见ZTE key/IV前缀、顺序变体、MD5/SHA-1/SHA-256二次派生。
- 已知ZTE AES-128-ECB rootfs密钥及SR1010型号组合。
- 每次候选均以AES解密后严格 `zlib.decompress` 和XML特征验证；尚未命中。

敏感字段、管理密码、Wi-Fi口令及设备唯一标识未写入本仓库。

## 可重复产物

- `tools/nand-layout-check.py`：输出分区哈希、双槽擦除块差异、raw/OOB一致性和坏块标记。
- 本地研究工作区另有JFFS2恢复、FDT解析、AArch64字符串交叉引用和错误SHA候选验证原型；待参数化和去除样本路径后再进入共享仓库。

## 下一步

1. 对 `secure_image_verify`、`AES KEY check`、`KEY_RESTORE`、`pdt_getreal_kernelfs` 建立AArch64函数边界和调用图。
2. 确认密文区头部 `33333333/cccccccc/88888888/dddddddd` 的结构字段和真实kernel/rootfs分界。
3. 判断 `KEY_RESTORE` 是测试密钥、密钥槽恢复还是OTP装载流程。
4. 若恢复私有rootfs，立即定位 `cpsd`/配置导入导出模块、错误SHA实现及最终key/IV覆盖点。

## 第三阶段暂停点：双槽差异字段已解释

按128 KiB擦除块比较后，双槽实际只有6字节不同，且全部位于各槽尾部头结构的相同相对位置`0x1CE01F2..0x1CE01FF`：

- 槽1绝对位置：`0x22E01F2..0x22E01FF`
- 槽2绝对位置：`0x4BE01F2..0x4BE01FF`
- 其中前2个差异字节属于一个小端32位地址字段：槽1为`0x00600000`，槽2为`0x02F00000`，正好分别等于kernel1/kernel2槽起点。
- 后4个差异字节属于紧随其后的32位校验字段：槽1为`0xA96C2F93`，槽2为`0x46318FFC`。
- 地址字段之间的其他值（`3`、`1`）以及后续长数据完全相同。

因此双槽并非不同固件版本；6字节差异由“本槽物理起点+随之变化的头部校验”完整解释。后续无需分别逆向两个槽，只分析槽1即可，槽2用于验证地址重定位和校验算法。

## CSPBOOT静态追踪补充

- 槽内可执行映射基址确认为`0x84000000`，本地已生成完整AArch64反汇编和重点函数片段。
- 安全启动/AES/eFuse日志字符串存在，但编译方式未产生简单的直接字符串交叉引用，需要继续从调用图、MMIO访问和函数表恢复。
- 对`0x10E40000`的首轮追踪落入PON时钟/模式代码，已排除其为固件AES控制器，避免后续沿错误MMIO地址继续分析。
- 用户要求先跳过硬件密钥链，下一主线改为固件尾部头结构、校验算法和可重复工具。

## 第四阶段：槽尾头CRC和加密层边界已还原

槽尾头可通过两个条件自动识别：偏移`+0x08`为小端`0x510`，且`CRC32(header[0:0x1FC]) == u32(header+0x1FC)`。实测：

| 槽 | 头位置 | 头CRC32 | 版本 |
|---|---:|---:|---|
| kernel1 | `0x22E0000` | `0xA96C2F93` | `V1.0.0.1B5.8000` |
| kernel2 | `0x4BE0000` | `0x46318FFC` | `V1.0.0.1B5.8000` |

由头字段和128 KiB对齐关系恢复出的分层：

| 层 | 槽1 | 槽2 | 长度 |
|---|---:|---:|---:|
| 加密kernel | `0x0780000` | `0x3080000` | `0x54C500` |
| 加密rootfs | `0x0CE0000` | `0x35E0000` | `0x1600000` |
| 槽尾头 | `0x22E0000` | `0x4BE0000` | `0x510` |

`kernel`与`rootfs`两份槽位切片分别逐字节相同。16字节块重复统计：kernel有552个重复块，rootfs有12805个重复块，进一步确认二者均具有ECB型分块加密特征。

头部`+0x38=0x180334`、`+0x3C=0x6D4AD138`以及`+0x44=0x6E0314`、`+0x48=0x7EBEEE9D`很可能分别是解密后kernel/rootfs的有效长度与CRC；它们不匹配密文CRC32，符合“头保存明文校验”的设计，但仍需解密后最终验证。

新增工具[`tools/slot-header-carve.py`](tools/slot-header-carve.py)：自动扫描有效头、验证CRC32并切出每槽的`kernel.enc`、`rootfs.enc`和`header.bin`。

## 第五阶段重大突破：rootfs已解密

对未加密bootloader、Tag和槽内CSPBOOT区域进行逐字节滑动的16字节候选常量扫描。利用ECB中“全零块/全FF块加密后会形成高频固定密文块”的性质，不需要先知道文件系统魔数即可筛选候选。

在CSPBOOT镜像偏移`0x68BFA6`发现16字节ASCII密钥：`SR1010V102020030`。使用AES-128-ECB、无填充解密`0x0CE0000..0x22E0000`后，首字节立即成为合法JFFS2节点`85 19 01 E0`。两槽rootfs密文哈希相同，解密结果也相同。

恢复结果：989个目录项、989个inode、924个普通文件。关键内容包括：

- `kmoduletmp/kmodule.img`：18,165,760字节，合法SquashFS v4（`hsqs`），应包含主要应用和库。
- `/etc/hardcode`、`/etc/enhardcodefile`、`/etc/enwebdhardcodefile`。
- Dropbear配置及主机密钥、`passwd`、`shadow`、`inetd.conf`。
- LXC下层BusyBox、telnet/telnetd入口、插件管理器。

加密kernel使用同一密钥直接解密后尚未出现可靠FIT/Linux魔数，说明kernel层可能有不同起点、额外头、不同密钥或不同模式；rootfs突破已独立确认。

新增`tools/decrypt-ecb-layer.py`用于可重复解密和魔数扫描。下一主线是提取`kmodule.img` SquashFS并定位配置导入导出程序。

## 第六阶段：进入主应用 SquashFS，锁定配置加密实现

已验证`kmodule.img`为可正常枚举的SquashFS v4，共1113个目录项。Windows版`squashfs-tools-ng 1.0.0`的压缩包SHA256为`F5D2C71062B45341A2253710287BB385372D4A4F1EE72CD74B10EBB0C79CBFF0`。其全量解包在Windows符号链接处理处持续占用CPU，因此改用`rdsquashfs --cat`逐文件无损导出；新增[`tools/squashfs-select-extract.py`](tools/squashfs-select-extract.py)固化此路径。

主配置服务已确认是32位ARM ELF `bin/cspd`，入口`0x1EF28`，导出后大小3,124,626字节。相关组件还包括`bin/cpeserver`、`bin/config_learning`、`lib/libcsputil.so`和OpenSSL 1.0.0库。`cspd`内同时存在：

- `AES_set_encrypt_key`、`AES_set_decrypt_key`、`AES_encrypt`、`AES_decrypt`、`AES_cbc_encrypt`；
- `CspHardCodeEncryDefaultKey`；
- `/var/tmp/db_encrycopy.bin`、`/var/tmp/db_user_cfg.xml`、`/etc/db_user_cfg.xml`；
- `DB cfg encry fun null`、`DB cfg encry fail`、`dbFileEncry`；
- `/var/tmp/curconfig.bin`、`/var/tmp/defconfig.bin`；
- `encrypt success %s ==> %s`和`decrypt success %s ==> %s`。

这把配置导入/导出的调用链从“猜测CSPBOOT算法”收敛到了一个明确的用户态目标：`cspd`中的`dbFileEncry`及其AES调用。Web端的`do_download_usercfg.lua`和`do_restore_usrcfg.lua`是Lua 5.1字节码，只分别转交`modules.file_download_logic.DownloadFile("config")`和`modules.file_upload_logic.UploadFile("ConfigUpload")`，实际密码学不在Web脚本中。

下一步按字符串交叉引用恢复`dbFileEncry`函数边界、参数和密钥来源，并用现有`config.bin`做解密/再加密闭环验证。kernel使用的第二把密钥仍保持独立支线。

## 第七阶段：还原Web到CSP的控制链，并校验ELF提取完整性

补提取`file_download_logic.lua`和`file_upload_logic.lua`后确认，两者调用同一个原生入口`cgilua.cmapi.nocsrf.callUploadDownloadProc`，参数结构包含`fileCtrlID`、`serverFD`和`execOut`。因此配置上传下载不是Lua直接读写文件，而是经CMAPI消息转入`cspd`；`config`与`ConfigUpload`是两个控制ID。后续动态追踪时只需观察这两个ID对应的处理分支。

同时发现当前Windows版`rdsquashfs --cat`导出的稀疏ELF存在布局异常：`cspd`的程序头声称首个LOAD段为`0x243844`字节，但节表偏移落入动态字符串区，标准ELF解析器会在压缩节头处失败；全量/单文件`--unpack-path`则持续占用CPU而不落盘。当前导出件SHA256为`A22363AEB602E41F086C24D98A2EE2C1AD6EE557C60E458C9F678554D9F10EA6`，只适合字符串与接口清单分析，暂不作为最终反汇编基准。`kmodule.img`本体SHA256为`1110AED0D43A2D0E2BCFF5E70CC1C1DC7DD6F2071456A8D642E95A130E399C3A`。

这一步避免了在错位ELF上制造虚假的函数地址。下一解包路线将换用Linux原版`unsquashfs`或直接解析SquashFS inode/fragment表，取得保留稀疏区的原始`cspd`后再做AES调用交叉引用。

## 第八阶段：取得完整cspd并还原AES密钥派生

升级到`squashfs-tools-ng 1.3.2`后，`--cat`的稀疏文件前向seek问题已修复。工具ZIP SHA256为`CAAD53995FA75E8DEC867D048192B9F0C86CCACA3644C4025FCA2FB59F7CFF2F`；新导出的`cspd`为3,106,388字节、SHA256 `EB7062B96F8885035A719FB428A6B100933D8BE0C7FE5D65876550BD49106250`，完整包含`.symtab`的22,836个符号，ELF节表可正常解析。

配置相关函数已经精确定位：

- `dbFileEncry @ 0x199814`、`dbFileDecry @ 0x1990BC`；
- `dbFileVerifyAndDecry @ 0x1991D8`；
- `dbcSetEncryKey @ 0x19E65C`、`_dbcSetEncryComKey @ 0x19E4D8`；
- `AESCBCEncry @ 0x1A0C30`、`AESCBCDecry @ 0x1A0B28`；
- `dbcCfgFileDecry @ 0x1A2DA4`、`_dbGetCfgFileEncryKey @ 0x1AAF18`。

`dbcSetEncryKey`先读取Tag参数`0x1004`（32字节）、`0x0200`（64字节）和`0x0100`（6字节MAC），构造旧式候选`%s%sMcd5c46e`与`G21b667b%s%s`；随后`_dbcSetEncryComKey`读取`DevInfo.ModelName`，去掉空白，并用常量`0x0510`、`0x0001`覆盖成通用密钥短语：

```text
KEY_PHRASE = strip_spaces(ModelName) + "Key" + "0510" + "0001"
IV_PHRASE  = strip_spaces(ModelName) + "Iv"  + "0510" + "0001"
AES_KEY    = SHA256(KEY_PHRASE)             # 32字节，AES-256
CBC_IV     = SHA256(IV_PHRASE)[0:16]        # CBC取前16字节
```

`AESCBCEncry`明确传入`AES_set_encrypt_key(..., 0x100)`，即256位密钥；数据使用零字节补齐，并且明文恰好16字节对齐时仍增加一整个16字节块。解密走`AES_set_decrypt_key`和`AES_cbc_encrypt(..., AES_DECRYPT)`。

新增[`tools/config-key-derive.py`](tools/config-key-derive.py)复现短语、SHA256、AES-256密钥与IV派生。下一步是还原`dbcCfgFileDecry`外层magic/CRC/分块头，并对样本`db_user_cfg.xml`执行闭环。

## 第九阶段：Type-4配置已完整解密

使用`ModelName=SR1010`对JFFS2中的`db_user_cfg.xml`实测成功。输入大小28,728字节、SHA256 `89AAE2FCC04A0D7C9EF5DF703850000E5435CFC6806F29A75BDC02F71DEB317E`；输出是232,443字节完整XML，SHA256 `867DC71FDFB5C6DB1B2AD0174B8AC3FF37A8693B9A1D2C06E3D4958BFE2EF3AC`。正文未提交仓库，避免泄露设备配置。

外层格式已还原：

```text
+0x00  BE32  0x01020304
+0x04  BE32  type=4
+0x3C  BE32  内层实际长度（本样本0x6FEC）
+0x40  BE32  AES密文长度（本样本0x6FF0，16字节对齐）
+0x48        AES-256-CBC密文
```

解密后的内层同样以`0x01020304`开头；`+0x08`为最终XML总长度，`+0x10`为首块解压长度，块数据使用zlib。首块在`+0x40`只保存`压缩长度/下一块偏移`，后续块保存`解压长度/压缩长度/下一块偏移`，最后一块的下一偏移为0。本样本四块依次解出65,536、65,536、65,536、35,835字节，合计232,443字节。

新增[`tools/config-bin-decrypt.py`](tools/config-bin-decrypt.py)，包含外层校验、密钥派生、AES解密、块链边界检查、zlib解压和总长度验证。实测命令：

```powershell
python tools/config-bin-decrypt.py db_user_cfg.xml db_user_cfg.dec.xml --model SR1010
```

配置解密目标已经完成。后续可继续恢复反向打包器，并只在本地分析XML中的隐藏服务、诊断开关和账号字段。

### 解密配置的非敏感安全状态摘要

仅记录开关和字段结构，不提交账号、口令、密钥、服务器地址或完整XML：

- `TelnetCfg`存在完整的LAN/WAN、端口、用户名、口令、失败锁定和安全模式字段；当前总开关、LAN和WAN均为0。
- `Log.SerialEnable=1`，`LogSerialCfg`中的`SerialEnable/PrintfEnable/PrintkEnable`均为1，说明串口日志路径在配置层启用，但不等于串口登录免密。
- `DiagCfg.RemoteDiag=0`、`SysdiagCfg.Enable=0`，但诊断连接表保留URL、端口和加密参数。
- `FTPServerCfg.FtpEnable=0`且`WanIfEnable=0`，同时仍保存一条FTP用户记录。
- `DevAuthInfo.Enable=1`且保存用户/口令字段；其具体值只留在本地分析副本。
- `SyslogCfg.RemoteEnable=1`，远端地址、端口和TLS口令字段已在本地标记，仓库中全部省略。
- `SecProtect.EnableProtectAdminPass=0`、`EnableProtectWifiPass=0`，说明当前配置未启用这两个额外保护标志。
- `Upgrade.UpgradeUserCfgEn=0`，但保留远程配置和固件URL字段。

这些结果证明加密配置内确实包含此前无法从外层JFFS2判断的管理服务、诊断通道和认证状态。下一步优先恢复可重打包格式，并评估哪些字段由运行时策略再次覆盖。

## 第十阶段：配置反向打包实现逐字节闭环

从`EncryByCRC @ 0x1A1A60`还原了内层完整性算法：每个64 KiB明文块使用zlib level 9压缩；所有“压缩数据本体”按顺序累计标准CRC32，写入内层`+0x14`；随后对内层头前`0x18`字节计算标准CRC32，写入`+0x18`。内层头实际为`0x3C`字节，每条块记录统一由`解压长度/压缩长度/下一记录绝对偏移`三个BE32组成。

新增[`tools/config-bin-pack.py`](tools/config-bin-pack.py)，实现：

1. XML按64 KiB切块；
2. zlib level 9压缩；
3. 构建块链和两级CRC32；
4. 构建Type-4外层；
5. SHA256派生密钥/IV并执行AES-256-CBC；
6. 按固件规则执行严格下一块零填充。

使用原始解密XML重新打包后，输出28,728字节，SHA256仍为`89AAE2FCC04A0D7C9EF5DF703850000E5435CFC6806F29A75BDC02F71DEB317E`，与原始`db_user_cfg.xml`从第0字节到末尾完全相同。由此确认压缩级别、头结构、CRC、密钥、IV、填充和AES模式全部闭环，不再只是“能够解密”。

认证字段只做类型审计：`DevAuthInfo.Pass`、`FTPUser.Password`、`TelnetCfg.TS_UPwd`、`SambaCfg.PassWord`等长度符合直接字符串存储特征，并非统一的固定长度哈希；具体值继续只保存在本地明文副本中。回家实测时应先使用原配置记录核对正常Web入口，不应直接导入修改版作为第一步。

## 第十一阶段：脱敏审计和最小开关修改器

新增[`tools/config-audit.py`](tools/config-audit.py)：直接读取加密Type-4配置，解密后输出管理面开关；对于用户名、口令、密钥、URL、服务器和地址类字段只报告“存在及长度”，不输出值。

新增[`tools/config-switch-edit.py`](tools/config-switch-edit.py)：使用`TABLE:ROW:FIELD=0|1`语法修改经过白名单审核的布尔开关，保持原XML其余字节不变，随后调用反向打包器，并立即再次解密验证输出。工具不接受用户名、密码、端口或地址修改，避免敏感值进入命令行历史，也降低首次实机验证的变化范围。

本地测试将`LogSerialCfg[0].PrintfEnable`从1改为0：新配置生成成功，反向解密与预期修改后的XML逐字节相同；再次审计只观察到该字段由1变为0。测试配置和审计结果只保存在本地分析目录，未提交仓库。

示例：

```powershell
python tools/config-audit.py config.bin --json audit-redacted.json
python tools/config-switch-edit.py config.bin config-mod.bin --set "LogSerialCfg:0:PrintfEnable=0"
```

回家后的首次测试顺序应是：保存设备新导出的原始配置与版本信息、运行脱敏审计、验证原文件可被设备正常恢复，最后才测试单字段修改版。不要把启用Telnet、诊断和WAN管理组合成同一次首次导入。

## 当前实机配置兼容性验证（V1.0.0.2B5.8000）

用户从当前设备导出的`config.bin`大小34,344字节，SHA256为`<ORIGINAL_CONFIG_SHA256>`。现有解密器无需修改即成功处理：5个zlib块、明文286,082字节，明文SHA256为`<PLAINTEXT_CONFIG_SHA256>`。

这确认从旧样本`V1.0.0.1B5.8000`还原的Type-4算法、`ModelName=SR1010`密钥派生和块格式继续适用于当前`V1.0.0.2B5.8000`。当前配置比旧样本从241张表/5,554个字段扩展到280张表/6,935个字段；脱敏开关审计显示Telnet、FTP、远程诊断仍关闭，串口日志/printf/printk仍开启，远程Syslog开启，`DevAuthInfo`记录启用。

当前明文配置及脱敏JSON只保存在本地分析目录，未上传仓库。`config.bin`是当前运行配置而非完整固件镜像；其价值是验证当前版本兼容性、核对Web认证信息和生成最小修改配置，不能替代NAND/固件分区转储。
