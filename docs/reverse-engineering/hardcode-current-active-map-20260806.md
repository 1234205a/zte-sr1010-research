# SR1010 hardcode 当前生效映射（脱敏）

日期：2026-08-06  
输入：本机解密后的当前B2配置与`enhardcodefile`；两份明文均未加入仓库。

## 为什么做这一步

hardcode库有209项跨产品通用秘密。此前只能证明“固件里存在”，不能证明SR1010正在用。
本轮停止继续钻PluginAutoStart细节，改为把hardcode键与当前配置逐项交叉引用。

新增[`tools/hardcode-active-map.py`](tools/hardcode-active-map.py)。工具只输出字段名及
`equal/different/absent`状态，绝不输出值。

## 当前结果

| 状态 | 数量 | 含义 |
|---|---:|---|
| `equal` | 5 | 当前配置值与hardcode默认值一致 |
| `different` | 2 | 当前配置存在该字段，但已覆盖默认值 |
| `absent` | 202 | 当前配置没有对应的完整字段路径 |

匹配到当前配置的七项：

| 字段 | 状态 |
|---|---|
| `CpeDetectCfg.1.Pass` | equal |
| `Sbus.CertKey` | equal |
| `Sbus.PskConnectKey` | equal |
| `UserIF.1.OpensslPassword` | equal |
| `UserIF.1.PKCS12CertkeySeed` | equal |
| `STAProfile.1.WPAPSK` | different |
| `WLANPSK.1.KeyPassphrase` | different |

这说明当前SR1010直接继承hardcode默认值的主要是内部SBus、证书容器和CPE探测相关字段；
当前Wi-Fi/STA密钥已经被设备配置覆盖。库中大量Telnet、TR-069、MQTT、摄像头和其他产品
密码只是通用库存，不能继续把“存在”写成“当前生效”。

## 直接代码调用点

ELF导入和ARM调用点复核得到两个清晰的字段使用者：

- `idm_service`直接请求`IDM.TLSPW`，输入文件为`/etc/enhardcodefile`；
- `passpppoe.so`直接请求`dataprotocol.ppp.OpensslPASSKEY`，输入文件同上。

`cspd`虽然保留`CspHardCodeParamGet`动态符号，但当前静态代码没有直接BL到对应PLT项，
更可能经包装函数、函数指针或产品初始化路径间接访问。不能据此声称其所有hardcode键已启用。

## 大白话意义

以前得到的是一大串“厂家可能用过的万能密码/密钥库”；现在已经把它压缩成当前设备真正
值得继续追的少数入口。后续优先分析SBus、IDM TLS和CPE探测，不再浪费时间逐个尝试202项
与本机配置无关的跨产品默认值。

