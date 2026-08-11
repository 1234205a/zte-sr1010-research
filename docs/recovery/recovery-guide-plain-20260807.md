# SR1010 恢复指南（大白话版）

## 先判断坏到哪一层

### A. 路由器能正常开机，只是配置错了

使用原始 `config.bin` 走网页配置恢复。这是风险最低的方式，不写bootloader和固件槽。

推荐顺序：

1. 保留当前新导出的配置；
2. 用 `config-transaction.py` 检查原始备份；
3. 上传原始 `config.bin`；
4. 只有网页明确要求时才重启。

### B. 路由器能开机，但WireGuard或DDNS没起来

不刷固件。先运行插件健康检查：

```sh
/opt/sr1010-net-runtime/post-upgrade-health.sh check
```

需要修复时运行 `apply`。如果插件目录缺失，再安装恢复包中的IPK并恢复配置备份。

### C. 插件升级后配置丢失

使用各插件 sibling 备份目录中的最新归档：

- `/opt/sr1010-net-runtime-backups/`
- `/opt/sr1010-cf-ddns-backups/`

恢复脚本会先校验归档路径和SHA-256，再应用配置。不要把WireGuard私钥或Cloudflare令牌写入Git。

### D. 系统能进入原厂网页，但固件文件损坏

可以考虑网页恢复候选文件，但必须先运行统一离线自检。当前候选已通过所有已知结构和CRC检查，但尚未进行实机上传验证，因此操作前必须保留完整闪存和配置备份，并单独取得操作授权。

### E. 系统不能正常启动，但bootloader/TTL还能用

使用恢复包中的完整闪存或单槽提取物作为数据来源。优先只恢复损坏槽，不要直接整片覆盖。必须根据实际NAND坏块和OOB/ECC情况选择写入方式。

### F. bootloader也损坏

这属于底层硬件救援，需要TTL、编程器或原始NAND数据。当前128MiB文件是逻辑MTD转储，不含2048+64格式的原始OOB/ECC，不能冒充编程器级原始NAND镜像。

## 恢复包已经有什么

- 128MiB逻辑全闪存转储
- 网页恢复候选
- 原始config.bin
- WireGuard 0.2.1 IPK
- Cloudflare DDNS 0.1.1 IPK
- 逐文件SHA-256清单

## 仍缺什么

- 原始NAND OOB/ECC转储
- 已实机验证的网页固件恢复闭环
- Bootloader/TTL密码的最终实机验证
- 编程器接线和坏块重建记录

这些缺项只影响“设备完全不开机”的最底层救援，不影响日常配置、插件和普通固件恢复。

## 一条命令自检

通过统一入口执行 `offline-selftest`，当前结果为7/7通过：全闪存双槽、config往返、网页候选、恢复ZIP、两个IPK和Plugin边界全部PASS。
