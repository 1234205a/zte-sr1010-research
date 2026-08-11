# SR1010 固件升级 key 校验精确边界

日期：2026-08-07  
对象：当前 B2 `/kmodule/bin/cspd` 的 `UpgradeCheckUpgradeKey`（`0x14af84`，596 字节）。

## 可直接使用的结论

设备当前升级 key 从运行时 procfs 读取：

- 首选：`/proc/csp/versionstates`
- 兼容回退：`/proc/zte/verinfo/versionstates`
- 字段：`curUpgradeKey1`、`curUpgradeKey2`
- 文本格式：`0x%08x`

只读保存方法（不会写配置或重启）：

```sh
cat /proc/csp/versionstates > /tmp/versionstates.txt
```

拿回电脑后运行：

```powershell
python sr1010/tools/upgrade-key-readonly.py versionstates.txt
```

## 实际判断逻辑

逐指令还原结果：

```text
current_key1 = read_proc("curUpgradeKey1")
current_key2 = read_proc("curUpgradeKey2")
if current_key1 in (0, 0xffff) or package_key1 in (0, 0xffff):
    return SUCCESS
if package_key1 == current_key1 and package_key2 == current_key2:
    return SUCCESS
return UPGRADE_KEY_ERROR
```

失败时函数返回 `0x0a`，日志错误码为 `0x2100`。跳过条件只检查 key1：设备当前 key1
或升级包 key1 为 `0`/`0xffff` 时直接成功，不再要求 key2 相等。这是独立于零签名长度
分支的第二个兼容性边界。

## 有什么用

1. 拿到原厂升级包后，可预判是否会被本机 key 策略拒绝。
2. 构造兼容升级头时，可读取当前值，不再猜设备派生算法。
3. 与 `sign_len=0` 组合后，剩余重点缩小到 CRC、产品/板型、版本及分段布局。

它只恢复 upgrade key 这一层规则，不代表任意文件可以写入 NAND。
