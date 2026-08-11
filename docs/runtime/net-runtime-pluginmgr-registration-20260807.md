# SR1010 net-runtime原厂pluginmgr禁用登记闭环

日期：2026-08-07

## 最终状态

`sr1010-net-runtime 0.1.0`已从上一阶段的“仅opkg staging安装”推进为原厂pluginmgr正式
登记，同时保持不运行：

```text
ViewName=DEV.PluginInfo2
Name=sr1010-net-runtime
ID=sr1010-net-runtime
Type=local
Status=1
Enable=0
PID=0
Version=0.1.0
StartCMD=/bin/sh /opt/sr1010-net-runtime/start.sh
StopCMD=/bin/sh /opt/sr1010-net-runtime/stop.sh
StartMode=0
```

opkg、真实文件和健康检查同时通过。设备当前没有`wg-nrt0`、UAPI socket或WireGuard进程，
临时HTTP端口已关闭，WAN `ppp0`保持`UP,LOWER_UP`，nativeC保持`RUNNING`；没有重启。

## 首笔即禁用

修改[`tools/cm-plugin-install-ssend.c`](tools/cm-plugin-install-ssend.c)，增加：

```text
--execute-disabled
```

该模式在原厂`0x2409`安装请求中直接把Enable ctype设为0，而不是先用Enable=1安装、再抢时间
发送禁用事务。原有`--execute`行为保持不变，无参数仍在任何IPC调用前返回usage和退出码2。

本机首次交叉编译误用了默认GLIBC_2.34；上传后动态加载器在执行usage前拒绝，数据库仍为空。
随后把Zig目标固定为`arm-linux-gnueabi.2.17`，最终ELF仅要求`GLIBC_2.4`，实机usage保护通过。

## 安装流程

1. 调用包自身`stop.sh`；
2. 从nativeC opkg移除上一阶段staging副本，并从容器视图清理仅属于本包的state目录；
3. 重新传输同一个确定性IPK，字节数和`gzip -t`通过；
4. 用本机回环URL启动一次性`serve-one-file`；
5. 调用原厂安装事务：

```text
SSEND rc=0 plugin_rc=0 response_len=40 payload=DEV.PluginInfo2
```

6. 安装事务第一笔记录为`Enable=0, StartMode=0`；
7. 安装返回的临时记录是`Status=0, PID=236`，而宿主`/proc/236`并不存在，接口也不存在；
8. 通过既有原厂`0x2401`状态事务再次写入禁用，最终收敛为
   `Enable=0, Status=1, PID=0, StartMode=0`。

第7项表明安装返回时的PID字段不能直接当作真实进程证据。三层验证仍必须同时看PluginInfo、
opkg和真实进程/接口。

## 资源字段新发现

安装请求故意使用不同数值：

```text
FLASH_KB=8192
RAM_KB=32768
```

最终数据库却是：

```text
AllocatedDiskSpace=8192
AllocatedMemory=8192
```

后续静态闭环确认请求结构的RAM偏移正确；当前pluginmgr只检查RAM非零，随后把flash值同时
写入两个数据库资源字段。完整证据见
[`plugin-resource-field-closure-20260807.md`](plugin-resource-field-closure-20260807.md)。数据库的8MiB
不能解释为Linux真的施加了8MiB内存限制。

## 清理结果

- 一次性HTTP服务自然退出，18081端口关闭；
- 传输IPK、禁用安装调用器和本轮输出已从设备`/tmp`删除；
- 安装内容保留在`/opt/sr1010-net-runtime`；
- 原有hello插件记录和文件未修改；
- 没有地址、路由、DNS、iptables或重启操作。

## 下一步

RAM资源字段已经闭环为固件自身的复制行为，无需修改调用器偏移。下一步制作真实配置的本地
导入器。导入器只接受用户提供的配置，写入
设备0600文件并显示公钥指纹，不把私钥写入Git。之后再单独授权一次“单测试主机精确路由”，
不会直接替换Asus默认路径。
