# SR1010 远程诊断 WebSocket 上游鉴权与消息协议分析

日期：2026-08-06
二进制：`diagnose`（当前 `V1.0.0.2B5.8000`，71,008 字节，ARM32 stripped）
方式：ELF节表解析 + 字符串交叉引用 + 已有反汇编 + 配置表核对

## 核心结论

**不是"云端无需鉴权"，而是"鉴权在连接层完成，命令层不做二次校验"。**

三层安全边界：

| 层 | 机制 | 结论 |
|---|---|---|
| TLS mutual auth | 设备有客户端证书，连 `diagnosis.ztehome.com.cn:443` 时做双向 TLS | 存在，TLS 握手不过就断 |
| 设备身份注册 | JSON-RPC `Init` 消息上报 MAC、序列号、型号、固件版本 | 存在，服务器据此决定是否接受连接 |
| 命令级校验 | 收到 WebSocket 消息后直接提取 `cmdId` → `popen` 执行 | 不存在任何命令白名单 |

**所以：如果你有合法的 TLS 客户端证书 + 知道设备序列号/MAC，你就可以远程在这台路由器上执行任意命令。但如果缺其中一环，连 WebSocket 都建不起来。**

此前 Commit b821247 的结论"下游命令处理器无白名单"仍然正确，但需要补充的是连接层有双向 TLS 保护。

---

## 连接建立流程

```
读取配置表:
  DiagCfg.RemoteDiag → 1/0
  DiagConnection.ViewName = "DEV.WS1"
  DiagConnection.Url = diagnosis.ztehome.com.cn
  DiagConnection.Port = 443
  DiagConnection.Path = /diagnosisTunnel/SN/   (SN = 序列号动态替换)
  DiagConnection.EnableEncryption = 1
       |
DiagnoseConnBuild → DiagnoseConnSetup
       |
__DiagnoseConnCreatContext
  → lws_create_context(TLS_certs)
  → lws_client_connect_extended(wss://diagnosis.ztehome.com.cn:443/diagnosisTunnel/<DEVICE_SERIAL>/)
       |
TLS 握手 (双向, 含客户端证书)
       |
LWS_CALLBACK_CLIENT_ESTABLISHED  →  发送 Init:
  {"params": {
    "configuration": "...",
    "type": "ZXSLC SR1010",
    "version": "V1.0.0.2B5.8000",
    "protocolVersion": "1.0",
    "mac": "<DEVICE_MAC>",
    "serialNumber": "<DEVICE_SERIAL>",
    "odm": "...",
    "areaCode": ""
  }, "jsonrpc": "2.0", "method": "Init"}
       |
服务器验证通过 → WebSocket 保持 → 可收远程命令
```

## 消息接收路径

```
WebSocket 收到消息
  → LWS_CALLBACK_CLIENT_RECEIVE
  → __DiagnoseConnRcvPacket  (JSON 解析)
  → 查 params.ParamList:
       |-- 有 "Primary" → 设备自检模式 → DiagnoseHandlerSetDiagnosisMsg
       └-- 有 "cmdId"   → 远程诊断模式 → 先构建返回 {"status":0, "id":<counter>}
                                         然后 DiagnoseRemoteHdlMsg
```

## DiagnoseRemoteHdlMsg 内部

```
params.ParamList.cmdId.valuestring → 提取 cmdId 字符串
  → 日志 "cmdId = %s"
  → 发送内部事件 EV_WEBSOCKET_RMT_DIAG
    目标: "diagnose.remote_diag.remote_diag"
  → 该事件触发 __DiagnoseRmtHandleCmd:
     |-- 含 " -pc " → popen(cmd)
     |-- 含 ">" 或 ">>" → popen(cmd)
     |-- 含 ".sh" → popen(cmd)
     └-- 其他 → 检查程序名长度≤63 → PcStartProgram
```

**全程没有任何地方检查 cmdId 是否在白名单里，也没有检查消息签名。**

---

## TLS 证书来源

`diagnose` 二进制使用 libwebsockets 的以下 TLS 参数：
- `LWS_SSL_CLIENT_CA_CERTS` — CA 证书（验证服务器）
- `LWS_SSL_SERVER_CERTS` — 客户端证书（设备自己的）
- `LWS_SSL_SERVER_KEYS` — 客户端私钥

这些证书的种子/口令来源不在 `diagnose` 二进制本身。通过硬编码库 (`enhardcodefile`) 交叉引用：
- 仅 `Camera_DiagConnection.0.TLSPW=toc12zte`（摄像产品线），SR1010 无直接对应字段
- `cpeserver.0.pkcsCertSeed=8cc72b05705d5c46f412af8cbed55aad` 是 CPE 维护协议的 cert seed，不是诊断通道
- `UserIF.1.PKCS12CertkeySeed=8cc72b05705d5c46f412af8cbed55aad` 是 Web HTTPS 证书种子

因此 TLS 证书可能来自固件预置的 `/etc/` 证书文件，或通过 `lws_context_creation_info` 传入的运行时路径。

---

## RemoteDiag 启用来源

当前配置 `RemoteDiag=0`，可被以下途径修改：
1. 配置表写入（config.bin 重打包）
2. `sendcmd diagnose..remote_diag setDiagEnable 1`（本地调试总线）
3. MQTT 云通道下发（`cmScpDiagnoseSetCfg` 函数存在但当前未建立外连）
4. 隐藏 Web 管理页（`/supgrade.html`）

---

## 安全判定

| 场景 | 是否可行 |
|---|---|
| 外网任意 IP 直接连诊断 WebSocket | 需有效 TLS 客户端证书 |
| ZTE 云端服务器连设备 | 若 TLS 证书产品线通用，ZTE 拥有该证书 |
| 局域网攻击者连诊断 WebSocket | RemoteDiag=0 时不启动连接 |
| 改配置打开 RemoteDiag 后 | WebSocket 启动，但证书要求同上 |
| MQTT 云通道远程启用诊断 | MQTT 已是有效会话，能发 cmScpDiagnoseSetCfg |

---

## 未完整闭合项

1. TLS 客户端证书的具体文件路径/种子未被恢复（不在 `diagnose` 二进制本身，也不是硬编码库的标准字段）
2. 服务器侧的设备号验证逻辑未知
3. 若证书是产品通用，整条产品线共用同一组 mTLS 凭据；若设备唯一则每个设备独立
