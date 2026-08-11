# SR1010 pluginmgr IPC 事件闭环（2026-08-07）

## 结论

已从当前固件 `pluginmgr` 的真实事件表确认：原厂没有“读取 PluginInfo 记录”的公开 IPC 事件。此前计划把 `0x2402` 当作插件信息查询入口并不成立；它实际映射到 `PluginOperateStatusGet`，只返回全局插件操作状态。

因此本轮没有盲目修改数据库，也没有通过删除/重装伪造版本同步。

## 事件表

| 事件 | 处理函数 | 用途 |
|---|---|---|
| `0x1100` | `PluginMgrPowerOn` | 上电阶段 |
| `0x1103` | `PluginMgrNormalStart` | 正常启动阶段 |
| `0x2409` | `PluginCmapiInstall` | 安装插件并登记 |
| `0x2410` | `PluginCmapiUpgrade` | 原厂升级事务 |
| `0x2411` | `PluginCmapiRemove` | 移除插件 |
| `0x2401` | `PluginCmapiSet` | 启停/状态事务 |
| `0x2402` | `PluginOperateStatusGet` | 查询全局操作状态 |
| `0x1111` | `PluginStopProg` | 停止插件程序 |

## `0x2401` 的实际行为

反汇编确认它只使用请求中的插件 ID 和 Enable 值：

1. 根据 ID 调用 `FindPluginInfoDBByName`；
2. 用 `dbAPIGetView` 读取现有记录；
3. 根据 Enable 启动或停止插件；
4. 更新 Status/PID/Enable；
5. 用 `dbAPISetView` 保存。

它不会把请求中的 Version、StartCMD 或 StopCMD 合并进数据库，所以不能拿它安全同步展示版本。

## 独立数据库查询器验证

已还原并实机验证：

- `DBShmCliInit` 与 OSS 初始化顺序；
- `0x01020304` 查询魔数；
- `0xC28` PluginInfo ctype 长度；
- ID 等值查询字段；
- 结果计数和缓冲区布局。

独立任务对 net-runtime、cf-ddns、hello 及无条件枚举均返回 `dbAPIGetView=-19`。原厂数据库访问依赖已登记的 OSS 固件任务上下文，不能由临时进程直接复用 `pluginmgr` 身份。

## 正确后续路线

- net-runtime：使用 `0x2410 PluginCmapiUpgrade` 完成正式版本升级登记；
- cf-ddns：若尚无记录，使用 `0x2409 PluginCmapiInstall` 正式登记；
- 在执行前继续还原 `0x2410` 的专用请求结构、长度/摘要字段及失败回滚行为；
- 不使用 `0x2401` 强写版本，也不直接修改数据库共享内存。

## 实机安全状态

本轮没有重启路由器，没有修改凭据、密钥、接口、路由或防火墙。临时查询程序与 NAS HTTP 服务均在验证后清理。WireGuard 与 DDNS 保持运行。
