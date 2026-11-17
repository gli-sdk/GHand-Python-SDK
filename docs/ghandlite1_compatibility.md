# GHandLite1 兼容说明

本说明记录仓库保留的 L1 配置和协议实现，参考 C++ SDK 与 L1 V2.2 协议。当前 V3.1.0 的正式产品支持范围保持 README 的约定：L1 用户使用对应的 SDK 2.x。离线测试不代表三种通信已完成真机验收。

## 产品配置

- 型号：`L1-6A11D-S01`，设备名称：`GHand Lite 1`。
- 11 个反馈关节、6 个主动关节。`THUMB_TMC_AA` 限位为 30–60°，位置控制按该范围限制目标角度。
- 启用触觉；拇指、食指、中指、无名指、小指分别为 38、31、31、31、31 组采样点。

## 通信布局

| 项目 | L1 | GHand5 |
|---|---|---|
| Modbus 关节反馈 | 从 0x105C 起，按配置中的11关节顺排，每关节5寄存器 | 0x105F + JointId × 5 |
| Modbus 主动关节控制 | 从 0x0261 起，按主动关节顺序，每关节4寄存器 | 每关节6寄存器 |
| Modbus 整手状态 | 0x1051 起11寄存器 | 0x1051 起14寄存器 |
| EtherCAT 整手反馈头 | 22字节 | 28字节 |
| EtherCAT 单关节反馈 | 10字节 | 10字节 |
| EtherCAT 单关节命令 | 8字节 | 12字节 |

L1 整手状态为 state、6字节 warning、6字节 fault、6字节 critical、int16 温度。EtherCAT 关节反馈为 state/error/mode/reserved 各1字节，以及 angle/speed/current 各2字节。角度以0.1°编码，速度和电流为有符号百分比。

L1 关节命令仅包含 mode/stop、angle、speed、current，不包含 kp/kd；mode 的闭环选择保留位写0。完整 EtherCAT TPDO 为650字节，RPDO 为50字节，均包含配置中全部相应关节。L1 不采用 GHand5 的缩短拇指触觉兼容布局。

RS485 按手类型寄存器探测 L1，不执行 GHand5 的连接/断开控制握手。CANFD 保留连接握手，并将目标节点的 FC44 异常响应识别为 L1 节点存在，随后继续验证连接。

## 能力与错误

`GHand.move_joints()` 对 L1 的 MIT 模式、关节 MIT 模式、非零 kp/kd 或半闭环设置抛出 `NotImplementedError`，发生在发送命令之前。位置、速度、电流和合法 CUSTOM 控制沿用现有接口。

L1 的 PID 与堵转容差读写返回不支持（`NotImplementedError`）。位置传感器版本、拇指触觉子版本和四指触觉子版本返回 `N/A`，不访问对应的 GHand5 专用字段。主控、触觉 MCU、电机驱动和固件包版本仍使用既有版本查询入口。

协议向量和模拟验证位于 `tests/test_ghandlite1_protocol.py`，同时检查 GHand5 命令布局。运行：

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_ghandlite1_protocol.py -q
```
