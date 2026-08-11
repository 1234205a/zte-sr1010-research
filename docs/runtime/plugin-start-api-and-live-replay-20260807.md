# SR1010 Plugin启动API与无重启在线重放

日期：2026-08-07

## 静态闭环

`PluginAutoStart`对每条`PluginInfo`记录执行的关键流程已精确到字段和调用参数：

```text
PluginInfo +0x1a4: Enable，必须等于1
PluginInfo +0x9e4: StartCMD
PluginInfo +0xc24: 宿主/容器启动选择字段
```

容器分支实际调用：

```c
LXCPcStartProgram("/bin/sh", plugin_info->StartCMD, NULL, 0);
```

`IPKGetInfo`读取control里的`StartCMD`后，会用固件内置格式串`/bin/sh %s`写入数据库。
所以当前数据库中的`/bin/sh /opt/sr1010-hello/start.sh`是原厂有意生成的完整命令行，
不是hello包重复添加了shell。

`LXCPcStartProgram`只是`liboss.so::PcStartProgramEx`包装器：它设置LXC标志为1，并把请求
发送给`pc`进程。只有该调用返回非负PID，`PluginAutoStart`才把Status更新为2、PID写回数据库。
当前PID保持0，说明失败发生在PC/LXC启动请求，而不是数据库遍历或脚本路径筛选之前。

## 无重启在线复核

通过正式`0x2401`事务把hello临时切到`Enable=1, Status=2`，随后重放`0x1103`：

```text
enable: SSEND rc=0, plugin_rc=0
pluginmgr handler 0x12adc RCounts: 4 -> 5
startup同步调用返回-1（该启动事件没有同步响应）
```

handler确认再次执行，但事件日志没有新增，数据库PID仍为0。测试结束后已通过正式事务恢复：

```text
Enable=0
Status=1
PID=0
```

没有重启、没有写MTD，也没有改变路由、防火墙或网络服务。

## 已排除与剩余边界

已排除：

- IPK未落盘；
- JFFS2/overlay不持久；
- StartCMD由包重复添加`/bin/sh`；
- Enable门控未满足；
- 只因开机时PC/LXC尚未就绪；
- `0x1103`没有真正抵达handler。

剩余问题集中到`PcStartProgramEx -> pc::StartProgram`对LXC请求的接受条件，例如容器目标、
进程登记名或命令行拆分。下一步应恢复PC请求结构和错误返回码，不再用重启试错。

