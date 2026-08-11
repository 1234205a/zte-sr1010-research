# SR1010 升级文件完整性算法精确还原

日期：2026-08-07  
对象：当前 B2 `cspd` 的 `UpgradeCheckFileIntegrality`（`0x14a81c`，1352 字节）。

## 文件描述符布局

该函数收到的描述符开头已经可以确定：

```c
struct integrity_desc {
    uint32_t algorithm;       // +0x00
    uint32_t expected_size;   // +0x04
    char checksum_hex[];      // +0x08
};
```

执行顺序是：确认路径存在、读取文件长度、检查描述符长度、打开并读取文件、计算摘要、转成
小写十六进制，最后先比较字符串长度再比较内容。

## 算法枚举

| algorithm | 实际行为 | 摘要文本长度 |
|---:|---|---:|
| 0 | 直接成功，不读取摘要 | 0 |
| 1 | 直接成功，不读取摘要 | 0 |
| 2 | MD5 | 32 |
| 3 | SHA-256 | 64 |

对于算法 2/3，空文件失败；`expected_size` 非零时必须与文件实际长度一致。算法 2 生成 16
字节摘要再转 32 字符，算法 3 生成 32 字节摘要再转 64 字符。

## 可直接使用的离线预检器

```powershell
python sr1010/tools/upgrade-integrity-check.py COMPONENT `
  --algorithm 3 --size EXPECTED_SIZE --checksum EXPECTED_SHA256
```

它不会接触路由器，可用于核验拆出的升级组件，也可在以后重建升级包时生成/验证描述符值。

## 对整体升级链的修正

此前笼统写作“CRC”的前置完整性层，在这个公共文件检查函数中实际是 **MD5/SHA-256 或
枚举 0/1 直接通过**。随后对实机双槽头的复核确认：另一处 CRC 确实存在于 header
`+0x1fc`，算法是覆盖 `+0x000..+0x1fb` 的标准 CRC-32；两者不能混称。

结合已确认的 `sign_len=0` 和 upgrade key1 哨兵分支，当前还需恢复的是外层升级头如何引用
该描述符、产品/板型/版本字段以及组件切割偏移。
