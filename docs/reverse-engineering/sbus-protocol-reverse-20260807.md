# SR1010 SBus CoAP资源与PSK派生逆向

日期：2026-08-07  
对象：当前B2固件`sbusd`；本轮为离线静态逆向，没有向UDP端口发送发现或控制报文。

## 协议资源

SBus不是普通Web接口，而是一套ZTE设备发现和服务调用总线：

| 用途 | 资源/地址 |
|---|---|
| 局域网发现 | `coap://239.255.255.250:PORT/device_discover` |
| 加密连接 | `coaps://ADDRESS:PORT/connect` |
| 服务消息 | `coap://ADDRESS:PORT/RESOURCE?msgId=NUMBER` |
| 本地daemon IPC | `/var/tmp/sbus_unix_socket` |

发现JSON包含这些字段：`ipv4Addr`、`ipv6Addr`、`vendor`、`deviceName`、`deviceSN`、
`macAddr`、`deviceId`、`version`、`accountHash`、`protocol`、`devType`、`serviceTag`、
`deviceModel`、`capability`、`profile`和`serviceList`。服务条目含`serviceName`、
`serviceUUid`、`authType`及`custData`。

当前daemon拥有UDP 15683、15684、15685；代码同时支持CoAP、CoAPS/DTLS、单播与组播。
`CoapAddMsgResource`明确把`connect`注册为POST处理资源；`device_discover`用于发现发布。

## 连接消息

连接/服务状态机的JSON外壳包括：

```text
msgId, dest, action, data, version, errCode, errMsg
```

已识别动作：

- `connect`
- `startService`
- `sendCommonMsg`
- `sendCommonMsgResponse`

本地服务通过`serviceUUid`匹配，连接成功后才进入启动服务和通用消息阶段。

## PSK派生

`SbusLoadDeviceCfgInfo`从当前SBus配置取得`PskConnectKey`，交给
`CoapConnectSetPskEncryKey`。后者保存输入并调用`CoapConnectSetNewPskKey`：

```text
material = first_16_characters(PskConnectKey) || DEVICE_BINDING
derived  = SHA256(material)
```

继续逐字段对齐`CoapAddDeviceJsonData`后已经确认，设备信息结构`+0x82`对应JSON字段
`deviceId`，不是`deviceSN`或`accountHash`。因此准确算法是：

```text
material = first_16_characters(PskConnectKey) || deviceId
derived  = SHA256(material)
```

32字节SHA-256结果随后被拆成前后两个16字节块，送入SBus的AES-CTR连接载荷处理。
新增[`tools/sbus-psk-derive.py`](tools/sbus-psk-derive.py)复现KDF；默认只输出指纹，
`--show-derived`才显示派生结果。PSK和设备绑定值必须从本地保险箱/现场输入，不进入Git。

## 边界修正

上一阶段确认当前`Sbus.PskConnectKey`仍等于hardcode默认值，但协议还把它和设备字段绑定后
做SHA-256，并非直接把配置字符串当作网络密钥。发现报文会暴露设备元数据，但控制路径仍
有派生密钥、CoAPS/DTLS和服务UUID状态机。

## 下一步

端口分工也已由`CoapSetPort`和URI构造函数精确恢复。配置给出基础端口，函数连续设置
`base/base+1/base+2`；当前默认基础端口为15683：

| 端口 | URI字段 | 角色 |
|---:|---|---|
| 15683 | `coapUri` | `device_discover`普通CoAP发现 |
| 15684 | `connectUri` | `coaps://.../connect`证书/DTLS连接 |
| 15685 | `connectUriPsk` | `coap://.../connect`PSK保护连接 |

## 下一步

新增[`tools/sbus-coap-decode.py`](tools/sbus-coap-decode.py)，可离线解析CoAP头、token、
扩展option、URI-Path和JSON payload。默认只显示JSON结构和数据类型，只有显式
`--show-values`才显示值。工具只读本地文件或hex字符串，没有socket代码，不会误发报文。

进一步交叉引用确认`accountHash`在`sbusd`内只作为`g_localDeviceInfo+0x145`字段序列化；
当前二进制没有生成它的函数，`sbusd-adaptor`也没有该字段名。它由上游设备基础信息接口
填入，因此算法边界位于`libsbus_adaptor.so`或其产品回调，而不在`sbusd`主程序。下一步
转查该库的设备基础信息回调，再决定是否需要一次只读组播发现实测。
