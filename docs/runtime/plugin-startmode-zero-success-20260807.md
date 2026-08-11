# SR1010 Plugin持久化启动根因与无重启成功闭环

日期：2026-08-07

## 根因

此前把`StartMode=1`解释成“自动启动”是错误的。`PluginAutoStart`真正的自动启动门控是
`Enable==1`；`StartMode`决定执行命名空间：

```text
StartMode == 0 -> LXCPcStartProgram，进入nativeC/LXC
StartMode != 0 -> PcStartProgram，在宿主执行
```

hello载荷通过opkg安装在容器视图`/opt/sr1010-hello`，宿主持久实体则是
`/Plugin/apps/opt/sr1010-hello`。原包使用`StartMode=1`后，PC在宿主执行：

```text
/bin/sh /opt/sr1010-hello/start.sh
```

宿主没有这个`/opt`路径，因此shell立即失败。安装、数据库、Enable、PC和容器本身都没有坏。

## 无重启成功验证

现场临时把`StartMode`从1改为0，再通过正式`0x2401`事务设置Enable=1并重放`0x1103`。
日志立即新增两次容器内启动记录：

```text
event=start
pid=51
mount_plugin=tmpfs on /plugin ...

event=start
pid=59
mount_plugin=tmpfs on /plugin ...
```

这证明`PluginAutoStart -> LXCPcStartProgram -> nativeC -> /bin/sh -> start.sh`完整成功，不需要
重启验证基本执行链。两条记录可能来自此前直接PC探针的延迟请求与本次0x1103重放先后完成；
不影响StartMode切换前0条、切换后成功执行的因果结论。

测试后设备已恢复原状态：

```text
Enable=0
Status=1
PID=0
StartMode=1
```

没有重启、写MTD、修改网络或防火墙。

## 工具修正

`build-hello-ipk.py`现将`StartMode`生成成0。以后为nativeC容器打包的WireGuard/DDNS或其他
插件也应使用0；只有命令和依赖明确位于宿主命名空间时才使用1。

下一次正式重装修正版hello后，只剩开机持久自启动确认；该验证涉及重启，仍需用户当次明确
授权。在此之前无需再逆向PC拒绝路径。

