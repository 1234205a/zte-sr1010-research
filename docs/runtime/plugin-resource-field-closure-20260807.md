# SR1010 pluginmgr资源字段闭环：RAM偏移正确，固件复制flash值

日期：2026-08-07

## 纠正结论

上一阶段数据库把请求中的`FLASH_KB=8192, RAM_KB=32768`保存为两个8192。现已通过当前B2
固件三段代码交叉确认：调用器中的`OFF_FLASH=0x7c0`和`OFF_RAM=0x7e0`都是正确的，问题在
pluginmgr自身。

因此不修改`cm-plugin-install-ssend.c`的两个资源偏移。数据库的AllocatedMemory不是实际传入
RAM值的可靠证据。

## mqtt转换层

`mqtt::convertParamListAndPluginCfgStruct`：

```text
0x46718 -> flash ctype base +0x7c0
0x46744 -> ram   ctype base +0x7e0
```

ctype实际32位值位于基址`+0x1c`，所以pluginmgr收到的值地址分别是：

```text
flash.value = request + 0x7dc
ram.value   = request + 0x7fc
```

## pluginmgr消费层

当前`PluginCmapiInstall`对两个地址的全部引用：

```text
flash.value +0x7dc: 3 references
  0x00013254 ldr r3, [sl, #0x7dc]   # 必须非零
  0x00013338 ldr r0, [sl, #0x7dc]   # 磁盘总配额检查
  0x000136d8 ldr r3, [sl, #0x7dc]   # 取flash值

ram.value +0x7fc: 1 reference
  0x00013260 ldr r3, [sl, #0x7fc]   # 只检查非零
```

`0x136d8`之后，同一个从flash读取的`r3`连续写入新PluginInfo结构的两个32位资源字段：

```text
0x136e4 str r3, [r4, #-0x2c]
0x136ec str r3, [r4, #-0x0c]
```

中间没有再次读取`ram.value`。这精确解释了为什么数据库的
`AllocatedDiskSpace/AllocatedMemory`都变成8192。

## 实际影响

- RAM请求仍必须非零，否则安装在`0x13260..0x13268`被拒绝；
- RAM数值没有参与后续配额计算，也没有写入PluginInfo；
- flash值参与约40000 KiB的累计磁盘配额检查；
- 两个数据库资源字段最终都是flash值；
- 这看起来是厂商代码缺陷或有意的字段归一化，不是调用器偏移错误；
- 当前8192只是数据库元数据，不代表Linux cgroup真的把WireGuard限制到8MiB。本轮未发现
  nativeC存在按该字段施加的内存cgroup动作。

为了与固件行为一致，后续安装请求仍提供语义正确的flash和ram值，但验收时不再要求数据库
显示不同值。若管理界面需要展示预计内存，应由net-runtime自己的只读状态文件提供，而不是
读取PluginInfo.AllocatedMemory。

## 可重复检查

新增：[`tools/plugin-resource-field-audit.py`](tools/plugin-resource-field-audit.py)

```powershell
python sr1010/tools/plugin-resource-field-audit.py PATH_TO_CURRENT_PLUGINMGR
```

当前B2结果为`PASS`。脚本依赖现有分析环境中的`pyelftools`和`capstone`，只读取ELF，不连接
路由器。

## 设备状态

本项完全离线分析，没有修改设备。`sr1010-net-runtime`继续保持：

```text
Enable=0 Status=1 PID=0 StartMode=0
```

下一步可以停止研究资源字段，转入真实配置的安全导入器设计。

