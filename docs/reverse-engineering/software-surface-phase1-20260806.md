# SR1010 全软件面逆向：第一阶段盘点

日期：2026-08-06  
固件：`V1.0.0.2B5.8000`

## 本阶段范围

WG/DDNS 暂停，转为对当前固件全部软件面的系统盘点。当前 `kmodule.img` 已完整转成 941 个普通文件；Windows 无法建立其中的 Unix 符号链接，但不影响真实 ELF 样本。共识别 **266 个 ELF**。

新增批量工具：[`tools/elf-surface-scan.py`](tools/elf-surface-scan.py)，按认证、命令执行、隐藏/调试、升级、云管理、恢复模式和密码学分类提取证据。

## 高优先级目标排序

1. `httpd`：Web 登录、权限、隐藏页面、TR-069、USP、配置上传、升级入口。
2. `cspd`：所有配置数据库、进程管理、固件校验、账号和硬编码解密的核心。
3. `telnetd`：独立账号校验、CLI/root shell 切换、密码修改/删除接口。
4. `cmd` / `cpeserver`：诊断命令、远程 CPE 操作、Telnet 和恢复出厂控制。
5. `mqtt` / `libupgrade_service` / `pluginmgr`：上一阶段已完成主调用链，后续补齐消息格式和权限来源。
6. `libhardcode.so` + `/etc/enhardcodefile` + `/etc/enwebdhardcodefile`：厂商硬编码参数库。
7. bootloader/tags：启动槽、回滚、debug 触发和串口控制。

## 新确认的认证与串口事实

- Linux 实际 root 用户名是 `Z500_w9bZ`，UID/GID 0；Telnet 层把输入的 `root` 映射到该账号。
- `/etc/shadow` 使用 `$5$`（SHA-256 crypt）保存系统 root 哈希；Telnet 还存在自己的 `TelnetCfg` 数据库和独立登录状态机。
- `telnetd` 有完整符号：`ForkChildProAndEexcShell`、`SwitchToShell`、`CmDebugChangePassword`、`CmDebugDeletePassword`、`CmSetTelnetdCfg`。
- 登录成功后可在厂商 CLI 与真正 `/bin/sh` 间切换；现有 LAN root 闭环走的是 shell 路径。
- `/etc/inittab` 无条件 `respawn:/sbin/getty ttyAMA0 115200`。内核命令行同时含 `console=ttyAMA0,115200n8` 和 `serial=close`：Linux 用户态仍配置了串口 getty，但 bootloader/板级逻辑可能用 `serial=close` 控制早期输出。
- bootloader 环境仍为 `bootdelay=2`、stdin/stdout/stderr 为 serial；当前 bootloader 明文只出现 `Trigger debug mode !`，没有密码提示。Bootloader 密码尚不能判定为“存在”；需从 debug 触发分支反向追踪，而不是继续猜字典。

## 硬编码参数库

`libhardcode.so` 保留完整符号：

- `CspHardCodeEncry` / `CspHardCodeDecry`
- `CspHardCodeEncryDefaultKey` / `CspHardCodeDecryDefaultKey`
- `CspHardCodeParamGet`

已还原默认密钥字符串构造：

```text
"0x0510" + strip(/etc/hardcode) + "0x0001"
```

本机 `/etc/hardcode` 为 `SR1010_QD`。后续对 Web 包装器的参数入栈顺序和实测共同确认，当前两份加密文件使用的材料是：

```text
SR1010_QD0x05100x0001
```

库将其复制进 33 字节零化缓冲区并调用 `AES_set_decrypt_key(..., 256)`，数据按最多 `0x400` 字节读取并以 16 字节块 ECB 解密。两份文件现已完整解密，详见 [`hardcode-library-reverse-20260806.md`](hardcode-library-reverse-20260806.md)。

## Web 管理面

`httpd` 约 2 MiB 且保留符号，已定位：

- `funcs_login`、`funcs_handleLoginError`
- `webLoginApLogin`、`webLoginApCheck`、`webLoginCheckProof`
- `_parseXXSRFTOKEN`、`_parseAuthorization`
- `SetLogin`、`SetUserInfo`、`QueryUserInfoByCond`
- `CspHardCodeParamWebdGet`
- TR-069 Digest Auth、下载/上传账号设置、远程恢复出厂
- USP Controller/Subscription/Transport 调试与命令注册树

登录前端已知协议仍是：随机 `logintoken`，客户端提交 `SHA256(明文密码 + logintoken)`；本阶段将继续还原服务端 proof、会话、CSRF 和角色检查。

## 运行时暴露面

当前关键进程：`cspd`、`httpd`、`telnetd`、`mqtt`、`upnpd`、`cmd`、`diagnose`、`hadbgd`、`uspd`、`phddns`、`pluginmgr`、`multiapd`。还存在 `cpeserver`/TR-069/USP 的代码与证书，即使某些功能当前未单独显示为进程，也可能合并在 `httpd` 或由 `pc/cspd` 调度。

设备节点权限非常宽：`/dev/mem`、`/dev/kmem`、全部 `/dev/mtd*` 对 root 可读写。这意味着现有 root 已是完整软件控制权；后续逆向重点是协议、密钥、恢复/升级和可重复工具，而不是继续寻找更高的 Linux 权限。

## 后续执行顺序

1. 解出 `enhardcodefile`/`enwebdhardcodefile`，枚举隐藏账号、服务开关和服务器常量。
2. 完整还原 Web 登录 proof、角色/ACL、隐藏 API、TR-069/USP 权限边界。
3. 还原 `cmd`、`cpeserver`、`hadbgd`、`diagnose` 的本地消息协议和命令表。
4. 解析 tags/bootloader 变化块、活动槽/回滚字段和 debug 触发条件。
5. 完成 MQTT 消息 schema、升级容器格式和签名策略矩阵。
6. 将各解析器合并进统一 SR1010 分析工具。
