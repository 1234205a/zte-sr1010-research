# SR1010 PluginInfo数据库与自动启动闭环

日期：2026-08-06  
目标：确认hello插件怎样被正式登记并在重启后运行

## 结论

后续动态闭环修正：此前把`cmp value,#1`归因于StartMode是字段定位错误。该比较实际检查
`Enable==1`；`StartMode`在调用点选择运行命名空间，0走LXC、非0走宿主。

自动启动流程是：

```text
dbAPILstView("PluginInfo", "DEV")
  -> dbAPIGetView(每条记录)
  -> Enable == 1
  -> /bin/sh <StartCMD>
  -> 启动成功后 dbAPISetView 更新运行状态
```

运行位置由`StartMode`决定：0调用`LXCPcStartProgram`，非0调用`PcStartProgram`。因此脚本
必须使用所选命名空间中的实际路径，不能假定宿主`/Plugin`与容器`/plugin`是同一路径。

## 正式安装顺序

`PluginCmapiInstall` 不是简单执行 `opkg install 本地文件`，而是一个完整事务：

1. 校验CMAPI请求；
2. 检查 `PluginInfo` 中是否已有同名记录；
3. 对下载URL检查鉴权参数；没有时查询 `/plugin/authlist` 并生成授权URL；
4. `IPKDownload` 下载 `/plugin/<name>/<name>.ipk`；
5. `dbAPIAddView("PluginInfo", "DEV", ...)` 创建记录，已存在时走 `dbAPISetView`；
6. 后续安装状态机运行 `IPKInstall`/`IPKGetInfo`；
7. `IPKGetInfo` 从control读取 `Version/StartCMD/StopCMD/StartMode` 并写回数据库。

`IPKInstall` 本身明确执行：

```text
opkg install /plugin/<name>/<name>.ipk
```

而且安装完成后再次用名称查询 `PluginInfo`。这说明绕开CMAPI只手工运行opkg，容易因为缺少数据库记录而被判失败，也不会形成可靠的 `PluginAutoStart` 闭环。

## hello包判断

现有hello包的字段与真实自动启动条件一致：

```text
StartCMD: /plugin/sr1010-hello/start.sh
StopCMD: /plugin/sr1010-hello/stop.sh
StartMode: 0
```

包格式、权限和确定性哈希已离线验证。剩余阻点不在IPK内容，而在如何从当前固件公开的CMAPI/调试总线提交一条本地测试安装请求。

## 下一步现场只读检查

不直接伪造 `PluginInfo` 数据库记录。先通过已存在的root会话读取：

```text
sendcmd pluginmgr..DB p
sendcmd pluginmgr..plugin_mgr help
sendcmd pluginmgr..plugin_mgr p
```

实际debug任务名需以 `sendcmd pluginmgr.. help` 的返回为准。目标是找出官方CMAPI install入口所需的请求字段或可调用命令，再让路由器从LAN临时HTTP地址下载hello包。

安装测试期间不重启前先确认：

- `PluginInfo`出现 `sr1010-hello`；
- `StartMode=1`；
- `StartCMD`路径正确；
- 手动启动后只新增自身日志；
- 卸载/停止入口有效。

满足以上条件后才安排一次重启验证。当前没有理由修改JFFS2节点、启动脚本或Bootloader。

## 2026-08-06 在线只读验证

通过现有WireGuard链路连接家中路由器的LAN Telnet，仅执行查询命令，确认：

```text
pluginmgr PID = 906
PluginInfo RowCount = 0
PluginInfo dwMaxRow = 32
PluginInfo bSave = 1
PluginInfo dwDmNum = 17
```

17个持久字段的真实顺序是：

```text
ViewName, Name, ID, Type, Status, Enable, URL,
Username, Password, AllocatedDiskSpace, AllocatedMemory,
PID, Version, Description, StartCMD, StopCMD, StartMode
```

这解释了为什么不能只放文件：`PluginAutoStart`依赖持久化 `PluginInfo` 行中的 `StartCMD/StartMode`。当前表为空也与 `/plugin/applist` 返回空列表一致，设备没有已经登记的官方插件可供复制模板。

同时确认数据库debug接口确实具备：

```text
p [tablename]
pti [tablename]
addr [tablename]
set [tablename][rownum][dm][dmvalue]
delr [tablename][rownum]
save
```

本轮只用了 `p/pti`，没有执行 `addr/set/delr/save`。这些写命令理论上能手工制造记录，但会绕过CMAPI资源检查和安装状态机，因此不作为首选安装方式。

`PluginCfg` 当前指向厂商插件目录；`PluginUpgrade` 的周期/重试状态也正常存在。具体带临时签名参数的URL和任何凭据不写入仓库。

另一个已纠正的调用格式：sendcmd真实进程/task寻址为 `pluginmgr.plugintask`，其PCB显示三个模块：

```text
plugin_mgr          PID 12
pluginupgrade_mgr   PID 13
pluginadaptor_mgr   PID 10
```

它们没有额外注册可直接调用的插件安装debug命令，所以正式安装入口仍应从CMAPI消息调用链寻找，而不是继续猜sendcmd命令名。
