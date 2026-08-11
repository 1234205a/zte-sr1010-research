# SR1010 可重复恢复工具箱

日期：2026-08-07  
入口：`tools/sr1010-tool.py`

## 目标

把此前分散的全闪存、双槽、网页固件和配置工具收束成一个入口。所有命令默认只处理本地
文件；提取和构建始终要求独立输出路径，不原地覆盖输入。

## 常用命令

完整闪存报告（128 MiB大小、SHA-256、双槽头和全部CRC）：

```powershell
python sr1010/tools/sr1010-tool.py flash-report whole-flash.bin
```

生成文件校验清单：

```powershell
python sr1010/tools/sr1010-tool.py manifest FILE --output FILE.manifest.json
```

提取槽或槽头：

```powershell
python sr1010/tools/sr1010-tool.py extract-slot whole-flash.bin current current-slot.bin
python sr1010/tools/sr1010-tool.py extract-header whole-flash.bin backup backup-header.bin
```

网页升级包：

```powershell
python sr1010/tools/sr1010-tool.py web-build whole-flash.bin candidate.bin
python sr1010/tools/sr1010-tool.py web-check candidate.bin
```

config.bin：

```powershell
python sr1010/tools/sr1010-tool.py config-decrypt config.bin config.xml
python sr1010/tools/sr1010-tool.py config-audit config.xml
python sr1010/tools/sr1010-tool.py config-pack config.xml rebuilt-config.bin
```

其他统一子命令：`nand-check`、`header-compare`、`header-rebase`、`versionstates`。
这些子命令把其后的参数原样传给经过验证的专用脚本；需要专用帮助时在末尾加 `--help`。

## 恢复资产分级

| 资产 | 用途 | 是否适合进Git |
|---|---|---|
| 128 MiB full flash | 最完整底层恢复 | 否，含设备配置 |
| 41 MiB slot镜像 | 单槽分析/底层恢复 | 否 |
| 0x510 slot header | 头部研究/换槽 | 否，可能含设备字段 |
| web candidate | 网页升级候选 | 否，含当前JFFS2 |
| config.bin/XML | 配置恢复 | 否，含凭据 |
| manifest JSON | 本地文件校验 | 可按需，默认本地 |
| 工具与无秘密报告 | 可重复分析 | 是 |

## 当前验证

工具箱已用当前128 MiB转储完成：全闪存报告、两槽CRC、槽头提取、网页候选包构建和独立
预检。没有向设备上传文件、写MTD或重启。
