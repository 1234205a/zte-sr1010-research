# SR1010 启动链六项离线审计

日期：2026-08-06  
固件：`V1.0.0.2B5.8000`  
样本：当前设备完整 NAND 转储

## 总结

六项任务中，前五项已完成现有样本能够支持的离线分析；第六项已经形成现场只读验证流程，但因设备不在手边，电气层实测仍待回家执行。全程没有写路由器 flash，也没有启动远程诊断控制面。

最重要的新结论：

1. U-Boot 没有密码校验，真正的不确定点是 CSPBOOT/板级串口门控；
2. 当前 U-Boot 保留了相当完整的读写、网络启动和升级命令面；
3. 安全启动同时存在镜像校验、硬件 AES/eFuse 和升级 CRC/key/signature 框架，但不能简单等同于“所有升级都强制非对称签名”；
4. `tags` 主要是设备出厂身份及无线参数 TLV，不是活动槽/回滚状态区；
5. Bootloader 恢复入口是串口按键 `1` + TFTP `upgrade.bin`，未发现 Bootloader HTTP 恢复服务器。

## 1. CSPBOOT debug 触发与串口门控

MTD bootloader 的早期层是 AArch64 CSPBOOT/BOOTROM 包装，包含：

```text
enter bootloader...
Debug mode!
Trigger debug mode !
debug
```

早期代码和完整 U-Boot 是两个阶段。完整 U-Boot 明确配置 `stdin/stdout/stderr=serial`；Linux 命令行里的 `serial=close` 并不能证明 U-Boot 自己关闭串口。

本轮逐段扫描没有发现 CSPBOOT 的密码提示、密码常量或哈希比较。`Trigger debug mode !` 邻近区域也没有 SN/MAC/OTP 文本依赖。因此其门控更可能是启动状态、GPIO/按键或早期串口字符，而不是派生密码。

**尚未静态闭环的点**：当前 CSPBOOT 没有符号表，字符串交叉引用受到扁平镜像重定位和 literal pool 混排影响；现有证据不足以在“GPIO”与“串口字符”之间作唯一选择。这一项已完成排除密码链，但精确触发条件仍需 UART/GPIO现场观测。

## 2. U-Boot 命令面恢复

从槽内 U-Boot 正文、命令名及帮助字符串恢复到以下命令面：

### 只读或通常只读

```text
help version bdinfo printenv coninfo
md cmp crc32 iminfo
ping
```

其中 `md` 只能读取当前地址空间；读取非法或外设映射地址仍可能挂死，现场仅从已知 RAM/flash 映射开始。

### 会改变RAM或临时环境，但默认不持久化

```text
setenv editenv run
mw mm nm cp loop base
tftpboot bootp loadb loads loadx loady
```

### 启动控制

```text
bootm booti go reset sleep
zxboot bootsecure
```

### 明确危险/持久写入

```text
saveenv
sf
nand write.raw[.noverify]
upgrade
zteboot_upgrade / zteboot_upgrade_burn
```

镜像中没有恢复出独立的 `mmc`/`usb` 文件系统救援命令证据。现场只读阶段禁止 `saveenv`、`sf erase/write`、`nand erase/write`、`upgrade` 和所有 burn 类入口。

## 3. 安全启动、AES/eFuse与验证链

已恢复的主干函数名：

```text
zteboot_verify_uboot
zteboot_verify_kernel
zteboot_verify_fs
zteboot_verify_header
zteboot_verify_boot
zteboot_verify_firmware
zteboot_verify_signature
up_mode_check_verify
secure_image_verify
```

启动路径能看到 `Verifying Checksum`、`Verifying Hash Integrity`、kernel magic、boot/kernel/fs/whole-firmware 校验及失败分支。硬件密钥链包含：

```text
The security aes secret key has been set!!!
Safety boot aes secrect key write protected!!!
Safety boot aes secrect key read protected!!!
AES KEY check fail!
AES KEY write and check PASS!
get KEY_RESTORE fail!
```

结合已完成的 rootfs 解密，量产 rootfs 使用镜像内可恢复的 AES-128-ECB 常量；eFuse/AES 链仍可能用于安全启动的另一层或密钥部署状态，不能把两者混为同一把密钥。

签名策略也不是一个全局开关：镜像同时存在 `zteboot_verify_signature` 和 `public_key inited but CSPBOOT_VERIFY_SIGN_XXX not enable`。这说明部分构建目标/镜像类型可以编译为不启用签名验证。升级层另有 `upgrade_key1/upgrade_key2` 与 CRC，并存在 `No need to check upgrade key` 分支。

当前可下的结论是：

- 原厂启动链一定做格式、magic、CRC/hash及AES相关处理；
- 非对称签名框架存在，但尚不能证明每种 `boot/image/version` 升级类型均强制签名；
- 在没有现场救援手段时，不制作或刷入自定义 kernel/rootfs 来试探策略。

## 4. tags与双槽状态

当前 `tags` 分区 SHA-256：

```text
30cea3389caac82db1828fa83db371d4277107e635a3ccfbe803e470bfb8cd5c
```

旧样本为：

```text
2c1479b5c05d65021f8863476e778ce8386c813cc0ff6297ef93b1e2d0c9cb6c
```

两者只有前 `0x1aa` 范围内84个字节不同。结构以 `3333` 魔数、总长 `0x2b0`、校验字段和一系列类型/长度/值记录开头。差异字段对应每台设备独有的无线SSID/口令、序列号及设备标识；公共型号、厂商和后续密钥材料保持一致。

敏感字段仅在本地样本中检查，本文不写入明文值。

结论：`tags` 是工厂身份/参数 TLV，不是活动槽记录。槽1/槽2的 U-Boot 正文逐字节相同；真正的启动槽、重试和回滚状态由 U-Boot 的 `bootpara` 结构及其保存逻辑管理。已确认相关入口：

```text
zteboot_update_bootpara
zteboot_save_bootpara
update bootpara first firmware
update bootpara second firmware
pon from the second time , should recovery the default data
```

但当前只读转储中尚未唯一定位持久化 `bootpara` 的所有字段偏移，所以不提供未经验证的“活动槽字节修改法”。

## 5. 恢复模式与升级入口

Bootloader 明确提供：

```text
Hit 1 to upgrade software version
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.100
tftp
upgrade.bin
upgrade boot
upgrade image
upgrade version
```

这构成串口触发的 TFTP 恢复/升级路径：路由器侧默认 `192.168.1.1`，TFTP服务器默认 `192.168.1.100`，默认文件名 `upgrade.bin`。`boot/image/version` 会走不同的烧写和验证分支。

Bootloader 字符串中没有 HTTP server、recovery Web 页面或救援Web监听实现的证据。因此 `/supgrade.html` 属于正常 Linux Web 管理层，不是 Bootloader 救援页。

恢复路径仍会检查header、CRC、upgrade key，并可能按构建选项检查签名。不能把任意二进制重命名为 `upgrade.bin` 后上传；也不在远程状态下测试升级入口。

## 6. 现场UART只读验证流程

设备当前不在手边，因此本项完成的是可执行检查单，硬件动作状态为**待现场**。

1. 使用3.3V TTL适配器，连接 `GND↔GND`、适配器TX→路由器RX、适配器RX←路由器TX；不接VCC。
2. 串口参数 `115200 8N1`，关闭硬件/软件流控。
3. 先开串口日志，再给路由器上电。
4. 在两秒窗口连续发送空格或回车；若出现菜单，先记录，不选择升级。
5. 若看到 `Hit any key to stop autoboot`，中断后只执行：

   ```text
   version
   bdinfo
   printenv
   help
   ```

6. 禁止执行：

   ```text
   saveenv
   nand erase/write
   sf erase/write
   upgrade
   resetenv
   ```

7. 若未进入 U-Boot 而启动到 Linux `login:`，可使用已在本机验证的 root 凭据；凭据只保存在受控本地记录，不在本文重复写明。
8. 若完全无输出，依次检查共地、TX/RX交叉、3.3V电平、引脚复用和是否需要板上GPIO/按键触发；不要转而尝试密码字典。

## 后续收敛点

下一轮最有价值的离线工作是定位 `zteboot_save_bootpara` 的flash写入目标与结构字段，并为它制作**只读解析器**。精确CSPBOOT debug触发则以现场UART日志为最短路径。
