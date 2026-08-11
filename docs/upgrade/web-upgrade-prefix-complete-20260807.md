# SR1010 网页升级包前缀与当前版本重建闭环

日期：2026-08-07  
状态：离线格式、偏移和全部已知 CRC 闭环；未向设备上传。

## 最前端私有封装

`UpgradeVerifyCspFwMagic` 精确检查外层前16字节：

```text
99999999 44444444 55555555 aaaaaaaa   # 四个小端 uint32
```

外层结构共20字节：

```c
struct outer {
    uint32_t magic[4];
    uint32_t skipped_header_size;  // 当前布局为 0x20c
};
```

`cspd` 读取它后跳到 `0x14 + skipped_header_size`，读取 `0xf4` 字节 common header。
当前布局满足：

```text
0x14 + 0x20c + 0xf4 = 0x314
```

签名长度位于 common header 开头，当前值为0，因此 `VerifySign` 成功返回。被跳过的 `0x20c`
区域在零签名形态下可保持全零。

## 完整文件映射

```text
0x000000..0x000013  outer（CSP magic + 0x20c）
0x000014..0x00021f  零签名保留区
0x000220..0x000313  0xf4 common header
0x000314..0x180313  槽前导区，0x180000字节
0x180314..0x180333  kernel自身32字节外部对象
0x180334..0x6cdf33  kernel CRC覆盖数据，0x54dc00字节
0x6cdf34..0x6e0313  原槽对齐/保留区，0x123e0字节
0x6e0314..0x1e60313 fs数据，0x1780000字节
```

最简且不会破坏对齐的方法不是手工拼每段，而是：构造 `0x314` 前缀后，直接附加目标槽从
slot base 到 header address 之前的全部 `0x1e60000` 字节。这样32字节对象和保留区会原样
保留，kernel/fs offset自然吻合。

## 重建工具

```powershell
python sr1010/tools/build-current-web-firmware.py whole-flash.bin output.bin
```

工具从当前槽头读取长度和偏移，重新计算 boot、kernel、当前JFFS/fs及common header CRC，
验证最终长度必须等于 `fs_offset + fs_length = 0x1e60314`，再写新文件。

当前JFFS2已经包含设备配置和运行时变化，所以生成物只保存在本机，不上传Gitea。它是当前
设备快照的零签名网页升级候选包；在实际上传前仍应单独安排回滚窗口，不能把静态闭环等同于
已经做过实机写入测试。

独立预检器（不复用构建器的计算结果）如下：

```powershell
python sr1010/tools/web-firmware-preflight.py output.bin
```

它重新定位 common header，并独立检查 CSP magic、common CRC、boot CRC、kernel CRC、fs
CRC、组件边界、签名长度、key、版本和产品字段。
