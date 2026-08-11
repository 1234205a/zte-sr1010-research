# SR1010 厂商 hardcode 参数库完整解密

日期：2026-08-06  
固件：`V1.0.0.2B5.8000`

## 结论

`/etc/enhardcodefile` 和 `/etc/enwebdhardcodefile` 已完整解密。算法已实现为 [`tools/hardcode-decrypt.py`](tools/hardcode-decrypt.py)。明文包含大量厂商密码、AES 密钥、API secret 和一把 Web RSA 私钥，因此**明文产物只保留在本地分析目录，不提交 Git**。

## 算法

从 `libhardcode.so` 的完整符号和 ARM 指令还原：

```text
model = strip(read("/etc/hardcode"))
material = model + "0x0510" + "0x0001"
key = zero_pad(material, 32)
plaintext = AES-256-ECB-decrypt(ciphertext, key)
```

SR1010 当前 model 是 `SR1010_QD`，所以密钥材料顺序为：

```text
SR1010_QD0x05100x0001
```

此前第一阶段记录的常量顺序来自默认包装函数，未区分 Web 包装器的参数入栈顺序；实测和 `CspHardCodeParamWebdGet` 指令共同确认上述顺序才是当前两份文件所用顺序。

## 解密产物指纹

| 文件 | 明文长度 | 明文 SHA-256 | 内容 |
|---|---:|---|---|
| `enhardcodefile` | 9362 | `b2b1a74c7eb2863db9d1ed88e33de8def6b12d4b641204bd7879371ff6f0a212` | 209 行通用产品硬编码参数 |
| `enwebdhardcodefile` | 1704 | `1ec3a7b61ca1c484cee6fb983aa9c32b6a818d8c6ead2f6aa867df28824931be` | 2048-bit RSA 私钥 PEM |

RSA 公钥 SPKI SHA-256：

```text
cd5c5b7731b1ccf673e862d5df51bb81db29373a57f6a184cbc6c63f40541e7d
```

## 参数库包含什么

这不是只为 SR1010 制作的最小文件，而是跨大量 ZTE 产品/运营商配置复用的通用秘密库。字段类别包括：

- `TelnetCfg.0.Passwd`、多个产品的 root/CLI/SSH/FTP/Web 默认密码；
- `DevAuthInfoUser.*.Password` 和多用户默认凭据；
- MQTT CBC key/IV/TLS 口令；
- TR-069 管理服务器密码、Connection Request 密码和 PKCS#12 口令；
- 配置、Tag/TagParam、Wi-Fi 密码使用的 AES key/IV；
- 云 API app secret、access key、client secret；
- IPsec、SBus、IDM、syslog、摄像头等组件的密钥或证书口令。

这些值并非全部在 SR1010 当前配置中启用。`CspHardCodeParamGet` 按字段名取值，产品代码/默认配置决定实际使用哪一行。后续要把 `cspd/httpd/telnetd/mqtt` 的每个取值调用点与字段名交叉引用，建立“存在”与“当前生效”的区别。

## Web RSA 私钥的意义

`httpd` 的 `CspHardCodeParamWebdGet` 在运行时：

1. 从 `/etc/hardcode` 取得 model；
2. 构造上述 AES key；
3. 解密 `/etc/enwebdhardcodefile` 到带 PID/TID 的临时文件；
4. 读取 RSA 私钥后删除临时文件。

这说明 Web 登录 proof/密钥交换依赖的是固件内可恢复的静态 RSA 私钥，而不是设备唯一硬件密钥。获得固件即可离线恢复它。接下来需要把该私钥在 `webLoginApLogin/webLoginApCheck` 中的具体用途和客户端 JavaScript 完整对齐。

## 工具使用

默认只向屏幕输出字段名或“RSA private key present”，不打印值：

```powershell
python sr1010/tools/hardcode-decrypt.py INPUT `
  --model-file ETC_HARDCODE `
  --inventory REDACTED_OUTPUT
```

需要本地明文分析时显式加 `--plaintext LOCAL_SECRET_OUTPUT`。该文件不得加入仓库。

## 下一步

1. 枚举所有 `CspHardCodeParamGet` 调用及其字段名，生成当前 SR1010 生效映射。
2. 还原 Web RSA proof、session、CSRF 和角色校验。
3. 确认 `TelnetCfg.0.Passwd` 如何进入 Telnet 登录状态机，以及是否存在其他休眠账号。
4. 对 Tag/TagParam、MQTT、TR-069/USP 的硬编码字段逐一验证。

