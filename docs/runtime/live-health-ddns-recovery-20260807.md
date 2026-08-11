# SR1010 实机健康检查与DDNS恢复（2026-08-07）

## 范围

用户明确授权实机验证。本轮通过设备 LAN 地址的 Telnet 进入宿主系统，执行只读检查；发现DDNS停止后，仅调用现有DDNS `start.sh` 恢复服务。没有安装IPK、写固件槽、修改凭据或重启路由器。

## 关键运行架构

宿主系统的 `/opt` 为空；nativeC 的实际持久根位于 `/Plugin/apps`，运行进程则拥有自己的root/mount视图。宿主侧检查nativeC文件可使用：

```sh
/proc/PID/root/opt/...
```

执行nativeC脚本可使用：

```sh
chroot /proc/PID/root /bin/sh -c 'COMMAND'
```

其中PID可从正在运行的 `wireguard-go` 进程取得。直接在宿主运行 `/opt/...` 会误报文件不存在。

## 实测结果

- 固件：`V1.0.0.2B5.8000`
- `/Plugin`：40MiB，使用约18%，空间充足
- `/usercfg`：2MiB，使用约25%
- net-runtime：0.2.0，opkg状态正常
- DDNS：0.1.0，opkg状态正常
- WireGuard：接口UP、监听51888、配置状态running
- WireGuard配置权限：0600
- WAN入口与WG到LAN转发规则：存在
- 双地址面板：正常响应
- lifecycle-audit：全部PASS
- nativeC内 `tar/sha256sum/awk/stat/ip/iptables/sed`：全部存在

## 发现并处理的问题

DDNS的PID状态文件已失效，健康检查报告 `loop=stopped`，最后成功时间停留在较早时间。调用现有：

```sh
/opt/sr1010-cf-ddns/start.sh
```

返回0；三秒后健康检查为 `loop=running`。脚本会核对PID对应的cmdline，因此不会误杀无关进程。

这证明0.2.1中“WireGuard启动后检查并拉起DDNS”的改动有真实用途，并非纯理论防护。

## 尚未执行

- 未把net-runtime升级到0.2.1
- 未把DDNS升级到0.1.1
- 未上传网页候选固件
- 未重启设备

新版IPK实机安装仍应作为独立变更执行并保留升级前配置备份。
