# SR1010 net-runtime 0.2.0 正式升级（2026-08-07）

## 结果

通过原厂 Plugin Manager remove/install/enable 事务，将此前“0.1.0 注册记录 + 现场文件”正式升级为：

```text
Version=0.2.0
Enable=1
Status=2
StartMode=0
AllocatedDiskSpace=16384
AllocatedMemory=16384
```

nativeC 的 opkg 同时确认 `Version: 0.2.0`、`Status: install user installed`。

## 安全流程

1. 把配置备份到 `/usercfg/sr1010-recovery/config-latest.tar.gz`；
2. 从 mtd9 sibling IPK 启动本地一次性 HTTP 服务；
3. 正式 remove 0.1.0，确认 `wg-nrt0` 消失；
4. 正式 install 0.2.0；
5. 从 usercfg 恢复 `runtime.env` 和 `wg0.conf`；
6. 正式 Enable=1；
7. 执行生命周期审计。

首次调用 host recovery 暴露了归档名称白名单问题：`recovery-import.tar.gz` 被 restore 拒绝。现场配置未被覆盖；把导入名修正为 `config-recovery-import.tar.gz` 后恢复成功，源码和工具包已同步修复。

## 验证

- `wg-nrt0`：UP；
- UDP 51888：监听；
- WAN 和 WG->LAN 规则：存在；
- 双面板：`10.77.0.1:51889` 与 `192.168.50.1:51889`；
- 配置权限：0600；
- Peer：1；
- lifecycle-audit：全部 PASS；
- Cloudflare DDNS：loop=running。

检查时手机尚未向新进程发起握手，因此服务端计数为0；这不影响服务端正式升级结论。

本轮未重启路由器、未修改 Telnet/root 凭据、未限制 Telnet、未写固件槽。
