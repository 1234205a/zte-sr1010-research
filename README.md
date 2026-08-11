# ZTE ZXSLC SR1010 使用说明

本仓库用于处理自己的 SR1010：解密、检查、修改和重新打包 `config.bin`，以及分析 NAND 固件布局。请始终保留原始备份。

## 1. 安装

需要 Python 3.10+：

```powershell
python -m pip install pycryptodomex
```

## 2. 处理 config.bin

以下命令中的文件名替换为你自己的文件。

```powershell
# 查看结构
python tools/config-bin-tool.py inspect config.bin --model SR1010

# 解密为 XML
python tools/config-bin-tool.py unpack config.bin config.xml --model SR1010

# 检查敏感开关
python tools/config-bin-tool.py audit config.bin --model SR1010

# 验证能否无损解密并重打包
python tools/config-bin-tool.py roundtrip config.bin --model SR1010
```

修改配置前，先确认 `roundtrip` 成功。可修改字段以 `edit --help` 和工具白名单为准：

```powershell
python tools/config-bin-tool.py edit --help
python tools/config-bin-tool.py edit config.bin config-mod.bin `
  --set TABLE:ROW:FIELD=0 --model SR1010
python tools/config-bin-tool.py verify config-mod.bin --model SR1010
```

如果直接修改了解密后的 XML：

```powershell
python tools/config-bin-tool.py pack config.xml config-new.bin --model SR1010
python tools/config-bin-tool.py verify config-new.bin --model SR1010
```

重新导入前，比较修改范围并准备原始 `config.bin` 回滚副本。格式说明见 [`config.bin` 往返分析](docs/reverse-engineering/config-bin-roundtrip-20260807.md)。

## 3. 分析固件

```powershell
python tools/sr1010-tool.py --help
```

常用步骤：

1. `manifest`：记录原文件大小和 SHA-256。
2. `flash-report`、`nand-check`：检查 NAND 与分区布局。
3. `extract-header`、`extract-slot`：提取双槽头和固件槽。
4. `firmware-layout`：提取 kernel/rootfs。
5. `header-compare`：比较两个固件槽。
6. `web-check`、`upgrade-policy`：检查升级包匹配关系。
7. `recovery-kit`：生成本地恢复材料。

详细资料：

- [NAND 固件分析](docs/reverse-engineering/firmware-analysis-20260806.md)
- [启动链分析](docs/reverse-engineering/boot-chain-six-part-audit-20260806.md)
- [升级头格式](docs/upgrade/web-upgrade-header-layout-20260807.md)
- [恢复说明](docs/recovery/recovery-guide-plain-20260807.md)
- [工具索引](tools/README.md)

## 4. 测试

```powershell
python tools/test-config-bin-tool.py
python tools/test-cf-ddns-v012.py
```

测试不需要真实设备，也不会连接路由器。

## 注意

- 不要上传真实 `config.bin`、解密 XML、完整 NAND dump、VPN 密钥或云服务 Token。
- 仓库中的地址和占位符不要直接用于你的设备。
- 写入配置或固件前必须保留可恢复的原始备份。

## 致谢

感谢 [cnjn](https://github.com/cnjn) 分享初始研究样本：[恩山原帖](https://www.right.com.cn/forum/forum.php?mod=viewthread&tid=8462464) / [GitHub 固件](https://github.com/cnjn/ZXSLC_SR1010/releases/tag/1)。
