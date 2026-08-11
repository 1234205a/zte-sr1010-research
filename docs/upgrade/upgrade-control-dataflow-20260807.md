# SR1010 UpgradeCtl 与只校验路径数据流

日期：2026-08-07

## 已闭环的数据流

当前 B2 `cspd` 的升级推送事件号为 `0x2605`。`UpgradeMain`收到该事件后把消息体交给
`UpgradeProcPushEvent`，后者执行：

```text
消息体 +0x2d8  ->  UpgradeCtl
UpgradeCtl     ->  g_tUpgradeStateMachine +0x370
```

文件校验成功后，`upgradeProcCheckSuccessEvent`从状态机`+0x370`读取该值：

```text
0      -> UpgradeProcFileFlashEvent（正常写非活动槽）
1      -> 延迟/通知状态机路径
其他值 -> upgradeEndWithoutFlash（不进入刷写）
```

因此原厂的“下载并完整校验，然后结束而不刷写”并非死代码，而是消息协议中的正式控制分支。

## 当前入口边界

Web端`do_firmware_upgrade.lua`只调用`VersionUpload`，公开页面没有传入 UpgradeCtl 的字段。
`httpd`中的 `VersionUpload` 是固定上传类型注册项；现有静态证据未显示网页参数能够覆盖
消息体`+0x2d8`。MQTT升级服务也只公开`upgradeMode/flashVersion`等云升级参数，没有确认的
本地 validate-only 门面。

结论：内部字段和分支已经定位，但“从现有Web页面安全设置非0/1值”尚未成立。直接伪造
`0x2605`内部消息还需要同时正确构造约`0x468`字节结构中的路径、媒体ID、回调和状态字段；
只设置`+0x2d8`会让前置解析读取未初始化字段，不作为实机方案。

## 可重复核对

```powershell
python sr1010/tools/upgrade-control-audit.py path/to/cspd
```

工具只读取ELF并核对关键加载、保存和结束调用，不连接设备。

## 实际意义

1. 已把“不刷写校验”从猜测提升为确定的内部协议能力。
2. 后续若还原完整`0x2605`消息结构，可以用原厂验证链检查重建包，同时避免写NAND和切槽。
3. 在完整结构还原前，继续使用离线预检器更稳妥；本阶段没有向路由器上传文件、写闪存或重启。
