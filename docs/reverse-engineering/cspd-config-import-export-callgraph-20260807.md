# cspd 配置导入/导出调用链（阶段 1，2026-08-07）

## 样本

`V1.0.0.2B5.8000` 当前 rootfs 中的 ARM32 `bin/cspd`，文件大小 3329124 字节，带完整 `.symtab`，因此可以直接恢复函数边界。

## 已定位的主链

### 导出

- `dbFileSaveUserCfg`：先调用 `dbXMLFileSave` 写 XML，再复制中间文件。
- `dbGetUsrCfgFileDeal`：进入封装阶段；可见 `EncryByCRC` 与 `dbcCfgFileComKeyEncry` 分支。
- `dbcCfgFileComKeyEncry` / `dbcCfgFileEncry`：根据制造配置选择加密处理。
- 固件日志字符串确认中间路径为 `/var/tmp/db_user_cfg.xml`。

### 导入

- `_dbCfgFileDecry.constprop.4`：先尝试 `dbcCfgFileComKeyDecry`，再进入 `dbcCfgFileDecry`。
- `dbcCfgFileDecry`：按类型分派到 `aescbc_decry`、`DecryByAES`、`DecryByCRC` 或旧 `decry` 路径。
- `dbcCfgFileIsEncry`：识别文件是否加密。
- `dbcCfgFileVersion` / `dbcCfgFileUnVersion`：处理版本外层。
- `dbFileRestore`：完成数据库重载、产品/个人配置初始化、保存和恢复通知。

## 对现有 Type-4 工具的意义

现有工具对应的是 `dbcCfgFileDecry -> aescbc_decry` 这一条现代 Type-4 路径。固件同时保留 CRC、旧 AES 和通用密钥封装兼容分支，因此网页导入并不是只接受一种历史格式。

当前本地样本已通过外层长度、CBC、块链、zlib、头 CRC、数据 CRC 和 XML 全链校验；重建结果与原文件逐字节一致。这大幅降低格式不兼容的可能性。

## 下一步

1. 对 `dbcCfgFileDecry` 的条件分支建立“类型值 -> 解密函数 -> 错误码”表。
2. 逆向 `dbcCfgFileVersion` 的型号、版本和兼容性判断。
3. 跟踪 `dbFileRestore` 在写数据库前后的回滚点，确定导入失败是否会保留旧配置。
4. 全程先做本地静态分析，不连接或重启设备。

## 阶段 2：格式分派与错误边界

`dbcCfgFileDecry` 在读取 0x3c 字节头部后，对大端类型字段进行如下分派：

| 类型 | 路径 |
|---|---|
| 0 | `DecryByCRC` |
| 1 | `DecryByAES`，随后进入旧通用 `decry` |
| 2 | 旧 AES/通用解密兼容路径 |
| 3、4 | `aescbc_decry` |
| 其他 | 拒绝 |

因此当前 `config.bin` 的类型 4 与 `aescbc_decry` 精确对应，不是基于字符串推测。

已识别的返回边界（ARM `mvn` 立即数换算）：

- `-31`：空参数或文件打开/状态失败类路径。
- `-32`：固定长度头部读取不足。
- `-33`：版本数据读取/流处理失败。
- `-34`、`-35`：版本层文件读写失败。
- `-38`：magic 或格式类别不匹配。

错误码的业务名称仍需结合上层枚举确认，目前只记录可证实的触发位置。

## 恢复事务顺序

`dbFileRestore` 的顺序已经明确：

1. 发出恢复前事件并等待最多约 30000 ms。
2. 调用 `dbCPSaveCfg` 保存当前配置检查点；失败会立即退出，不进入重载。
3. 重置数据库管理器并加载默认配置。
4. 加载导入配置，初始化产品/个人配置。
5. 保存新数据库并发送恢复完成通知。

这说明破坏性重载前确实存在旧配置检查点，但函数本身在进入重载后没有对每个初始化调用逐一检查返回值。现阶段应把它视为“有备份基础”，而不是已经证明任何失败都能自动回滚。

新增 `tools/cspd-config-map.py`，可从带 `.symtab` 的 ARM `cspd` 自动提取 12 个关键函数、地址、大小和直接调用关系，便于换固件版本后重复对比。

## 阶段 3：版本层与备份位置

### `dbcCfgFileVersion` 的真实用途

进一步逐指令分析后修正命名造成的误解：该函数主要是**添加 0x80 字节文件版本封装头**，并不是执行固件版本升降级策略。

封装头包含：

- 四个固定哨兵：`0x99999999 / 0x44444444 / 0x55555555 / 0xAAAAAAAA`
- 头长度 `0x80`
- 格式类型 `4`
- 原始负载长度
- 两个由调用者传入的 16 位产品参数

`dbcCfgFileUnVersion` 会验证四个哨兵、头长、负载长度和文件读写完整性，然后剥离 0x80 字节头。当前函数中没有发现型号字符串比较、版本号大小比较或禁止降级判断。

调用关系扫描进一步确认：

- `dbcCfgFileVersion` 的直接调用者是 `dbGetModuleUserCfg`。
- 当前完整配置导入主链 `_dbCfgFileDecry.constprop.4 -> dbcCfgFileDecry` 不调用它。
- `dbcCfgFileUnVersion` 没有静态直接调用者，可能通过函数指针用于模块配置路径。

所以这个“版本层”属于模块配置封装，不是当前完整 `config.bin` 的主要兼容性门槛；继续在这里寻找固件降级限制属于错误方向。

### 配置检查点位置

固件字符串和数据库路径表确认：

- 当前持久配置：`/usercfg/db_user_cfg.xml`
- 默认配置：`/defcfg/db_default_auto_cfg.xml`
- 恢复前检查点：`/usercfg/db_backup_cfg.xml`
- 状态表：`/status/db_tbl_cfg.xml`
- 临时导入/解密文件位于 `/var/tmp/` 下

`dbFileRestore` 在重载前调用 `dbCPSaveCfg`，与 `/usercfg/db_backup_cfg.xml` 的用途吻合。该文件是后续实机恢复验证最关键的观察点，但本阶段未连接设备。

### 新方向

配置链已经不存在明显的“版本比较”缺口。下一步应转向：

1. 逆向调用 `dbFileRestore` 的 `dbAPIMsgDeal` / `dbEvtRestore`，还原网页导入最终错误码。
2. 检查恢复失败时是否存在把 `db_backup_cfg.xml` 写回的代码路径。
3. 分析内部持久 XML 的独立加密常量，但仓库只记录算法和占位符，不保存真实常量。

## 阶段 4：上层错误返回与自动回滚结论

### `dbFileRestore` 的三个入口

静态调用者只有三个：

1. `dbAPIMsgDeal`：正式 API/网页消息入口。它在调用前检查 `dbFileCtrlState(6)`，然后直接返回 `dbFileRestore` 的返回值，因此底层错误码可以传回网页层。
2. `dbEvtRestore`：内部事件入口；调用完成后继续广播事件，并固定返回 1，不向调用者保留详细恢复错误码。
3. `dbDebugCmdMsgDeal`：调试命令入口，支持多个恢复模式，调用后不单独处理详细返回值。

这说明网页导入理论上能获得底层错误码；若网页只显示统一失败提示，丢失发生在 `cspd` 之上的 Web/API 映射层。

### 备份写入路径

- `dbBackupUsrCfg*` 和 `dbFileSaveBackupCfg` 最终通过 `dbFileCopy` 写入备份目标。
- 开机、保存状态和升级路径都会触发用户配置备份。
- `dbFileRestore` 本身在重载前调用 `dbCPSaveCfg` 保存检查点。

### 自动回滚搜索结果

已对所有带符号函数扫描直接调用关系：没有发现 `dbFileRestore` 的失败分支调用 `dbFileCopy`、`dbBackupUsrCfg*` 或把备份文件重新加载回当前配置的路径。恢复函数进入重载后也没有统一的错误出口触发回写。

因此当前可证实的行为是：

- ✅ 覆盖前保存检查点。
- ✅ 早期失败不会进入破坏性重载。
- ❌ 尚无证据表明中途失败会自动把 `db_backup_cfg.xml` 写回。

实际操作应保留导出的原始 `config.bin`，不能把存在备份文件等同于自动回滚保证。

### 工具更新

`cspd-config-map.py` 现在覆盖 18 个配置、备份和恢复函数，并为每个目标同时输出正向调用和反向调用者；当前样本已完成回归运行。
