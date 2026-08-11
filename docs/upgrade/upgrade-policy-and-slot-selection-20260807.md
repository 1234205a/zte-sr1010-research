# SR1010 升级版本策略、目标槽和回滚字段

日期：2026-08-07  
对象：当前 B2 `cspd`、`fw_flashing`及实机只读`versionstates`。

## 目标槽选择已精确还原

`fw_flashing::SetVersionHeader`读取：

- `currentverphyaddr`
- `curverheader_highstart`
- common header `+0x1e0/+0x1e4`低槽边界
- common header `+0x1e8/+0x1ec`高槽边界

逻辑为：

```text
if currentverphyaddr >= high_start:
    target = low slot
    flashing_selector = 1
else:
    target = high slot
    flashing_selector = 2
```

即永远写非活动槽，不覆盖当前正在运行的槽。当前设备从低槽运行，因此下一次正常固件升级
目标是：

```text
target_start = 0x02f00000
target_end   = 0x05800000
selector     = 2
```

## 版本计数与切换

写入目标槽头之前，flashing程序执行：

```text
header[0x1f0] = target_start
header[0x1f4] = maxversionum + 1
header[0x1f8] = 1
header[0x1fc] = crc32(header[0:0x1fc])
```

当前`maxversionum=4`，所以新槽头计数会是5。写入、回读和头部校验成功后才调用
`CspSwitchVersion`切换启动版本；原活动槽及其计数4保留，形成回滚底座。两个槽的坏槽标志
由内核版本管理层维护，当前均为0。

## BootVer策略

BootVer只在对应文件类型及开关启用时执行，当前版本文件来源为`/usercfg/bootversion_file`，
格式严格是：

```text
V%04u.%04u.%04u
```

每段必须不大于9999。比较规则只使用前两段：主版本必须相等，新次版本必须大于或等于当前
次版本；第三段被解析但不参与放行比较。违反规则返回升级错误。

## 普通软件版本分类

`CheckUpgradeType`理论枚举为：

```text
1 = 未分类/禁用比较
2 = 新版本高于当前版本
3 = 新版本低于当前版本
4 = 相同版本
```

当前B2传给解析器的版本分隔/格式字符串实际为空，函数在`strlen==0`时立即返回1。因此当前
构建没有通过这个通用函数强制阻止同版本或降版本；结果只写入升级状态供后续策略参考。
产品定制回调仍可增加限制，所以候选包继续保持本机真实版本和产品字符串最稳妥。

## 产品与专用校验

完整链先调用可选`SpecFileCheck`，随后调用产品/版本专用回调；回调缺失时日志明确记录
“not need spec check”。当前候选包使用真实的`ZXSLC SR1010`及`V1.0.0.2B5.8000`，没有
跨产品字段。通用`CheckUpgradeType`本身不是拒绝条件。

## download-only内部路径（修正第1项结论）

继续追踪`upgradeProcCheckSuccessEvent`发现内部确实有：

```text
UpgradeCtl == 0  -> 正常进入flash
UpgradeCtl == 1  -> 延迟/通知控制路径
其他控制值      -> 日志“Download only, No need flash”并调用upgradeEndWithoutFlash
```

因此“原厂代码不存在check后结束路径”的说法需要修正为：**内部路径存在，但当前Web上传Lua和
公开服务没有暴露设置该控制值的validate-only门面。** 在没有确认CM消息字段和回执前仍不向
设备提交候选包。

## 可重复工具

```powershell
python sr1010/tools/sr1010-tool.py upgrade-plan versionstates.txt
```

工具只读解析快照，输出目标槽、写入范围、selector和下一版本计数。
