# SR1010 本地诊断、CPE 控制与远程命令链逆向

日期：2026-08-06  
固件：`V1.0.0.2B5.8000`

## 结论

当前固件存在三套容易混淆的管理链：

1. **本地调试总线**：`sendcmd` → `/var/tmp/<process>...` Unix datagram → `hadbgd`/各进程 debug table；
2. **厂商远程诊断**：`diagnose` → ZTE WebSocket → 无命令白名单的执行处理器 → `popen/PcStartProgram` → 回传结果；
3. **CPE 维护协议**：`cpeserver` 的组播发现、TLS/DTLS 会话、session key/checksum/TLV，支持 Telnet、Wi-Fi、升级、恢复出厂等动作。

本机当前 `DiagCfg.RemoteDiag=0`，远程诊断 WebSocket 没有建立；`cpeserver` 也没有作为独立进程运行。因此这些是**固件具备但当前休眠**的控制面，不是当前正在接受公网命令的服务。

## 实机监听端口与进程归属

通过设备定制 `/proc/net/tcp*` 的 PID/task 扩展字段直接确认：

| 端口 | 进程 | 含义 |
|---:|---|---|
| TCP 80/443 | `httpd` | 普通 Web 管理 |
| TCP 8085/8086 | `httpd` | 自定义 HTTP/HTTPS 管理监听；普通根路径重定向到 `notallowed.html` |
| TCP 23 | `telnetd` | 当前人为开启的 LAN Telnet |
| TCP 7777 | `mqtt` | MQTT 本地监听 |
| TCP 23002 | `idm_service` | IDM 设备管理服务 |
| TCP 23011 | `fttr_m` | FTTR 管理服务 |
| TCP 动态 52869 | `upnpd` | UPnP HTTP 服务 |

`mqtt` 同时连接远端 `39.108.160.143:31808`。当前列表没有 `cpeserver` 的独立监听，也没有 `diagnose` 的外连 WebSocket。

`httpd` 的 8085/8086 对 `/` 返回 307，目标为 `http://192.168.50.1:8085/notallowed.html`；这表明端口活着，但另有来源、Host、路径或模式限制。

## 本地 sendcmd / hadbgd 总线

`sendcmd` 是厂商统一调试客户端，支持按进程/任务寻址，例如二进制自带示例：

```text
sendcmd cspd..DB p
sendcmd diagnose..remote_diag setDiagEnable 0
```

运行时存在：

```text
/var/tmp/hadbgd.hadbgd_asy
/var/tmp/hadbgd.hadbgd_snd
/var/tmp/hadbgd_oam
/var/tmp/diagnose.remote_diag_asy
/var/tmp/diagnose.remote_diag_snd
```

以及每个 `cspd/httpd/mqtt/pluginmgr/telnetd` 任务的 `_asy`、`_snd` 和 OAM socket。`hadbgd` 只保留 `_ShowAllCmd`、`_DealDebugMsg` 和 `g_DebugProcTable`，本身主要是调试消息路由器；真正命令由各进程注册。

当前已经是 root，因此该总线可用于无网络副作用的状态读取；任何带 set/reset/upgrade 的命令仍需单独判定，不进行盲跑。

## diagnose：远程命令执行链

配置表：

```text
DiagCfg.RemoteDiag = 0
DiagConnection.Url = diagnosis.ztehome.com.cn
DiagConnection.Port = 443
DiagConnection.Path = /diagnosisTunnel/SN/
DiagConnection.EnableEncryption = 1
```

`diagnose` 保留完整连接和消息函数：

- `DiagnoseConnBuild/Setup/SendReq/SendPing`
- `__DiagnoseConnClientReceive`
- `DiagnoseRemoteHdlMsg`
- `__DiagnoseRmtHandleCmd`
- `DiagnoseHandlerSetDiagnosisMsg`

远程命令处理器明确包含：

```text
use popen to run sendcmd -pc cmd
use popen to run sendcmd redirect cmd
use popen to run sendcmd shellscript cmd
/var/tmp/cmdres
```

对 `__DiagnoseRmtHandleCmd`（`0x15218`，长度 `1092` 字节）的逐指令复核纠正了上一版结论：日志虽然使用 `__DiagnoseRmtCmdCheck`、`__DiagnoseCmdCompare` 作为函数名字段，但处理器内**没有命令白名单、拒绝表或比较结果 gate**。实际分流如下：

1. 命令包含 `" -pc "`：直接 `popen(command, "r")`；
2. 命令包含 `>` / `" >> "`：直接 `popen(command, "r")`；
3. 命令包含 `.sh`：直接 `popen(command, "r")`；
4. 其他命令：拼成 `"%s > %s"`（输出文件 `/var/tmp/cmdres`），只检查首个程序名长度不超过 `0x3f`，随后调用 `PcStartProgram(program, full_command, 0, 0)`。

前三条会把收到的完整命令原样交给 shell；普通分支也提供带参数及输出重定向的程序启动能力。处理完成后读取输出并回传，函数固定返回 `1`。因此它在命令层面是**通用远程 OS 命令执行原语**，而不是受限的厂商诊断命令集合。

边界仍需区分：上游 `__DiagnoseConnClientReceive/DiagnoseRemoteHdlMsg` 可能在消息进入该处理器前执行 WebSocket 会话、协议字段或身份校验；当前配置 `RemoteDiag=0`，实机也没有建立该外连。下一步应逆向上游消息 schema、鉴权和启用来源，而不是继续寻找实际不存在的命令白名单。

### 本轮未完成项

“继续深挖厂商远程诊断 WebSocket 的上游鉴权和完整消息协议”本轮没有完成，已按用户要求跳过：

- 已确认接收路径会解析 JSON 的 `params` → `ParamList` → `cmdId`，并将 `cmdId` 通过内部事件 `EV_WEBSOCKET_RMT_DIAG` 送往 `diagnose.remote_diag.remote_diag`；
- 尚未完成 WebSocket 建连请求、云端身份凭据、TLS/应用层鉴权以及 `RemoteDiag` 启用来源的闭环；
- 一次反汇编文本区间提取把相邻 literal pool 当成 ARM 指令，产生了无效的 `andeq/strheq` 输出；修正函数边界后已取得真实 `DiagnoseRemoteHdlMsg` 指令；
- 随后一次命令错误地使用 Bash heredoc（`python - <<'PY'`），在 PowerShell 下触发语法错误。该错误没有修改样本或仓库；
- 因此不能据现有证据声称“云端无需身份验证”。可确定的范围仅是：命令进入 `__DiagnoseRmtHandleCmd` 后不存在命令白名单。

后续若恢复该任务，应从 `DiagnoseConnBuild/Setup`、libwebsockets 连接参数和 `__DiagnoseConnClientReceive` 入手，不重复执行错误的文本切片流程。

## cpeserver：维护协议状态机

`cpeserver` 没在当前进程表中，但二进制功能完整：

- 组播发现和 `CMD_SEARCH_DEVICE`；
- `CMD_SAYHELLO` 后建立 session key；
- 消息头含 `Id/Key/Rtn/CMD/Args/Length/Check_sum`；
- `CsAuthenticate` 和全局 `g_bIsAuthChecked`；
- PKCS#12 设备证书与 CA，字符串标明 `DTLSv1_2`；
- `WRONG MSG KEY`、重复消息、版本和 checksum 检查。

状态机：

```text
DISCONNECTED -> CONNECTING -> IDLE
                           -> DOWNLOAD -> WRITEFLASH -> WAITAFFIRM
                           -> TEST
```

已确认动作：

- `CsTelnetOperate` / `CsStartTelnet`
- `CsWifiOperate`，读写 SSID/PSK/WAN mode
- `CsDownUpgrade`，支持 boot/config/software/CA_OPTEE 类文件
- `CsResetFactory`
- USB、按键、产品测试
- LAN IP 设置与维护模式

协议会从 hardcode/config 获取 `cpeserver.0.pkcsCertSeed` 以加载 `/etc/cpeserver/serverpkcs12.pfx`。这进一步证明上一阶段 hardcode 解密结果不仅是历史遗留字典，而是部分当前组件的实际密钥来源。

## cmd：云升级命令执行器

`cmd` 不是交互 shell，而是云固件/版本管理状态机：

- WebSocket TLS 客户端；
- `/var/tmp/newver.bin`；
- 批量升级、版本回滚、升级进度；
- `NeedResetCfg` 决定升级后是否重置配置；
- `CmSetRemoteUpgrade4Cmd` 与本地 CM API；
- debug 开关包括 `ssldebug`、`wsdebug`、`remoteDiagSwitch`、`setupgflg`。

当前 `cmd` 进程存在，但 `/proc/net/tcp` 未显示它持有外连或监听 socket；云升级消息也可通过 MQTT/本地消息总线转交。

## 当前风险排序

1. **已开启 Telnet root**：当前明确可用，但仅 LAN/WG 路径。
2. **MQTT 云通道**：当前建立外连，并具有升级/插件/重启动作。
3. **HTTP/IDM/FTTR 监听**：当前真实开放，需继续解析认证。
4. **diagnose 远程 popen 链**：能力强，但 `RemoteDiag=0` 且无外连。
5. **cpeserver**：能力强，但当前没启动。

## 下一步

1. 逆向 `diagnose` 命令检查函数，恢复完整允许/拒绝规则。
2. 从 `CsAuthenticate` 还原 cpeserver 握手、session key 和消息结构。
3. 解析 IDM 23002、FTTR 23011、MQTT 7777 的首包与认证状态机；只做连接/被动读取，不发送状态修改命令。
4. 导出各进程 `g_*DebugProcTable`，建立可重复的只读命令清单。
