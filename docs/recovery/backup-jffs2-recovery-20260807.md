# SR1010 备用槽JFFS2恢复与历史节点结论

日期：2026-08-07  
输入：当前设备128 MiB全闪存转储；所有解密结果和文件正文只留本机。

## 恢复流程

1. 活动槽rootfs：`0x00ce0000..0x02460000`，当前已是明文JFFS2。
2. 备用槽rootfs：`0x035e0000..0x04d60000`，仍是AES-128-ECB封装。
3. 用已从CSPBOOT恢复的16字节rootfs常量解密备用槽。
4. 对两份`0x1780000`字节镜像逐字节比较。
5. 用新的参数化JFFS2工具分别恢复目录、文件及删除dirent。

## 最终结果

```text
active rootfs SHA-256:
e7295bb6aa714a62c9856413c18cfedf492fca4d08c49cfc2d8e4e5c19991127

decrypted backup rootfs SHA-256:
e7295bb6aa714a62c9856413c18cfedf492fca4d08c49cfc2d8e4e5c19991127

不同字节数：0
```

备用槽解密后与活动槽逐字节完全相同。两边JFFS2均解析出8536个有效节点和927个普通文件；
按相对路径、长度及文件SHA-256组成的文件树也完全相同。

因此备用槽不是更旧或更干净的版本，也不包含活动槽没有的旧配置、隐藏账号或服务开关。
它只是相同rootfs的AES封装副本；所谓双槽“巨大差异”全部来自一个明文、一个ECB密文。

## 删除和覆盖节点

解析器扫描所有dirent版本，并为最终inode为0的路径寻找最近一次非零inode。本镜像中：

```text
recovered_deleted = 0
```

也就是说，这个只读系统rootfs没有可恢复的删除文件墓碑。`/etc/passwd`、`/etc/shadow`、
Dropbear主机密钥及容器内对应文件在两个槽中都存在且内容相同；正文没有写入仓库。

这不等于`usercfg`、`defcfg`和`Plugin`三个独立JFFS2分区没有历史节点；它们不属于双固件
rootfs槽，已经由各自的恢复流程处理。

## 可重复工具

```powershell
python sr1010/tools/sr1010-tool.py rootfs-compare whole-flash.bin --key ROOTFS_KEY
python sr1010/tools/sr1010-tool.py jffs2-extract decrypted.bin output-dir `
  --offset 0 --length 0x1780000 --recover-deleted
```

本项仅操作离线镜像，没有连接、修改或重启路由器。
