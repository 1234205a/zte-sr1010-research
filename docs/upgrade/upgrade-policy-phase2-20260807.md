# SR1010 升级策略阶段 2：版本与 upgrade-key（2026-08-07）

## `check_ver_board` 精确行为

对 `fw_flashing` 中 632 字节的 `check_ver_board` 完成逐指令分析：

1. 从 `/proc/csp/boardtype` 读取运行中 board ID。
2. 从 `/proc/zte/verinfo/softVersion` 读取运行版本。
3. 从升级头解析四个最长 16 字节的字段。
4. 比较运行 board ID 与升级 board ID 的前 4 字节。
5. 比较运行版本与升级版本的前 6 字节。
6. 从 `/proc/capability/boardtype` 读取 VID，并检查 24 字节（192 位）能力位图。

成功返回 0，任何不匹配返回 1。

### 降级限制结论

这个函数没有把版本字符串转成数值，也没有执行大于/小于比较。它只要求版本前 6 字节一致。因此：

- 它是产品系列/主版本兼容检查。
- 它本身不是单调版本或禁止降级检查。
- 若存在真正的防降级策略，应位于更上层升级管理器或版本计数器，而不是 `check_ver_board`。

## `CSPBootCheck` 的 upgrade-key 策略

对 `boot_flashing` 中 544 字节的 `CSPBootCheck` 完成逐指令分析：

1. 读取升级包头中的 `key1/key2`。
2. 读取设备当前 `upgrade_key1/upgrade_key2`。
3. 若**升级包 key1** 为 `0` 或 `0xffff`，跳过 key 比较。
4. 若**设备 key1** 为 `0` 或 `0xffff`，同样跳过 key 比较。
5. 其他情况下，key1 和 key2 必须同时精确相等。
6. 无论是否跳过 key，比对结束后仍会验证 boot 内容 CRC。

因此“No need to check upgrade key”并非隐藏口令，而是明确的哨兵值兼容逻辑。CRC 校验不会随之跳过。

## 签名边界

`fw_flashing` 和 `boot_flashing` 的动态依赖与符号中没有 RSA、ECDSA、EVP、SHA 或证书验证入口；两者内置的是 AES 与 CRC 实现。可以确认最终 MTD 写入层主要依赖：

- upgrade key
- header/content CRC
- board/version 前缀
- VID 能力位图
- 写后逐字节检查

这不等于整个网页上传链没有外层签名校验；外层约束仍可能位于 `cspd` 升级管理器或 Web 上传预处理阶段。

## 可重复工具

新增：

```powershell
python tools/upgrade-policy-audit.py fw_flashing boot_flashing
```

工具按函数符号和 ARM 指令模式检查 7 项证据。本版本运行结果为 7/7 通过，不输出实际密钥值。

## 下一步

1. 分析 `SetVersionHeader`、`WriteVersion`、`CspSwitchVersion`，还原非活动槽写入和计数器切换顺序。
2. 定位上层外包签名/长度校验，区分网页候选文件与真正写入镜像。
3. 把上述策略校验加入固件重打包 preflight。
