# SR1010 网页升级包公共头与双组件布局

日期：2026-08-07  
来源：当前 B2 `cspd::UpgradeCheckFirmware` 逐指令还原，并用 NAND 中保存的当前版本头实算闭环。

## 文件读取顺序

`UpgradeCheckFirmware` 对上传文件执行：

1. 读取最前面的 `0x14` 字节封装头；
2. 调用内部解析器取得后续头偏移；
3. 跳到 `0x14 + parsed_header_size`；
4. 读取固定 `0xf4` 字节的 firmware common header；
5. 对 common header 的 `+0x00..+0xa3` 计算 CRC32，与 `+0xa4` 比较；
6. 按头内 offset/length 分块读取 kernel 和 fs，并分别计算 CRC。

## 已确认的 common header 字段

| 偏移 | 字段 | 当前 B2 值 |
|---:|---|---:|
| `0x08` | upgrade key1 | `0x510` |
| `0x0c` | upgrade key2 | `1` |
| `0x10` | 版本字符串 | `V1.0.0.2B5.8000` |
| `0x34` | kernel length | `0x54dc00` |
| `0x38` | kernel file offset | `0x180334` |
| `0x3c` | kernel CRC | `0x99285788` |
| `0x40` | fs length | `0x1780000` |
| `0x44` | fs file offset | `0x6e0314` |
| `0x48` | fs CRC | `0x0f097a69` |
| `0x6c` | 产品 | `ZXSLC SR1010` |
| `0x98` | 槽前导区 CRC | `0xd57e6630` |
| `0xa4` | common header CRC32 | `0x9d9cf94f` |

`+0xa4` 精确等于标准 CRC32 覆盖 `+0x00..+0xa3`。这与更外层槽记录 `+0x1fc` 的 CRC
是两个不同覆盖范围的 CRC，均已实算命中。

## 两个组件在上传文件中的关系

```text
kernel: offset 0x180334, length 0x54dc00
fs:     offset 0x6e0314, length 0x1780000
```

两个 offset/length 的精确关系：

```text
0x180334 + 0x54dc00 = 0x6cdf34
0x6e0314 - 0x6cdf34 = 0x123e0
0x6e0314 + 0x1780000 = 0x1e60314
```

因此当前版本的升级文件逻辑长度至少为 `0x1e60314`；kernel 和 fs 之间存在 `0x123e0`
字节的保留/对齐区，不能丢弃。另一个精确关系是 `0x314 + 0x180000 = 0x180314`，只比
kernel offset 少 `0x20`，说明 `0x314` 与前导区/下一段之间还有一个 32 字节对象；其用途
仍需结合前缀结构命名。

## 当前突破的意义

网页升级包已经从“未知私有大文件”缩小为已知组件 offset/length/CRC 的固定布局。当前还需
拆清前 `0x314` 字节内部的 `0x14` 封装、可变头、32字节对象，以及 kernel/fs 之间的
`0x123e0` 保留区，不能把它们错误地拼成无间隙文件。

本轮没有向网页上传文件，也没有调用升级状态机或写 NAND。
