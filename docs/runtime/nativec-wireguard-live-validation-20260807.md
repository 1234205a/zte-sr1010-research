# SR1010 nativeC WireGuard ARM32实机验证

日期：2026-08-07

## 结论

`wireguard-go`用户态路线已经从“理论可行”推进到真实设备闭环：官方源码交叉编译出的
ARM32程序可在nativeC运行，成功创建`wg-test`，静态`wg`可读取UAPI状态。测试接口没有
配置地址、peer、路由、DNS、iptables或持久化启动项，随后已删除；路由器未重启，nativeC
保持`RUNNING`。

这证明后续可以制作正式的WireGuard插件，不再需要保留Asus路由器仅用于WG。正式替换前仍需
实现配置权限、启动顺序、WAN变化重连、精确路由和卸载回滚。

## 固定构建输入

| 组件 | 版本/提交 |
|---|---|
| Go | `go1.26.5.windows-amd64.zip` |
| Go ZIP SHA-256 | `97e6b2a833b6d89f9ff17d25419ac0a7e3b482a044e9ab18cdef834bd834fd38` |
| wireguard-go | tag `0.0.20250522`，checkout `f333402bd9cbe0f3eeb02507bd14e23d7d639280` |
| wireguard-tools | tag `v1.0.20260223`，checkout `49ce333da02056ae7b22ee2aeb6afe8aaed79b19` |
| Go目标 | `GOOS=linux GOARCH=arm GOARM=7 CGO_ENABLED=0` |
| wg目标 | Zig `arm-linux-musleabihf`，静态链接，ARMv7/VFPv3-D16 |

构建脚本：[`tools/build-nativec-wireguard.ps1`](tools/build-nativec-wireguard.ps1)。脚本只写
本机工作目录，不含设备凭据、WireGuard密钥或Cloudflare token。

## 构建产物

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `wireguard-go-armv7` | 3,211,390 | `6867b5a68523755ba8d441fdc58f0e1205ab408e71db9ba0f29eaffe7b3922a1` |
| `wg-armv7-static` | 1,802,148 | `8fba7fa5f76c7ddf76cae600c68d42977e2cce989667c03f79006c8e8e9f3f07` |

两者均为ELF32、小端、ARM机器号40。压缩传输后在设备端通过`gzip -t`，解压后的字节数与
本地产物一致。

## 实机证据

nativeC中执行静态工具：

```text
wireguard-tools v1.0.20260223 - https://git.zx2c4.com/wireguard-tools/
```

创建临时接口后：

```text
START_RC=0
SHOW_RC=0
interface: wg-test
  listening port: 52700
IP_RC=0
20: wg-test: <POINTOPOINT,MULTICAST,NOARP> mtu 1420 qdisc noop qlen 500
    link/[65534]
```

`ip addr`输出没有`inet`或`inet6`，所以本次测试没有地址和流量路径。删除验证：

```text
DEL_RC=0
HOST_IF_RC=1
Device "wg-test" does not exist.
State: RUNNING
```

`wireguard-go`启动时显示“kernel has first class support”横幅。该版本源码在Linux/FreeBSD/
OpenBSD后台启动时无条件打印此提示，不是内核模块探测结果；真实成功点是它通过`/dev/net/tun`
创建了用户态接口和UAPI socket，不能据此改写先前“未发现WireGuard模块”的结论。

## 现场边界与清理

- Windows防火墙没有被修改：临时规则命令因子进程没有提升令牌而未生效；
- 改用已有Telnet管理通道传输gzip编码数据；
- 没有重启路由器或nativeC；
- 没有写`/Plugin`、JFFS2、配置数据库或启动项；
- 已删除`wg-test`、nativeC `/tmp/wireguard-go`、`/tmp/wg`及宿主侧传输临时文件；
- 本机便携Go、源码和构建产物保留在`Downloads/sr1010-wg-build`，便于下一步打包。

## 下一步

1. 生成不带秘密的`net-runtime`插件骨架，安装二进制但默认禁用；
2. 配置文件权限设为`0600`，Git只保存字段模板和密钥指纹；
3. start脚本按“创建接口→setconf→地址→精确路由”顺序执行，任一步失败即回滚；
4. stop/uninstall精确删除自身接口、路由、进程和UAPI socket；
5. 先与现有Asus WireGuard并行做单主机路由验证，稳定后再讨论替换。

