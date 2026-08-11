# SR1010 cpeserver按需启动与认证逆向

日期：2026-08-07  
方式：当前B2固件静态逆向和数据库脱敏只读核验；没有触发设备搜索或启动cpeserver。

## 修正此前边界

`cpeserver`不是常驻监听服务。`cspd`内的`cpeServerMgrMain`是进程管理器，只有收到
`CMD_SEARCH_DEVICE`对应的`0x2906`事件才启动`/bin/cpeserver`；搜索结束、超时或停止事件
会回收进程。因此现场没有cpeserver进程/端口是正常待机状态，不代表功能未编入固件。

管理器还包含这些保护：

- 单次搜索消息最大4096字节；
- 已有cpeserver进程时忽略重复搜索请求；
- 保存子进程PID并处理退出事件；
- 运行超时后终止搜索进程。

本轮没有重放`0x2906`，因为它会主动扫描局域网设备，不属于纯只读现场核验。

## cpeserver传输层

独立`/bin/cpeserver`包含：

- `/etc/cpeserver/serverpkcs12.pfx`
- `/etc/cpeserver/ca-cert.pem`
- PKCS#12解析及TLS证书校验
- 普通搜索与`csSearchDeviceWithSSLPort`
- `CMD_SEARCH_DEVICE`状态机

也就是说它是一次性设备搜索/维护代理，不是Web或Shell登录服务。

## 实际认证来源

`CsAuthenticate`解析请求中的两个TLV：

```text
tag 0x00010023 -> username
tag 0x00010024 -> password
```

随后执行：

```text
dbAPIGetView("IGD.AU1", ..., "DevAuthInfo")
strcmp(request_user, stored_user)
strcmp(request_pass, stored_pass)
```

两项完全一致才设置全局`g_bIsAuthChecked=1`并返回认证成功。当前数据库脱敏核验显示：

```text
DevAuthInfo RowCount=1
ViewName=IGD.AU1
Enable=1
IsOnline=0
AppID=1
Level=1
```

用户名和密码值由数据库调试输出自动隐藏，未写入仓库。

## CpeDetectCfg的真实位置

这证明cpeserver服务端认证实际使用`DevAuthInfo`，不是`CpeDetectCfg`。后者更可能供发起
设备探测的一侧使用。hardcode中的`CpeDetectCfg.1.Pass`不能描述为cpeserver登录密码；
此前文档中“没有公开登录口”的结论成立，但原因现在更精确：服务按需启动，并有独立
DevAuthInfo TLV认证和TLS证书路径。

## 大白话意义

这个隐藏组件的用途是“临时启动一个带认证的局域网设备搜索器”，不是永久后门。它确实
可以从内部事件启动，但启动会产生主动扫描流量。当前没有必要为了证明它存在而现场触发；
软件层面的启动条件、证书路径、账号来源和比较逻辑已经恢复。

