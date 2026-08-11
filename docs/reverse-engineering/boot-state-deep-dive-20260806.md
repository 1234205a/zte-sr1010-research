# SR1010 bootpara、环境块与启动状态深挖

日期：2026-08-06  
固件：`V1.0.0.2B5.8000`

## 新结论

对当前固件重新生成ARM64反汇编后，已把 `zteboot_save_bootpara` 收敛到 `0x840300ec..0x840301f4`。此前的 `uboot-full.asm` 来自旧版本样本，不能继续拿它的同地址指令解释当前固件；本轮已纠正这一工具链混用问题。

### bootpara结构

当前函数给出以下确定事实：

- `sizeof(T_BOOT_PARA) = 0x578`；
- 校验字段位于结构偏移 `0xc0`，宽度32位；
- 保存前先把该字段清零；
- 逐字节累加整个 `0x578` 字节结构；
- 把累加和写回 `+0xc0`；
- 随后按调用者提供的flash目标地址保存，并打印：

```text
##save bootpara @%#x size=0x%x sum=0x%08x
```

因此它不是CRC32，而是“校验字段清零后的无符号逐字节加和”。

升级/槽位选择函数还直接读取：

- `+0x04`：参与固件类别/状态判断；
- `+0x40/+0x44`：成对打印的状态字段；
- `+0x1e0`：当前/候选固件索引类字段；
- `+0x1e8`：版本上界或槽位数量相关字段，`0xffffffff`被视为无效。

这些字段语义仍需结合一次真实UART `print bootpara`输出或升级前后转储才能最终命名，但结构尺寸和校验算法已经闭环。

### 持久化位置

对整个当前NAND按 `0x200` 对齐扫描 `0x578` 字节结构，并验证上述加和规则，没有找到有效候选。这意味着当前bootpara不是一个裸露、页对齐的独立结构；它更可能：

1. 嵌在ZTE boot image/header内部且实际起点非页对齐；
2. 经坏块映射后由 `zbi` 提供逻辑地址；
3. 仅在升级时从镜像结构加载到RAM，再回写到镜像内计算出的偏移。

当前函数的调用参数中确实同时存在“结构指针”和“flash目标地址”，所以不能根据 `tags` 差异猜一个固定槽位字节。

## bootloader环境块复核

MTD bootloader中真正会变化的是 `0x80000..0x9ffff` 的标准U-Boot环境块：

- 前4字节是对剩余 `0x1fffc` 字节计算的标准CRC32；
- 当前CRC与重算值完全一致；
- 当前设备与旧设备只有CRC和 `fdtcontroladdr` 的运行时地址不同；
- `bootdelay=2`、串口stdin/stdout/stderr、TFTP地址及bootcmd一致。

因此此前“bootloader有一个128KiB块变化”并不代表CSPBOOT代码或密码逻辑变化，只是环境块CRC及运行时DTB地址变化。

## 可重复工具

新增 [`tools/boot-state-readonly.py`](tools/boot-state-readonly.py)，只读输出：

- 全flash哈希；
- U-Boot环境CRC校验、变量名和非敏感启动字段；
- tags魔数、声明长度和哈希；
- 双槽U-Boot哈希/一致性；
- 按已恢复算法扫描页对齐bootpara候选。

工具默认不打印MAC、序列号、无线口令或其他工厂敏感字段。

## 下一步

继续静态深挖的正确目标是 `0x8406dbc4` 保存调用及 `zteboot_update_bootpara` 的调用者，恢复传入的flash逻辑地址；现场最短闭环则是U-Boot中只读执行 `help`/可能存在的bootpara打印命令，并保存完整启动日志。
