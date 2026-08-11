# SR1010 config.bin 往返工具链（2026-08-07）

## 结论

当前版本 `V1.0.0.2B5.8000` 导出的 Type-4 `config.bin` 已实现可重复的完整往返：

`config.bin -> AES-256-CBC 解密 -> 分块 zlib 解压 -> XML -> 分块压缩 -> 加密 -> config.bin`

本地样本验证结果：

- 外层文件：34344 字节
- 内层有效数据：34259 字节
- 密文：34272 字节
- XML：286082 字节，根节点 `DB`
- 分块：5 块，每块上限 65536 字节
- 内层头 CRC32：通过
- 压缩数据 CRC32：通过
- 明文往返：完全一致
- 二进制重建：与原始 `config.bin` 逐字节一致

以上哈希和尺寸只用于确认算法，仓库中不保存用户配置正文、口令或派生密钥。

## 新工具

- `tools/config-bin-tool.py`
  - `inspect`：只输出结构、CRC、尺寸和哈希
  - `unpack`：解密并提取 XML
  - `pack`：验证 XML 后重新生成 Type-4 文件，并立即内部复验
  - `verify`：严格校验外层长度、CBC 填充、块链、zlib、CRC 和 XML
  - `roundtrip`：检查明文往返以及二进制是否可重复
- `tools/test-config-bin-tool.py`
  - 多块往返
  - 错误型号拒绝
  - 截断密文拒绝

## 使用

```powershell
python tools/config-bin-tool.py inspect config.bin
python tools/config-bin-tool.py unpack config.bin config.xml
python tools/config-bin-tool.py pack config.xml config-new.bin
python tools/config-bin-tool.py roundtrip config.bin
python tools/test-config-bin-tool.py -v
```

## 脱敏审计

对当前本地样本只做了字段存在性和开关审计：识别到 10 个重点开关表、75 个含敏感字段名的表。报告不保存字段值。已确认工具能够定位 Telnet、诊断、串口日志、FTP、升级配置保留和口令保护等控制面。

## 风险边界

工具生成文件不等于已经在设备上导入验证。导入前应保留原始 `config.bin`，先运行 `verify` 和 `roundtrip`。本阶段没有连接、修改或重启路由器。

## 下一步

1. 将脱敏审计整合为统一工具子命令，并增加修改前后字段级差异报告。
2. 从固件 `cspd` 的导入路径核对所有错误码与边界条件。
3. 在获得单独授权后，仅用无功能变化的二进制等价重建文件做网页导入验证。

## 2026-08-07 第二轮补强

统一工具新增：

- `audit`：输出重点开关以及敏感字段的存在性和长度，默认不显示密码、令牌、服务器等字段值。
- `diff`：比较两个 Type-4 配置；敏感字段默认只显示是否存在和长度，只有显式 `--reveal` 才显示本地值。
- `edit`：仅允许审核过的布尔开关，采用字节级定点替换，避免 XML 重新序列化造成无关变化；生成后自动解密复验。

当前回归测试增至 5 项，全部通过。另使用本地真实样本生成临时副本，将 `TelnetCfg[0].Lan_Enable` 从 `0` 改为 `1` 后执行差异检查，报告只出现这一项变化；临时副本随后删除，未导入设备。
