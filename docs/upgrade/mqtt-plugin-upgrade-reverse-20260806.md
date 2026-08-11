# SR1010 当前 B2：MQTT、升级链与 Plugin 持久化逆向

日期：2026-08-06  
对象：用户自有 SR1010，固件 `V1.0.0.2B5.8000`  
方式：当前 NAND 转储静态分析 + LAN Telnet root 只读核验。未写 MTD、未安装插件、未发送伪造 MQTT 指令。

## 结论先行

1. **用 SR1010 取代 Asus 承担 WireGuard、Cloudflare DDNS 和默认网关，在软件上可行。** 当前设备有 `/dev/net/tun`、约 334 MiB 可用内存、`/Plugin` 约 39 MiB 可用持久空间，并自带 `ip`、`iptables`、`curl`。
2. 内核/模块中未发现 WireGuard，因此实施路径应是 **静态 ARM 用户态 `wireguard-go` + `wg`**，而不是等待内核模块。
3. 原厂 Plugin 机制本身就是合适的持久化入口：标准/旧式 IPK、`control` 中的 `StartCMD`/`StopCMD`/`StartMode`、`PluginInfo` 数据库记录以及开机 `PluginAutoStart`。
4. 目前还**不应直接拔掉 Asus**：SR1010 的 DHCP 仍把 `.2` 下发为默认网关；需要先把网关改成 `.1`，部署并重启验证插件，再做吞吐、断线重连、动态公网 IP 和掉电恢复测试。
5. MQTT 不是本项目需要依赖的持久化通道。它具有云端远程升级、插件安装和重启能力，扩大了管理面；本地插件自启动更可控。

## 样本指纹

| 文件 | SHA-256 |
|---|---|
| `/kmodule/bin/cspd` | `8b8477e2598660653c27d796fcaaa5484f879cd263fb6caa5e0a982b1cee5ac1` |
| `/kmodule/bin/mqtt` | `4afd7a47a324adbf2881e2c4265128f0d9c809ef4eeb68412542f839efa615a3` |
| `/bin/pluginmgr` | `a8e7a6773c8f1c41df7564f5e9525e3eca616516ce40c61d85b461f2f19602c` |
| `/kmodule/bin/fw_flashing` | `f3ae93f790d80cc44278b95015e266a4365b55dc8c9bb3dc52c94521f4fde5f2` |

## MQTT 逆向

`mqtt` 保留了完整符号。它不是简单遥测客户端，而是本地管理 RPC 与云 MQTT 的桥：

- 鉴权/发现：`_do_http_get_mqttserver`、`_mqttAuthComplite`、`mqttGetDevAuthInfo`；发现路径为 `/router/mqttserver?oid=%s`。
- 插件操作：`pluginAdd`、`pluginList`、`pluginSet`、`pluginOperate`、`GetPluginRuntimeInfo`，最终调用 `CmSetPluginInfo` 等本地 CM API。
- 固件操作：`CmUpgrade`、`upgradeVerAction`、`upgradeSpecifyVerAction`、`batchUpgradeVerAction`、进度查询和结果报告。
- 设备操作：包含重启、配置读写等 RPC 注册点。
- OTA 库主题：`/$ota/upgradenotify/%s/req`、`/$ota/upgradenotify/%s/resp`、`/$ota/upgrade/versionreport/%s`、`/$ota/upgrade/progressreport/%s`。
- OTA HTTP：`/device/getUpgradeVersionInfo`；结果上报还出现 `/api/v1/upgrade/report-result`。

实机进程为 PID 711，映射 `/kmodule/bin/mqtt`、`libmqtt.so`、`libmqttextend.so`。本轮没有发布、重放或伪造消息。工程选择是：**WG/DDNS 不依赖 MQTT；部署稳定后可另行关闭云 MQTT，并验证本地 Web/升级不受影响。**

## 固件升级验证链

升级分为“策略/完整性验证”和“实际擦写”两层：

### cspd（前置验证与状态机）

关键函数包括：

- `UpgradeCheckUpgradeFile`、`UpgradeCheckFirmware`、`UpgradeCheckFileIntegrality`
- `VerifySign`、`UpgradeVerifySignRegister`
- `Sec_verifyDigest`、`Sec_verify`
- `DsaVerify`、`dsa_verify_*`、`DsaPublicKeyDecode`
- `UpgradeCheckUpgradeKey`、`UpgradeCheckFirmwareUpgradeKey`
- `UpgradeSplitUpgradeFile`、`UpgradeFlashFirmware`

字符串明确包含 PEM 公钥边界、DSA 验证实现以及 `signlen is 0, do not verfy sign!`。后续逐指令复核已经确认：`VerifySign`读取到`sign_len=0`时直接返回成功，因此密码学签名层确实可被零长度跳过；但完整升级仍会校验产品/板型、版本、两个 `upgrade_key`、头部/内容 CRC和镜像布局，不能据此断言任意无签名文件都可刷写。详见[`upgrade-signlen-boundary-20260807.md`](upgrade-signlen-boundary-20260807.md)。

### fw_flashing / boot_flashing（实际写入）

- `fw_flashing` 直接打开 `/dev/mtd0`，按地址擦写、写入并回读校验。
- `boot_flashing` 检查 `upgrade_key1`、`upgrade_key2` 和 CRC；也有 `No need to check upgrade key` 分支。
- 密码学签名验证主要在 `cspd` 前置层，不应只看 flashing 小程序后得出“升级无签名”的结论。

对本项目的意义：**不需要通过固件升级链实现持久化**。Plugin 分区可写、可回滚，风险远低于改双槽或 MTD。

## Plugin 持久化协议

### 实机命名空间

宿主机：`/Plugin` 是 `/dev/mtdblock9` 上的 40 MiB JFFS2，当前约 1.1 MiB 已用。  
`pluginmgr` 在自己的 LXC mount namespace 中把 tmpfs 挂到小写 `/plugin`；PID 906（namespace PID 10）内可见：

- `/plugin/applist`：当前 `{"result":[{}],"status":0}`
- `/plugin/plugincfg`：带临时鉴权参数的官方插件目录 URL

因此 `/Plugin`（持久 JFFS2）与 `/plugin`（管理器容器视图）不可混为一谈；安装动作由 LXC/PC 接口把内容落到正确位置。

### 安装与启动格式

静态逆向得到的精确流程：

1. `IPKDownload` 建立 `/plugin/<name>/tmp`，用 curl 下载 `<name>.ipk`。
2. `IPKInstall` 执行 `opkg install <path>`。
3. `IPKGetInfo` 又用 `tar -zxvf <ipk> -C <plugin>/tmp/` 读取旧式 tar-IPK，删除临时 `data.tar.gz`，再解开 `control.tar.gz`。
4. 解析 `/plugin/<name>/tmp/control`，语法为 `%[^:]: %s`，识别字段：
   - `Version`
   - `StartCMD`
   - `StopCMD`
   - `StartMode`
5. 启动命令通过 `/bin/sh <StartCMD>` 运行；停止由 `StopCMD` 或进程终止路径处理。
6. 元数据写入 `PluginInfo`，开机 `PluginAutoStart` 查询数据库并启动相应插件。

官方目录当前列出节点小宝、蒲公英、UU、游帮帮、玩辰和自动更新的测速插件。目录下载使用 HTTPS 和短期 `scpsign/scptime/key1/key2` 参数；具体 IPK 另行申请逐 URL 的授权链接。安装阶段可见 MD5 比较，但未在 `pluginmgr` 中发现对 IPK 的独立公钥签名验证。

### 推荐自有插件结构

建议包名 `sr1010-netstack`，数据只落到自己的目录：

```text
/plugin/sr1010-netstack/
  bin/wireguard-go
  bin/wg
  bin/cf-ddns
  etc/wg0.conf            # 密钥从本地加密保险箱注入，不进 Git
  etc/ddns.env            # Cloudflare TOKEN 同上
  start.sh
  stop.sh
  health.sh
```

`control` 至少提供：

```text
Package: sr1010-netstack
Version: 0.1.0
Architecture: arm
StartCMD: /plugin/sr1010-netstack/start.sh
StopCMD: /plugin/sr1010-netstack/stop.sh
StartMode: 1
```

后续逐指令复核已确认 `StartMode=1` 就是自动启动值：`PluginAutoStart` 从 `PluginInfo` 读取记录后明确比较该字节是否等于1，命中才把 `StartCMD` 交给 `/bin/sh`。仍待hello插件实机验证的是数据库登记、容器路径和重启持久化整体效果，而不是枚举值本身。

## WireGuard 与 DDNS 实施判断

| 能力 | 当前证据 | 方案 | 判断 |
|---|---|---|---|
| WireGuard 数据面 | `/dev/net/tun` 存在；无内核 WG/模块 | ARM 静态 `wireguard-go` + `wg` | 可行，需测速 |
| 防火墙/NAT | 原厂 `ip`、`iptables` 齐全 | 专用链，幂等添加/删除 | 可行 |
| 持久存储 | `/Plugin` 可写，约 39 MiB 空闲 | 自有 IPK/plugin 目录 | 可行 |
| 开机启动 | `PluginAutoStart` + control 协议 | `StartMode` + DB 记录 | 高概率可行，待无副作用验证 |
| Cloudflare DDNS | `curl` 可用；自带 inadyn 未见 CF 能力 | 小型静态客户端或 shell+curl | 可行 |
| 默认网关 | DHCP 目前下发 `.2` | 配置改为 `.1`，保留回滚 BIN | 必须先改 |
| Wi-Fi | Asus 还提供 <EXISTING_WIFI_SSID> | 保留 ISP AP 或迁移 SSID | 需用户确认覆盖 |

WireGuard 的首选监听端口可复用当前 Asus 的 UDP `51283`，迁移窗口内必须先换成临时端口并并行验证，避免端口转发冲突。Cloudflare DDNS 应以“公网 IP 变化才更新”为原则，并把最后成功时间/返回码写入 `/Plugin/sr1010-netstack/state/`。

## 分阶段上线与回滚

1. **无副作用验证**：安装只写日志的 hello 插件，重启确认 `PluginAutoStart` 和 `StartMode`。
2. **DDNS 灰度**：新建测试 DNS 记录，验证 IP 变化、失败重试和重启恢复。
3. **WG 灰度**：临时 UDP 端口、单独 peer，确认握手、LAN 路由、MTU 和吞吐。
4. **网关迁移**：生成新的 config.bin，把 DHCP 网关 `.2` 改为 `.1`；保留原始配置和 Asus 在线。
5. **稳定性观察**：至少一次路由器重启、一次 WAN 重拨、一次 24 小时运行。
6. **下线 Asus**：确认 ISP AP 覆盖和所有客户端续租后再拔除。

回滚顺序：插回 Asus → 恢复 DHCP 网关 `.2` 的配置备份 → 停用/卸载 `sr1010-netstack` 插件。全程不触碰 kernel/rootfs/bootloader MTD。

## 下一步产物

- 构建 `sr1010-netstack` 的 hello 验证 IPK，确认真实落盘目录和 `StartMode` 枚举。
- 交叉编译与设备 ABI 匹配的静态 ARM `wireguard-go`/`wg`，先在 `/tmp` 运行。
- 编写幂等 `start.sh`/`stop.sh`/`health.sh` 和 Cloudflare DDNS 客户端。
- 从现有配置生成 DHCP 网关 `.1` 的候选 BIN，但在 WG 灰度通过前不导入。
