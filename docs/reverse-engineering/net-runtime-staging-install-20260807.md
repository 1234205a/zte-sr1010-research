# SR1010 net-runtime默认禁用包：安装与回滚实测

日期：2026-08-07

## 本轮结果

完成了`sr1010-net-runtime 0.1.0`确定性IPK、nativeC安装、正常幂等、无地址TUN和错误配置
回滚测试。包当前保留安装，但保持：

```text
ENABLE=0
INTERFACE=wg-nrt0
ADDRESS=
ROUTES=
PluginInfo row = absent
```

因此当前包不创建接口、不启动进程、不添加地址/路由，也不参与原厂PluginAutoStart。即使设备
意外重启，原厂插件数据库也没有它的自动启动记录。本轮没有重启路由器或nativeC。

## 包结构

构建器：[`tools/build-net-runtime-ipk.py`](tools/build-net-runtime-ipk.py)

构建命令需要显式传入上一阶段生成的两个ARM32二进制：

```powershell
python sr1010/tools/build-net-runtime-ipk.py `
  C:\path\wireguard-go-armv7 C:\path\wg-armv7-static `
  C:\path\sr1010-net-runtime_0.1.0_arm.ipk
```

现场包：

```text
bytes   = 1944327
sha256  = 322906dca42af786b9641f69dd3b6ed9d79600e568f89f0788d7aa334ff35d76
audit   = PASS
mode    = config directory 0700; runtime.env/wg0.conf 0600
```

包内不含私钥、peer、公网地址、Cloudflare token或其他秘密。`runtime.env`默认禁用，
`wg0.conf`只有注释占位。

## 生命周期设计

- `start.sh`：先验证开关、接口名、TUN、配置存在性和0600权限；使用
  `WG_PROCESS_FOREGROUND=1`启动并记录准确PID；依次执行setconf、MTU、可选地址、link up、
  可选精确路由；任何一步失败由trap调用stop回滚。
- `stop.sh`：只在`/proc/PID/exe`确认是本包二进制后终止进程，只删除配置中的精确接口和
  对应UAPI socket，可重复执行。
- `health.sh`：只输出包、开关、接口、TUN、工具版本和状态，不输出配置内容。
- `selftest.sh`：默认只检查工具与TUN；显式`--tun`才创建`wg-nrt-test`，确认没有地址后删除。

## 安装证据

通过nativeC本地opkg安装：

```text
INSTALL_RC=0
Installing sr1010-net-runtime (0.1.0) to opkg...
Configuring sr1010-net-runtime.
Status: install user installed
Architecture: arm
```

之所以本轮没有走pluginmgr正式登记，是为了保持“装上但绝不自动启动”的staging边界。正式接管
网络前再走已经闭环的`0x2409`安装事务，把StartMode=0写入PluginInfo，并继续保持Enable=0。

## 正常与幂等测试

```text
HEALTH_RC=0
START1_RC=0
START2_RC=0
STOP1_RC=0
STOP2_RC=0
BASIC_RC=0
selftest=tun_created_without_address
TUN_RC=0
FINAL_HEALTH_RC=0
```

两个start在`ENABLE=0`时只写`state=disabled`；两个stop均安全返回。TUN自检只创建无地址
`wg-nrt-test`，退出trap完成清理。

最终残留与网络检查：

```text
wg-nrt0 absent
wg-nrt-test absent
wg-nrt0 socket absent
wg-nrt-test socket absent
route table before/after byte-identical
ppp0 UP,LOWER_UP
nativeC RUNNING
```

## 故障回滚测试

临时备份原配置，把`ENABLE`设为1并写入非法WireGuard指令。`wireguard-go`创建接口后，`wg
setconf`按预期失败：

```text
Line unrecognized: `INVALID_DIRECTIVE'
Configuration parsing error
EXPECTED_START_RC=1
```

随后trap闭环结果：接口不存在、UAPI socket不存在、PID文件不存在，状态为
`stopped/clean`。测试立即恢复原文件和0600权限，健康检查再次返回0、`ENABLE=0`。

## 当前设备状态与下一步边界

- 包保留在`/opt/sr1010-net-runtime`，约占5MiB展开空间；
- opkg已登记，PluginInfo未登记；
- 无运行进程、接口、socket、地址或路由；
- 路由器和nativeC均未重启；
- 传输IPK和测试输出已从设备`/tmp`删除。

下一步是在不改变当前状态的前提下制作“正式登记但仍禁用”的安装/卸载流程；再下一步才需要
用户提供真实WireGuard配置，并单独授权添加一条测试主机路由。

