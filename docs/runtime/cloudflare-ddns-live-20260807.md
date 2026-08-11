# SR1010 Cloudflare DDNS正式上线

日期：2026-08-07

## 当前结论

SR1010已独立维护新的灰云DNS记录：

```text
hostname = sr1010.example.invalid
type     = A
TTL      = 60
proxied  = false
IPv4     = PUBLIC_IP_B（部署时）
record   = 297fc40aa606620d93a7c0edf6f92868
```

Cloudflare API和Cloudflare DoH都返回同一个IPv4。此记录与现有`legacy-router.example.invalid`并存，
所以后续SR1010 WireGuard测试不会破坏Asus回退通道。

## DNS与凭据来源

- zone：`example.invalid`；
- zone id：`cb28317e31f640135503e3c2c2e5fc7a`；
- 使用私有运维资料中已有的Cloudflare DNS编辑Token；
- Token没有写进本报告、构建器或新Git提交；
- 设备端只保存在`/opt/sr1010-cf-ddns/config/curl-auth.conf`，权限0600；
- curl通过0600配置读取Authorization header，Token不出现在curl命令行参数中。

## 插件

新增确定性构建器：[`tools/build-cf-ddns-ipk.py`](tools/build-cf-ddns-ipk.py)。

完成PID归属和日志轮转修正后的规范包：

```text
Package=sr1010-cf-ddns
Version=0.1.0
StartMode=0
IPK bytes=109794
IPK SHA-256=6ad5deb71f88b8250c7bd5d7ca3bb82bcaf0907318385606a730b04239c9262c
plugin-ipk-audit=PASS
```

设备最初安装的是修正前同版本包，随后只从nativeC视图替换`start.sh/stop.sh/loop.sh`为规范包
中的确定内容并重启DDNS循环；配置、Token、PluginInfo和opkg登记未重建。

包内包含Mozilla CA bundle，不使用`curl -k`。下载时同时获取curl官方SHA文件并校验：

```text
cacert.pem bytes=186446
SHA-256=3ff344e30b9b1ed2971044eabb438a08f2e2245ddb5f8ab1a3ad8b63ab4eaf91
verified=true
```

## 原厂安装与状态

通过原厂`0x2409`事务安装为`DEV.PluginInfo3`。安装后的第一次禁用归一化过早，返回`-103`；
等待5秒后重试成功。这说明大型/小型插件安装后都应等待opkg/control回写完成，再发0x2401状态事务。

最终启用状态：

```text
Name=sr1010-cf-ddns
Enable=1
Status=2
PID=0
StartMode=0
StartCMD=/bin/sh /opt/sr1010-cf-ddns/start.sh
StopCMD=/bin/sh /opt/sr1010-cf-ddns/stop.sh
```

PID字段为0是因为StartCMD脚本启动自己的循环后退出；真实运行状态由0600 pidfile、`/proc`命令行
归属检查和`health.sh`共同判断。不能只看PluginInfo.PID。

原厂`0x1103`启动事务同步返回`SSEND rc=-1`，与此前确认的异步无响应行为一致；实际nativeC脚本
已执行并启动循环。

## 更新逻辑

- 每120秒检查一次公网IPv4；
- 依次使用api.ipify.org、checkip.amazonaws.com、icanhazip.com；
- 三个地址均使用经过校验的CA bundle和HTTPS；
- IPv4与`state/last_ip`相同则不调用Cloudflare写接口；
- 变化时PATCH固定zone/record，强制A、TTL60、灰云；
- API响应必须同时满足HTTP成功和JSON`"success":true`；
- 只记录IP、动作和成功时间，不记录Token或完整API响应；
- events.log超过64KiB后只保留最后200行；
- start/stop会核对`/proc/PID/cmdline`确属本插件，避免PID复用误判或误杀。

首次强制更新：

```text
result=PASS action=updated ip=PUBLIC_IP_B
```

循环随后连续返回：

```text
result=PASS action=unchanged ip=PUBLIC_IP_B
```

生命周期实测：重复start、health、重复stop均返回0；正式启用后health为`loop=running`。

## 与WireGuard的隔离

`sr1010-net-runtime`继续保持：

```text
Enable=0 Status=1 PID=0 StartMode=0
```

本轮没有创建WG接口、开放UDP端口、添加地址/路由、修改DNS转发或iptables。`ppp0`保持
`UP,LOWER_UP`，nativeC保持`RUNNING`，路由器未重启。

## 已知边界

当前更新器维护公网IPv4 A记录。光纤动态公网切换可以在约两分钟内追上；若SR1010切到5G
CGNAT，记录仍可能更新到移动出口公网地址，但外部UDP入站依然不可达。DDNS不能解决CGNAT，
这种状态仍需Cloudflare WARP私网应急路径。

下一步可以使用`sr1010.example.invalid`作为WireGuard服务器Endpoint，生成服务器和第一台客户端
密钥；在实际开放UDP端口和转发规则前仍需单独验证端口选择及与现有51283/51820的冲突。
