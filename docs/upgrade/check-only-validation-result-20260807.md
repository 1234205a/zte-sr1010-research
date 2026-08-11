# SR1010 网页升级包“只校验不刷写”路径最终结论

日期：2026-08-07  
目标：确认是否能让设备原厂升级解析器完整处理候选包，同时保证不进入写 NAND/重启阶段。

## 结论

当前 B2 没有对外暴露独立的 firmware check-only 接口。Web、MQTT和本地 CM 请求最终都进入
同一套 `UpgradeMain` 状态机；`UpgradeCheckUpgradeFile` 成功后由
`upgradeProcCheckSuccessEvent` 继续推进到 flash 事件。网页上传接口不是“解析后等待确认”的
两阶段事务，因此不能把完整候选包提交给它来做无副作用试探。

固件中虽保留 `upgradeEndWithoutFlash` 函数，但静态全 `.text` 调用扫描没有找到对它的直接
调用，现有 Web/Lua、`libupgrade_service.so` 和 MQTT 服务也没有导出使用它的外部方法。

## 排除的伪入口

### `/bin/upgradetest`

该程序名称容易误导。符号和主函数逆向表明它只通过 `CspTagParamGet/Set/SynTagParam` 测试
BootVer标签参数，不调用 `UpgradeCheckFirmware`、`UpgradeCheckUpgradeFile` 或升级状态机，
不能用于固件包预检。

### `libupgrade_service.so`

它导出的入口是升级服务启动、HTTP版本查询、进度/结果上报和 `upgradeStart`，没有单独的
包校验API。调用 `upgradeStart` 会进入正常升级流程，不符合本项“不刷写”的边界。

### Web上传Lua

`do_firmware_upgrade.lua` 只是调用 `modules.file_upload_logic.UploadFile("VersionUpload")`，
上传完成后交给CM升级流程，不提供 validate-only 参数。

## 安全完成方式

因此本项采用独立、只读的 `web-firmware-preflight.py` 复现原厂检查器在进入flash前的确定性
判断：

- CSP四字magic与`skipped_header_size`；
- common header定位和CRC32；
- `sign_size=0`；
- upgrade key1/key2；
- 产品和版本字符串；
- boot、kernel、fs边界及三段CRC32；
- 文件最终长度。

当前候选包独立预检结果为 `PASS`。构建器和预检器是两个分开的实现，预检器不读取构建日志，
并对生成文件重新计算全部值。

## 实机只读检查

- 已确认设备Telnet仍可达；
- `/var`临时空间约55 MiB，理论上容得下31.8 MiB候选包；
- 没有把候选包传到设备；
- 没有调用Web上传、`upgradeStart`或任何升级事件；
- 没有写配置、写MTD或重启。

本项至此完成：安全的无写入校验交付物是离线预检器；原厂状态机没有可安全调用的公开
check-only门面。

后续对`upgradeProcCheckSuccessEvent`的深入复核补充了一条重要边界：内部`UpgradeCtl`取
非0/1控制值时会打印`Download only, No need flash`并调用`upgradeEndWithoutFlash`。所以
内部结束路径实际可达；缺的是当前Web/Lua及公开服务到该控制值的已确认门面。详见
[`upgrade-policy-and-slot-selection-20260807.md`](upgrade-policy-and-slot-selection-20260807.md)。
