# SR1010 nativeC只读网络状态面板原型

日期：2026-08-07

## 产物

新增`build-net-runtime-status-ipk.py`，确定性生成`sr1010-net-status`旧式IPK。插件只读取：

- TUN设备是否存在；
- `wg`工具和`wg0`接口是否存在；
- 默认路由是否存在；
- 可用内存；
- DDNS是否配置。

它不会读取或输出WireGuard私钥、Cloudflare Token、接口地址、默认网关或公网IP，也不会
创建接口、修改路由、iptables或DNS。状态写入插件自己的`state/status.json`，自带静态
`panel.html`负责可视化。

## 生命周期

```text
StartMode=0
start.sh  -> 单实例采集循环，每60秒原子更新status.json
stop.sh   -> 终止采集器并删除PID文件
health.sh -> 立即采集一次并输出JSON
```

面板当前不启动HTTP监听器，避免未经设计就暴露新端口。后续可由仅绑定LAN/localhost的最小
服务器提供`panel.html`和`state/status.json`，或者接入路由器已有Web权限体系。

## 验证

生成包已通过`plugin-ipk-audit.py`：

```text
StartMode=0
start_file=yes
stop_file=yes
explicit_parent_dirs=yes
result=PASS
```

此外把`collect.sh`改为只写nativeC `/tmp`后做了一次现场执行，输出：

```json
{"tun":"yes","wg_tool":"no","wg0":"no","default_route_present":"yes","ddns":"not_configured"}
```

临时脚本和状态目录随后已删除。没有安装IPK、建立监听、修改网络或重启。

## 构建

```powershell
python sr1010/tools/sr1010-tool.py build-net-status OUTPUT.ipk
python sr1010/tools/sr1010-tool.py plugin-ipk-audit OUTPUT.ipk
```

