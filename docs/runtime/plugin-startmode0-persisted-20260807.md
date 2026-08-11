# SR1010 hello插件StartMode修正已持久保存

日期：2026-08-07

在保持插件禁用的前提下，已把设备现有`PluginInfo`记录正式修正并调用数据库save：

```text
Name=sr1010-hello
Enable=0
Status=1
PID=0
StartMode=0
```

修正只影响hello插件下一次进入PluginAutoStart时选择nativeC容器，不会立即启动程序，未重启、
未修改网络和MTD分区。现在设备端记录与修正后的IPK构建器一致。

新增`plugin-ipk-audit.py`，它会离线检查：旧式tar-IPK三成员、显式父目录、Start/Stop脚本
是否存在，以及nativeC插件是否使用`StartMode=0`：

```powershell
python sr1010/tools/sr1010-tool.py plugin-ipk-audit FILE.ipk
```

当前修正版hello包检查结果为PASS。下一次若要验证真正开机自动启动，只需先把Enable正式设为1，
再经用户当次授权重启；目前仍保持禁用，不会在意外重启后自动运行。

