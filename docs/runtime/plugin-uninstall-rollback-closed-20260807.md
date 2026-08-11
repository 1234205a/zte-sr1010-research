# SR1010 Plugin卸载、残留清理与重装回滚闭环

日期：2026-08-07

## 正式卸载结果

通过原厂`0x2411`事务卸载`sr1010-hello`：

```text
SSEND rc=0
plugin_rc=0
PluginInfo RowCount=0
opkg status: absent
```

opkg正确删除了`start.sh/stop.sh/health.sh`和包登记，但保留插件运行期自行创建的
`state/events.log`。这是合理的“未被包管理器拥有的数据不自动删除”行为。因此完整卸载应分两步：

1. 原厂事务停止并卸载包；
2. 确认数据库和opkg均已清空后，从nativeC容器内部清理插件自己的state目录。

## 发现的overlay边界

不能在nativeC运行时直接从宿主删除`/Plugin/apps`中的upperdir。现场这样操作后，正在挂载的
overlay出现：

```text
mkdir /opt: Stale file handle
```

原厂安装事务仍会错误返回业务成功并登记opkg/PluginInfo，但文件实际无法写入。这说明回滚
工具必须同时检查数据库、opkg和真实文件，不能只看`plugin_rc=0`。

正确规则：

- 运行时清理通过nativeC视图`/opt/<plugin>`进行；
- 不直接修改已挂载overlay的宿主upperdir；
- 若upperdir被外部修改，重新挂载需要重启nativeC容器；
- 启动命令必须带配置：`lxc-start -n nativeC -f /lxc/nativeC.conf -d`。

## 现场恢复

为修复本次overlay stale handle，只重启了nativeC容器，没有重启路由器。第一次省略`-f`导致
启动失败，随后使用原厂配置成功恢复。最终状态：

```text
nativeC=RUNNING
pluginmgr=running
ppp0=UP
WAN地址保持
router uptime连续（未重启）
```

之后再次通过原厂安装事务重装修正版`StartMode=0` hello包，并立即禁用。最终三层验证：

```text
PluginInfo: Enable=0, Status=1, PID=0, StartMode=0
opkg: install user installed
真实文件: start.sh, stop.sh, health.sh存在
health.sh: 正常返回
```

## 回滚闭环结论

现在已验证：安装、禁用、启动、停止、正式卸载、运行数据识别、overlay故障识别、容器恢复、
重新安装和健康检查。以后WireGuard/DDNS插件必须遵循相同的三层校验，且卸载脚本只能删除
自己命名空间内的文件。

