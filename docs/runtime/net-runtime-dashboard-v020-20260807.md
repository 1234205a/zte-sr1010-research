# SR1010 WireGuard 只读状态面板与 0.2.0 构建（2026-08-07）

## 在线结果

已在 nativeC 部署只读状态面板，监听 http://10.77.0.1:51889/。

只绑定 WireGuard 服务端地址，不监听 WAN 和普通 LAN 地址。面板展示运行状态、监听端口、Peer 数量、最近握手和收发流量，不提供写操作，也不读取或返回私钥、PSK、完整公网 Endpoint。

在线验证：

- TCP 10.77.0.1:51889 正常监听；
- /status.json 返回有效 JSON；
- 首页返回 1942 字节；
- stop 后 WireGuard 与面板均退出；
- start 后二者均恢复；
- Telnet/root 凭据及 Telnet 防火墙策略未修改。

## 0.2.0 包

- 构建产物：sr1010-net-runtime_0.2.0_arm.ipk
- SHA-256：$sha
- IPK audit：PASS
- StartMode：0（nativeC）
- 包内不包含 
untime.env 或 wg0.conf；
- postinst 只在配置不存在时创建默认禁用占位文件；
- 源码与发布资产均不包含 WireGuard 私钥或 PSK。

当前路由器使用 0.1.0 注册记录加现场 0.2.0 功能文件，运行正常。尚未通过 Plugin Manager 重新安装 0.2.0 IPK，避免安装器的 remove/install 流程删除现有密钥配置。正式升级前应先实现配置备份恢复事务。

## 生命周期闭环

- 配置备份保存在独立路径 /opt/sr1010-net-runtime-backups；
- 最多保留 10 份，权限 0600；
- restore 支持校验、一键应用及启动失败自动回滚；
- prerm 自动备份并停止服务；
- postrm 清理接口、socket 与 iptables 规则；
- 在线备份校验和实际恢复回放均为 PASS；
- 双地址面板已验证随 stop/start 正确退出和恢复。

