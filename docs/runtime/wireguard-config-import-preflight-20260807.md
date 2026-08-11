# SR1010 WireGuard配置安全导入与无流量预检

日期：2026-08-07

## 当前完成度

完成本地配置导入器和nativeC设备侧预检脚本，并用一次性随机私钥完成实机闭环。没有读取用户
现有WireGuard配置，没有生成持久peer，没有替换插件内的占位配置。

`sr1010-net-runtime`仍是：

```text
Enable=0 Status=1 PID=0 StartMode=0
```

## 本地导入器

工具：[`tools/wg-config-import.py`](tools/wg-config-import.py)

它接受`wg setconf`格式，不接受`wg-quick`的系统配置命令。检查项目：

- 必须恰好一个`[Interface]`，可有多个`[Peer]`；
- PrivateKey/PublicKey/PresharedKey必须是base64编码的32字节；
- Endpoint必须是`HOST:PORT`或`[IPv6]:PORT`；
- AllowedIPs必须是合法CIDR；
- 默认保护设备 LAN `192.168.50.0/24`和现有管理隧道 `10.8.0.0/24`；
- 默认拒绝覆盖受保护路由，包括`0.0.0.0/0`和`::/0`；
- 明确拒绝`PreUp/PostUp/PreDown/PostDown`；
- 也拒绝不能直接交给`wg setconf`的Address、DNS、Table、SaveConfig；
- 未知字段和重复字段均失败；
- 默认只输出脱敏JSON：私钥只显示present，peer公钥只显示SHA-256短指纹；
- `--output`创建规范化文件并强制0600，不在终端打印配置内容。

示例：

```powershell
python sr1010/tools/wg-config-import.py INPUT.conf --require-peer `
  --output C:\private\sr1010-wg0.conf
```

真实配置若确实需要默认路由或访问受保护网段，必须显式使用`--allow-protected-route`，后续仍需
单独审计runtime.env里的实际路由；该开关不会自动修改设备。

## 本地负面测试

使用三份随机一次性配置：

```text
合法最小配置                         PASS
包含 PostUp = echo bad               FAIL: forbidden/unsupported
Peer AllowedIPs = 0.0.0.0/0          FAIL: overlaps protected route
```

测试输出没有包含任何密钥。随机配置及规范化副本在实机验证后从本机删除。

## 设备侧预检

可重复脚本：[`tools/wg-config-preflight.sh`](tools/wg-config-preflight.sh)

脚本在nativeC运行，要求输入配置已经是0600。它创建固定临时接口`wg-import-test`，只执行
`wg setconf`，不执行`ip address add`、`ip route add`、DNS或iptables。退出trap总会终止自身
进程并删除接口和UAPI socket。

本轮一次性随机配置实测：

```text
PREFLIGHT_RC=0
MODE=600
SETCONF=PASS
LISTEN_PORT=51820
PEERS=0
```

清理和网络不变性：

```text
wg-import-test interface absent
wg-import-test socket absent
nativeC staged config absent
host staged config absent
route table before/after byte-identical
nativeC RUNNING
```

本轮配置只有Interface和随机私钥，所以peer为0；这验证的是秘密文件权限、ARM工具、UAPI和配置
加载链，而不是联网能力。

## 秘密边界

- Git只保存工具、规则和脱敏结果，不保存测试或真实密钥；
- 本轮随机测试密钥已从本机和设备删除；
- 设备正式配置目标仍是`/opt/sr1010-net-runtime/config/wg0.conf`、权限0600；
- 在真实配置通过本地和设备两层预检前，插件继续保持禁用；
- 上传真实配置时不在命令行、日志或报告回显内容。

## 下一步需要的输入

需要用户指定本机真实WireGuard配置文件路径，或者导出一份新的客户端配置。下一轮先只运行
本地脱敏审计；通过后上传并做同样的无地址、无路由临时预检，仍不启动正式`wg-nrt0`。

