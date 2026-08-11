# SR1010 插件正式安装CMAPI消息格式

日期：2026-08-06

## 结论

继续沿 `mqtt::pluginAdd` → `libcmapi::CmInstall` → `pluginmgr::PluginCmapiInstall` 追踪后，正式安装消息的入口、字段和内部IPC已经恢复。hello插件不需要伪造数据库行；正确路线是构造同一份CMAPI请求。

## 外层JSON-RPC参数

`mqtt` 中的 `pluginAdd` 调用 `convertParamListAndPluginCfgStruct`，按以下键转换：

```text
Id
Name
Enable
Status
Url
flash
ram
Version
Type
```

字段在内部 `PluginCfg` 请求结构中的偏移：

| JSON字段 | 结构偏移 | 用途 |
|---|---:|---|
| `Name` | `+0x000` | 插件名称 |
| `Id` | `+0x060` | 插件ID |
| `Type` | `+0x0c0` | 插件类别 |
| `Enable` | `+0x120` | 启用状态 |
| `Status` | `+0x140` | 操作/安装状态 |
| `Url` | `+0x160` | IPK下载地址 |
| `flash` | `+0x7c0` | 申请的持久磁盘空间 |
| `ram` | `+0x7e0` | 申请的运行内存 |
| `Version` | `+0x820` | 版本字符串 |

转换后的请求结构总长为 `0xbe0` 字节。`pluginAdd` 把该结构交给：

```c
CmInstall(result_buffer, plugin_cfg);
```

其中结果缓冲区最多回收32字节操作标识/结果字段。

## libcmapi内部IPC

`CmInstall` 位于 `libcmapi.so` 的 `0xaa394`，执行同步内部消息：

```text
事件ID：0x2409
接收者：pluginmgr.plugintask.plugin_mgr
请求长度：0x0be0
同步等待参数：0x1770
响应缓冲：0x80字节
```

pluginmgr收到后进入已经逆向的 `PluginCmapiInstall` 事务，完成URL鉴权、下载、`PluginInfo`登记、opkg安装和control字段回写。

## 意义

现在已经知道“正式安装请求应该长什么样”，不必使用数据库debug命令执行 `addr/set/save`。这保留了原厂对磁盘/内存资源、重复名称、下载结果和安装状态的处理。

同时也确认MQTT只是该CMAPI的一个调用方，不是必需条件。设备内任何正确链接 `libcmapi.so` 的本地小工具都可以调用 `CmInstall`，无需向厂商云发布伪造消息。

## 当前剩余工作

当前Windows环境没有ARM交叉编译器，路由器上也没有编译器，因此本轮没有生成或运行调用器，更没有安装插件。下一步有两条路径：

1. 在可用的ARM交叉编译环境中编译一个最小本地 `cm-plugin-install` 调用器；
2. 继续检查固件内是否有通用CMAPI CLI能直接调用 `CmInstall`。

调用器上线前仍需确认LAN临时HTTP服务器可被pluginmgr的LXC网络访问。hello IPK本身已经准备好，且没有网络或系统配置副作用。
