# SR1010 SBus、IDM TLS 与 CPE 探测实机边界

日期：2026-08-06  
方式：固件静态逆向、`/proc`只读核验和一次空TLS握手；未修改配置、未重启、未发送业务消息。

## 结论

hardcode生效映射指向的三组组件不是同一种入口：

- **SBus**是正在运行的加密设备发现/服务总线，使用三个UDP端口和本地Unix socket；
- **IDM**是正在运行的Mesh设备管理TLS服务，TCP 23002监听所有IPv4地址，但强制客户端证书；
- **CpeDetectCfg**当前只是`cspd`内`cpeserver_mgr`使用的配置项，没有发现独立cpeserver进程或对应监听口。

## 运行时端口和进程

| 组件 | PID/进程 | 监听/IPC | 证据 |
|---|---|---|---|
| SBus adaptor | 612 `sbusd-adaptor` | OSS sockets + adaptor IPC | 运行中，启动事件已执行 |
| IDM | 615 `idm_service` | TCP `0.0.0.0:23002` | `/proc/net/tcp` inode 6639归属PID 615 |
| SBus daemon | 730 `sbusd` | UDP `0.0.0.0:15683-15685` | inodes 6032/6033/6034归属PID 730 |
| USP | 948 `uspd` | 本地OSS/Unix IPC | 与本轮hardcode字段不是同一协议 |

关键Unix socket包括：

```text
/var/tmp/sbus_unix_socket
/var/tmp/service_unix_socket_IDM_MASTER_DEV
/var/tmp/service_unix_socket_IDM_SLAVE_DEV
/var/tmp/sbusd-adaptor.exec*_snd/asy
```

iptables/ip6tables中没有针对23002或15683-15685的端口专用规则；它们依赖接口绑定、协议
认证和上层WAN默认丢弃策略，而不是单独端口规则。

## IDM TLS

静态调用点确认服务器使用：

- `/etc/idm_ca.crt`
- `/etc/idm_server.crt`
- `/etc/idm_server.key`
- hardcode字段`IDM.TLSPW`作为私钥口令
- `SSL_CTX_set_verify(..., 3, callback)`

OpenSSL verify模式`3`即`SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT`。从当前WG/LAN路径
连接TCP 23002成功，但不提供客户端证书的TLS握手立即收到`handshake failure`，与静态结论一致。
因此它不是“知道端口即可调用”的明文管理接口。

服务器禁用了RC4、SHA1、NULL和一组旧/指定套件，但仍使用固件中的OpenSSL 1.0兼容库。
IDM消息层包含`MsgType`、请求/响应JSON和MASTER/SLAVE设备角色，主要服务于Mesh AP控制。

## SBus

`/etc/sbusd_info.json`实机读取后只记录脱敏结构：

```text
encrypEnable=1
version=1
devType=3
ca_path/cert_path/key_path present
```

二进制显示它使用CoAP/CoAPS、mbedTLS、DTLS、AES-CTR/CBC、SHA-256和Base64，具有发现、
连接、启动服务、发布服务和响应消息动作。三个UDP监听端口属于该daemon；本地控制通过
`sbus_unix_socket`与adaptor交互。

当前配置中的`Sbus.CertKey`与`Sbus.PskConnectKey`仍等于hardcode默认值。这是当前最值得
继续审计的共享认证材料，但“默认值仍生效”不等于协议无认证：实机配置明确开启加密，
代码同时存在PSK和证书/DTLS路径。

## CPE探测

`CpeDetectCfg.1.Pass`仍等于hardcode值，但现场没有`cpeserver`进程或`cpeserver_oam` socket。
`cspd`内部存在`cpeserver_mgr`模块，说明功能被编入主进程，而不是独立守护程序。当前没有
证据把该字段对应到一个对LAN/WAN开放的监听端口，后续应从`cpeserver_mgr`事件和调用点追踪，
不应直接把它描述成可登录账号。

## 大白话意义

本轮把七个“可能生效的hardcode字段”进一步分流：IDM端口真实存在但有双向TLS；SBus真实
存在且是加密的局域网设备总线；CPE密码目前没有对应的公开登录口。下一步优先恢复SBus的
CoAP资源路径和PSK派生，而不是尝试一大批默认密码。

