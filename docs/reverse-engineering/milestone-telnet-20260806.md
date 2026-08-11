# SR1010 当前固件配置解密与LAN Telnet实机里程碑

日期：2026-08-06  
设备：用户自有 ZTE SR1010  
当前固件：`V1.0.0.2B5.8000`

> 公开版本中的设备账号、密码和配置指纹均已替换为占位符。

## 当前配置样本

- 文件：`C:\Users\USER\Downloads\config.bin`
- 大小：34,344字节
- SHA256：`<ORIGINAL_CONFIG_SHA256>`
- 解密：成功，5个zlib块，明文286,082字节
- 明文SHA256：`<PLAINTEXT_CONFIG_SHA256>`

## 修改版

- 本地文件：`C:\Users\USER\Downloads\config-telnet-lan.bin`
- 大小：34,344字节
- SHA256：`<MODIFIED_CONFIG_SHA256>`
- 唯一修改：
  - `TelnetCfg[0].TS_Enable: 0 -> 1`
  - `TelnetCfg[0].Lan_Enable: 0 -> 1`
  - `Wan_Enable`保持`0`
- 生成后已再次解密，自检确认仅上述两个字段变化。

## 实机结果

通过设备配置恢复页面上传修改版后，路由器成功重启。经受控管理通道进入设备 LAN 实测：

```text
192.168.50.1 ping：成功
192.168.50.1:23：开放
192.168.50.1:80：开放
192.168.50.1:443：开放
```

结论：Type-4解密、重打包、CRC、zlib、AES-256-CBC和最小字段修改已通过真实硬件闭环；LAN Telnet成功启用，WAN Telnet保持关闭。

## 当前账号密码

### Telnet

```text
地址：192.168.50.1
端口：23
用户名：root
密码：<TELNET_PASSWORD>
权限等级：3
```

### Web / DevAuthInfo

```text
地址：https://192.168.50.1/
用户名：admin
密码：<WEB_PASSWORD>
权限等级：1
```

## 回滚

- 原始备份：`C:\Users\USER\Downloads\config-original-V1.0.0.2B5.8000.bin`
- 原始备份SHA256：`<ORIGINAL_CONFIG_SHA256>`
- 如需关闭Telnet，将`TS_Enable`和`Lan_Enable`恢复为`0`，或从Web恢复原始配置。

