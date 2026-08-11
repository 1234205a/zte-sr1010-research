# SR1010 无网络副作用插件持久化探针

日期：2026-08-06

## 用途

现阶段对日常使用最有价值的问题不是继续修改Bootloader，而是确认：放进插件区的自有程序能否在路由器重启后自动运行。

为此新增 [`tools/build-hello-ipk.py`](tools/build-hello-ipk.py)。它生成一个最小 `sr1010-hello` 插件包，只做三件事：

1. 启动时向自己的 `state/events.log` 写入时间、PID、UID和 `/plugin` 挂载信息；
2. 停止时追加一条停止记录；
3. `health.sh` 只读取这些记录。

它不会连接互联网、修改防火墙、启用Telnet、改配置或写Bootloader/kernel/rootfs。

## 包格式

包使用pluginmgr静态逆向所要求的旧式tar-IPK外层：

```text
sr1010-hello_0.1.0_all.ipk   (gzip tar)
├── debian-binary
├── control.tar.gz
│   └── control
└── data.tar.gz
    └── opt/
        └── sr1010-hello/
        ├── start.sh
        ├── stop.sh
        └── health.sh
```

`control`包含：

```text
StartCMD: /opt/sr1010-hello/start.sh
StopCMD: /opt/sr1010-hello/stop.sh
StartMode: 1
```

构建是确定性的：文件时间、UID/GID和gzip时间戳固定，同一脚本应得到相同哈希。

## 为什么暂不直接安装

离线已经确认包结构和pluginmgr解析字段，但尚未确认当前设备管理数据库怎样登记一个非官方插件，以及 `/plugin` tmpfs与宿主持久 `/Plugin` 的最终映射动作。跳过登记接口、只手工解包，可能证明脚本能运行，却不能证明 `PluginAutoStart` 会在重启后找到它。

因此正确现场顺序是：

1. 本地生成并展开检查IPK；
2. 通过现有LAN root会话只读查看pluginmgr数据库/调试命令；
3. 使用pluginmgr自己的安装入口安装hello包；
4. 先手动执行 `health.sh`；
5. 重启一次，检查是否自动新增 `event=start`；
6. 若失败，只卸载hello插件，不修改任何MTD启动分区。

只有这个闭环通过后，才把WireGuard与Cloudflare DDNS放进相同框架。

## 生成命令

```powershell
python sr1010/tools/build-hello-ipk.py sr1010-hello_0.1.0_all.ipk
```

## 2026-08-06 实机安装结果

已通过原厂 `0x2409` 安装事务完成实机闭环，未重启路由器。第一次IPK只有文件条目、
没有显式目录条目，opkg虽然登记包和文件清单，但实际报：

```text
wfopen: /opt/sr1010-hello/start.sh: No such file or directory
```

原因是该旧版opkg不会为文件隐式创建父目录。构建器现已在`data.tar.gz`中显式加入
`opt/`和`opt/sr1010-hello/`目录条目，并把载荷放在overlay持久层的`/opt`，避开
pluginmgr用于下载和解包后清理的`/plugin/<name>`临时目录。

修正版安装后同时确认：

- 容器合并视图：`/proc/906/root/opt/sr1010-hello/*.sh`
- 宿主持久上层：`/Plugin/apps/opt/sr1010-hello/*.sh`
- opkg文件清单：`/opt/sr1010-hello/*.sh`
- `PluginInfo.StartCMD=/bin/sh /opt/sr1010-hello/start.sh`
- `PluginInfo.StartMode=1`

在不重启的前提下，用相同容器根手动执行`start.sh`和`health.sh`，两者返回0，持久日志
成功写入`/Plugin/apps/opt/sr1010-hello/state/events.log`。探针不联网、不改防火墙，当前
数据库仍为`Enable=0`、`PID=0`。

## 第一次授权重启结果

用户明确授权后执行了一次`sync; reboot`。Telnet约56秒恢复，配置、插件数据库、opkg
记录和`/Plugin/apps/opt/sr1010-hello`脚本均完整保留，证明安装及JFFS2载荷持久化成立。

但事件日志没有新增`event=start`。重启前后数据库均为`Enable=0`，说明此前“只判断
StartMode”的静态结论不完整：启动链上还存在Enable门控，或者Enable=0使插件没有进入
待启动状态。

继续恢复`CmSetPluginInfo`后得到0x2401请求结构，并新增
[`tools/cm-plugin-enable-ssend.c`](tools/cm-plugin-enable-ssend.c)。实机正式切换成功：

```text
SSEND rc=0 plugin_rc=0
Enable=1
Status=2
PID=0
```

设置Enable不会在当前会话立即运行脚本，因此还需要第二次重启才能验证开机自动启动。
第一次授权已经执行完毕；第二次重启仍等待用户再次明确同意。

## 第二次授权重启结果

用户再次明确授权后，在`Enable=1, Status=2, StartMode=1`状态执行第二次重启。路由器
成功恢复，Telnet在发出重启约140秒后重新可用；读取`/proc/uptime`时系统已运行约202秒。
配置、数据库、opkg记录和脚本实体仍全部持久。

事件日志仍未新增第二条`event=start`，因此Enable门控并不是唯一剩余条件。当前证据把
问题缩小到原厂`PluginAutoStart -> LXCPcStartProgram/PcStartProgram`启动参数或插件运行
容器状态，而不是安装、JFFS2、数据库或重启持久化。

为避免以后每次开机重复尝试失败，验证后已通过正式0x2401事务恢复：

```text
Enable=0
Status=1
PID=0
```

没有继续重启。下一步应静态恢复`PluginAutoStart`传给`LXCPcStartProgram`的精确命令格式，
再用当前会话内的等价调用测试；通过后才需要考虑第三次重启。

## 第二次重启后的无重启深挖

在用户未再次授权重启的边界内，继续完成了两项排除：

1. 从设备取回完整`/var/tmp/lxc.EE.log`（500行、59269字节）并筛选`exec/attach/error`。
   日志只记录`nativeC`容器自身的启动过程，没有出现hello脚本或插件命令的执行记录。
   启动时的`/dev/tty1`、`/dev/tty2`已存在报错没有阻止容器进入RUNNING，属于非致命噪声。
2. 在当前会话用重定向标准输入输出的`lxc-attach`执行同一脚本成功，新增第二条
   `event=start`，返回码为0。这证明容器、overlay路径、脚本权限和脚本内容均可用。

因此故障边界进一步收窄：不是IPK、JFFS2、数据库、`nativeC`容器或脚本本身，而是
`PluginAutoStart`向PC/LXC管理器提交启动请求的时机或事务状态。原厂启动没有进入可在
LXC日志中观察到的exec阶段。

静态复核`liboss.so`还原了`LXCPcStartProgram`包装关系：它把固定的LXC目标字符串和
调用者参数转交内部`PcStartProgramEx`类实现；该实现要求调用进程已经具有有效OSS PCB
及发送FD，否则会在提交到PC管理器前失败。`pluginmgr`确实在OSS框架中运行，但开机阶段
是否早于PC/LXC通道就绪仍是当前最强假设。后续应优先寻找可在当前会话重新触发
`PluginAutoStart`的内部事件，或监听pluginmgr到`pc`进程的IPC；在此之前不值得做第三次
重启。

## 在线重放原厂启动事件

运行时OSS注册表确认了启动链，而不再只是静态推测：

```text
event 0x1103 -> handler 0x12adc -> PluginAutoStart 0x12850
event 0x1100 -> handler 0x12474
```

`0x12adc`先执行两次初始化辅助函数，随后直接调用`PluginAutoStart`。为避免第三次重启，
新增[`tools/cm-plugin-startup-ssend.c`](tools/cm-plugin-startup-ssend.c)，用普通进程OSS入口
向`pluginmgr.plugintask.plugin_mgr`重放零长度`0x1103` StartupMsg。

实机把hello临时切到`Enable=1, Status=2`后重放；pluginmgr运行时计数从1变成2，消息历史
明确记录：

```text
MsgId 0x00021103, MsgLen 0, Sender codex_plugin_startup0
handler 0x12adc RCounts 2
```

这证明`PluginAutoStart`在PC、lxcmgr和nativeC都已稳定运行的当前会话里被真正重新执行，
但事件日志仍没有新增，PID仍为0。测试后已正式恢复`Enable=0, Status=1, PID=0`。

因此“开机时PC/LXC通道尚未就绪”假设也被排除。剩余边界现在是：

1. `PluginAutoStart`读到的内部PluginInfo记录存在尚未识别的筛选字段；或
2. 它确实调用`LXCPcStartProgram`，但原厂PC协议拒绝当前StartCMD参数且没有把错误回写数据库。

静态复核同时确认该函数显式检查`Enable==1`，没有检查`StartMode`；传入启动API的程序固定
为`/bin/sh`，参数来自内部PluginInfo `+0x9e4`的StartCMD。下一步应直接观测/复现
`LXCPcStartProgram("/bin/sh", StartCMD, ...)`返回值，而不是继续重启。

## 2026-08-07 调用参数与再次在线复核

继续反向确认`IPKGetInfo`会主动以`/bin/sh %s`格式保存StartCMD，因此数据库中的
`/bin/sh /opt/sr1010-hello/start.sh`是原厂设计，不是包格式错误。`PluginAutoStart`再以
`/bin/sh`为程序名、该完整字符串为命令行调用`LXCPcStartProgram`。

修复本地ARM helper的DT_NEEDED和`libcommfun/libevent`依赖后，再次用正式0x2401启用、重放
0x1103并恢复禁用。handler计数确认从4增加到5，但PID仍为0、事件日志未新增。测试后状态
已恢复`Enable=0, Status=1, PID=0`，没有重启。剩余边界明确收敛到PC/LXC启动请求的拒绝
条件，详见`plugin-start-api-and-live-replay-20260807.md`。

## 2026-08-07 根因修正：StartMode是命名空间选择

继续追踪PC请求并做可回滚现场实验后确认：`StartMode=1`走宿主`PcStartProgram`，而不是
“自动启动”；`StartMode=0`才走`LXCPcStartProgram`。hello脚本的`/opt/...`只存在于nativeC
容器，所以旧包在宿主启动必然找不到路径。

临时改成0并重放0x1103后，事件日志成功新增容器内`event=start`，完整链已经跑通。测试后
设备恢复`Enable=0, Status=1, PID=0, StartMode=1`，构建器则永久修正为为容器插件生成
`StartMode: 0`。详见`plugin-startmode-zero-success-20260807.md`。
