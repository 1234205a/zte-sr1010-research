# SR1010 Bootloader 串口入口与“密码”校验逆向

日期：2026-08-06  
固件：`V1.0.0.2B5.8000`

## 结论

当前固件的 U-Boot 串口中断路径**没有发现密码输入、密码派生或密码校验函数**。现有证据更符合标准 U-Boot 行为：倒计时两秒，任意按键中断自动启动后进入命令行；并不存在一个等待从序列号、MAC 或 OTP 派生密码的 Bootloader 登录层。

这纠正了任务名称中的预设：本轮没有“算出一个 Bootloader 密码”，而是确认当前镜像里没有可供逆向的 Bootloader 密码校验链。

## 镜像边界

- MTD `bootloader`：flash `0x000000..0x0fffff`，SHA-256 `4625409fc9c6145eb7beefa3956b28bd68b34a1e01dc5675f35331c48620c269`；这是早期 BOOTROM/CSPBOOT 引导层，不是完整交互式 U-Boot。
- 槽1 U-Boot：flash `0x600000..0x6e3d0f`，ARM64 加载基址 `0x84000000`，长度 `0xe3d10`。
- 槽2 U-Boot：flash `0x2f00000..0x2fe3d0f`。
- 两槽 U-Boot 逐字节完全相同，SHA-256 均为 `00909e082c06d1ae3401a617a833c67d5472e4ffd71294f6f09258e382ba379f`。

## 串口中断证据

环境区明确保存：

```text
bootdelay=2
stdin=serial
stdout=serial
stderr=serial
```

U-Boot 正文包含标准提示：

```text
Hit any key to stop autoboot: %2d
```

同一字符串区还有厂商升级快捷键：

```text
Hit 1 to upgrade software version.
```

整份 U-Boot 明文字符串中没有 `Password:`、console password、口令错误、登录重试、MAC/SN/OTP 派生等提示。环境区也没有 `bootstopkey`、`bootdelaykey`、`bootstopkeysha256` 或类似的 keyed-autoboot 变量。

因此静态证据支持：串口数据真正送达 U-Boot 时，倒计时阶段的任意字符就是停止启动的条件，没有第二层密码比较。

## 容易误判的字符串

镜像中的以下内容不属于串口 Bootloader 登录：

- `user`、`pass`、`Get UserName or PassWord from Tftp failed!`、`UserName or PassWord ERROR!`：属于 TFTP 网络传输认证/重试逻辑；
- `USERNAME`、`USERPASSWD`：位于网络/协议数据结构区域，并非 autoboot 入口附近的口令常量；
- rootfs 中的 `passwd`、`hmkpasswd`、`chpasswd`：属于 Linux 用户态；
- CSPBOOT 的 `Debug mode!`、`Trigger debug mode !`：属于更早的启动模式选择，不等于 U-Boot 密码提示。

对镜像做字符串交叉检查后，没有证据把这些字段连接到 autoboot 中断路径，也没有发现序列号、MAC 或 OTP 进入字符串比较/哈希后控制 U-Boot CLI 的链路。

## 仍需现场验证的边界

目前摸不到硬件，所以尚未完成 UART 电气层验证。Linux 命令行含 `serial=close`，板级代码或 GPIO 复用可能让 UART 引脚在某阶段静默；这属于“串口是否可见/可输入”的硬件与早期启动门控问题，不是密码派生问题。

回家后的最小只读验证：连接 3.3V UART（共地，只接 RX/TX/GND，不接 VCC），上电后在两秒倒计时内发送任意字符，观察是否出现 U-Boot 提示符。该验证不执行 `saveenv`、`nand write/erase` 或升级命令，不会修改 flash。

## 安全与实际意义

若 UART 引脚可用，物理接触者很可能不需要 Bootloader 密码即可中断启动并使用 U-Boot 命令面；真正的限制将转移到串口引脚可达性、`serial=close` 门控、命令裁剪和 secure-boot 对启动镜像的验证，而不是口令强度。

下一条离线路线应分析 CSPBOOT 的 `Trigger debug mode !` 条件以及 U-Boot 命令表，确认串口门控来自按键/GPIO、环境变量还是早期寄存器设置。
