# SR1010 当前双固件槽与零签名实机状态

日期：2026-08-07  
来源：只读 `/proc/csp/versionstates`；序列号未写入仓库。

## 当前活动槽

```text
活动标志          current=1，backup=0
坏槽标志          current=0，backup=0
current boot      0x00600000
current image     0x00780000
current header    0x02460000
current jffs      0x00ce0000
backup image      0x03080000
backup header     0x04d60000
backup jffs       0x035e0000
槽边界             low 0x00600000..0x02f00000
                   high 0x02f00000..0x05800000
maxversionum      4
```

两个槽当前都没有被标记为坏，低地址槽是活动槽。低/高槽各自跨度约 `0x2900000`（41 MiB），
边界与此前 NAND 分区静态分析吻合。

## 最有用的新结论

当前实际运行固件报告：

```text
curversignsize = 0
```

这把 `VerifySign(sign_len=0)` 从“存在可达兼容分支”进一步闭环为“当前原厂 B2 活动固件本身
就在使用零签名长度”。因此制作格式兼容包时，零签名不是脱离现实的异常输入，而是当前设备
接受并正在运行的固件形态。仍然需要保持产品、版本、组件摘要、地址和长度结构正确。

## 本地复核工具

```powershell
python sr1010/tools/versionstates-readonly.py versionstates.txt
```

默认不输出序列号；只有显式加 `--show-serials` 才显示，避免误传设备标识。

本次没有改变活动槽、坏槽标志、启动状态或任何配置，也没有重启设备。
