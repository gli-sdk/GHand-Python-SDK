# GHand Python SDK

[![Version](https://img.shields.io/badge/version-v3.1.0-blue.svg)](src/ghand/version.py)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

[English](README.md)

GHand 灵巧手官方 Python SDK，提供 EtherCAT、CAN-FD、RS-485 通信接入，以及关节控制、触觉感知、碰撞检测和自适应抓取能力。

## 目录

- [主要功能](#主要功能)
  - [产品支持矩阵](#产品支持矩阵)
- [文档](#文档)
- [系统要求](#系统要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [通信说明](#通信说明)
- [示例](#示例)
- [项目结构](#项目结构)
- [开源与生态资源](#开源与生态资源)
- [更新日志](#更新日志)
- [贡献指南](#贡献指南)
- [支持与反馈](#支持与反馈)
- [许可证](#许可证)

## 主要功能

### 产品支持矩阵

以下功能适用于当前 V3.1.0 的 GHand5。**GHandLite1（L1）请使用 SDK 2.xx（2.x）**，并遵循对应版本的 README、API 和协议文档。

| 产品 | SDK 版本 | 通信方式 | 控制与触觉能力 |
| --- | --- | --- | --- |
| GHand5 | 当前 V3.1.0 | EtherCAT、CAN-FD、RS-485 | 位置、速度、电流、MIT、CUSTOM；触觉反馈、回调、开关、调零和显示 |
| GHandLite1（L1） | 使用 2.xx（2.x），如 [V2.2.2](https://github.com/gli-sdk/GHand-Python-SDK/tree/V2.2.2) | 参见对应 2.x 文档 | 参见对应 2.x 文档 |

仓库保留的 GHandLite1 类型和配置文件不代表 V3.1.0 支持连接该产品。L1 用户请先切换至对应的 2.x 版本，再按该版本说明安装。

- **设备控制**
  - 通过 EtherCAT、CAN-FD 或 RS-485 打开和关闭 GHand 设备。
  - 读取固件、固件包、序列号、产品名称、左右手类型和组件版本。
  - 清除故障、初始化关节、停止运动，并执行常用设备操作。

- **关节控制**
  - 按位置、速度或电流模式控制单个或多个关节。
  - 读取当前关节角度、速度、电流、状态和错误反馈。
  - 根据产品配置自动限制主动关节命令范围。

- **触觉感知**
  - 在支持触觉的产品上打开或关闭触觉传感器。
  - 读取触觉数据，并执行触觉基准清零。

- **碰撞检测**
  - 在执行运动前检查目标姿态。
  - 支持设置安全余量，并在检测到碰撞时返回安全角度。

- **自适应抓取**
  - 内置 `ghand.adaptive_grasp` 包，提供力感知保持和抓取流程示例。

## 文档

详细技术规格和 API 参考请查看 [Python SDK 开发者文档](https://fcnzogxju7xr.feishu.cn/docx/PlY7dUod5o3tZYxzXiUc0BN1nyd)。

本地 Sphinx 文档源码位于 `docs/`。

其他本地说明：

- [日志配置](docs/logging.md)
- [错误处理](docs/error_handling.md)
- [订阅与线程](docs/subscription_threading.md)

## 系统要求

| 平台 | 要求 |
| --- | --- |
| Python | 3.10 或更高版本 |
| Linux | Ubuntu 22.04/24.04 LTS (x86_64 / aarch64), glibc >= 2.35 |
| Windows | 10 / 11 |
| macOS | 12+ (Intel x86_64 / Apple Silicon arm64) |

## 安装

### 前置条件

- **Python** 3.10 或更高版本
- **Windows**：使用 EtherCAT 时需要安装 [Npcap](https://npcap.com/)
- **Linux**：构建原生依赖时需要 `build-essential` 和 `python3-dev`
- **macOS**：CAN-FD 和 RS-485 无需额外依赖。EtherCAT 通过 pcap 访问原始套接字需要 `sudo` 权限(macOS 无 Linux `setcap` 的持久化能力等价物)。

### 从源码安装

```bash
git clone https://github.com/gli-sdk/GHand-Python-SDK.git
cd GHand-Python-SDK
pip install -e .
```

仅在需要碰撞检测功能时安装对应依赖：

```bash
pip install -e ".[collision]"
```

Gitee 镜像：

```bash
git clone https://gitee.com/glitech/GHand-Python-SDK.git
cd GHand-Python-SDK
pip install -e .
```

仅在需要碰撞检测功能时安装对应依赖：

```bash
pip install -e ".[collision]"
```

## 快速开始

运行示例前，请确认 GHand 硬件已连接并上电。

```bash
python examples/tutorial/01.get_basic_info.py
```

最小 EtherCAT 示例：

```python
import logging

from ghand import CommType, GHand, ProductType, configure_logging

configure_logging(level=logging.INFO)

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)

try:
    if not hand.open("auto"):
        raise RuntimeError("Connection failed")
    print("Firmware:", hand.get_firmware_version())
    print("Device:", hand.get_device_name())
finally:
    hand.close()
```

以下版本查询代码应放在上例连接成功后、关闭连接之前：

```python
print("Firmware package:", hand.get_firmware_package_version())
print("Position sensor:", hand.get_position_sensor_version())
print("Tactile MCU:", hand.get_tactile_sensor_version())
print("Motor driver:", hand.get_motor_driver_version())
print("Thumb tactile sensor:", hand.get_thumb_tactile_sensor_version())
print("Finger tactile sensor:", hand.get_finger_tactile_sensor_version())
```

整手 CUSTOM 模式通过各关节的 `control_mode`、`loop_type` 和 `control_state` 控制行为。以下代码应在连接成功后、关闭连接之前执行：

```python
from ghand import (
    HandControlMode, JointCommand, JointControlMode,
    JointControlState, JointId, JointLoopType,
)

ok = hand.move_joints(
    [
        JointCommand(
            id=JointId.THUMB_MCP,
            control_mode=JointControlMode.POSITION,
            control_state=JointControlState.RUNNING,
            loop_type=JointLoopType.CLOSED_LOOP,
            angle=30,
            velocity=10,
            current=20,
        ),
    ],
    hand_control_mode=HandControlMode.CUSTOM,
)
if not ok:
    raise RuntimeError("Failed to send joint command")
```

角度单位为度，速度和电流单位为百分比。位置模式中的速度和电流是限值，应提供非零值。同一手指仲裁组内的控制模式和反馈环路必须一致，详见 [CUSTOM 示例](examples/tutorial/14.custom_control.py)。

`move_joints()` 返回成功表示命令已发送，实际执行状态需通过 `get_hand_info()` 和 `get_joints()` 确认。`close()` 关闭通信连接；需要停止保持或释放驱动力时，应先发送 `stop()` 或 `disable_hand()`，确认反馈后再关闭连接。

最小 CAN-FD 示例：

```python
import logging

from ghand import CommType, GHand, ProductType, configure_logging

configure_logging(level=logging.INFO)

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.CANFD)
try:
    if not hand.open("auto", slave_id=0x31):
        raise RuntimeError("Connection failed")
    print("Device:", hand.get_device_name())
finally:
    hand.close()
```

最小 RS-485 示例：

```python
import logging

from ghand import CommType, GHand, ProductType, configure_logging

configure_logging(level=logging.INFO)

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.RS485)
try:
    if not hand.open("auto", slave_id=0x31):
        raise RuntimeError("Connection failed")
    print("Device:", hand.get_device_name())
finally:
    hand.close()
```

## 通信说明

### Linux EtherCAT 权限

EtherCAT 需要原始套接字权限。如果遇到权限错误，可以为 Python 解释器授予能力：

```bash
sudo setcap 'cap_net_raw,cap_net_admin=eip' $(which python3)
```

### macOS EtherCAT 权限

macOS 下 EtherCAT 通过 pcap 使用原始套接字,需要 root 权限。使用 `sudo` 运行 Python 脚本:

```bash
sudo python3 examples/tutorial/01.get_basic_info.py
```

### Linux RS-485 串口

Linux 下使用 USB-RS485 转接器时，SDK 自动发现优先扫描 `/dev/serial/by-id/*`、`/dev/ttyUSB*`、`/dev/ttyACM*` 和 `/dev/ttyAMA*`。如果使用内置串口，请在 `open()` 中显式传入设备路径。

常用检查命令：

```bash
lsusb
ls -l /dev/ttyUSB* /dev/ttyACM* /dev/serial/by-id/ 2>/dev/null
python3 -m serial.tools.list_ports
```

如果串口设备存在但无法打开，请确认当前用户属于 `dialout` 组：

```bash
groups
sudo usermod -aG dialout $USER
```

修改用户组后需要重新登录。

### CAN-FD 适配器

CAN-FD 模式支持 ZQWL-CANFD CDC 串口适配器。Linux 下通常表现为 `/dev/ttyACM0` 或 `/dev/serial/by-id/...`，Windows 下通常表现为 `COMx`。

常用检查命令：

```bash
lsusb
lsusb -t
ls -l /dev/ttyACM* /dev/serial/by-id/ 2>/dev/null
python3 -m serial.tools.list_ports
```

如果 `lsusb -t` 显示 `Driver=cdc_acm`，说明适配器处于 CDC 串口模式，可被 SDK 的 CAN-FD 模式扫描到。

### RS-485/CAN-FD 从站 ID 与波特率

RS-485 和 CAN-FD 设备使用保持寄存器 `0x0003` 作为从站 ID 寄存器，`0x0000` 为连接控制寄存器。左手默认 ID 为 `0x31`，右手默认 ID 为 `0x32`。

连接时覆盖从站 ID：

```python
hand.open("COM10", slave_id=0x31)
```

修改已连接设备的从站 ID：

```python
ok = hand.set_slave_id(0x32)
hand.close()
```

默认波特率：

- RS-485：1,000,000 bps，`RS485BaudRate.BAUD_1000000`（档位 `0x05`）。
- CAN-FD：仲裁段 1 Mbps、数据段 5 Mbps，两者采样点均为 75%，`CANFDBitTiming.TIMING_1M_5M`（档位 `0x07`）。

`open()` 的 `baudrate` 参数选择本次连接使用的波特率，不修改设备保存的配置；`set_baudrate()` 写入设备配置。**修改配置成功后，必须将灵巧手断电再上电，新波特率才会生效；仅关闭并重新打开 SDK 连接不能使其生效。**

以下示例假定设备当前使用默认波特率，且已创建对应通信类型的 `hand`。如果设备已修改过波特率，首次连接时也应指定其当前配置值。

RS-485：先以当前波特率连接，将设备配置改为 115,200 bps：

```python
from ghand import RS485BaudRate

try:
    if not hand.open("COM10", slave_id=0x31, baudrate=RS485BaudRate.BAUD_1000000):
        raise RuntimeError("Connection failed")
    if not hand.set_baudrate(RS485BaudRate.BAUD_115200):
        raise RuntimeError("Failed to configure baud rate")
finally:
    hand.close()
```

**现在将灵巧手断电再上电**，然后显式指定新波特率连接：

```python
if not hand.open("COM10", slave_id=0x31, baudrate=RS485BaudRate.BAUD_115200):
    raise RuntimeError("Connection failed")
# 在此执行设备操作，结束后调用 hand.close()。
```

CAN-FD：使用 `CANFDBitTiming` 枚举，先以当前配置连接，将设备配置改为仲裁段 1 Mbps、数据段 2 Mbps：

```python
from ghand import CANFDBitTiming

try:
    if not hand.open("COM10", slave_id=0x31, baudrate=CANFDBitTiming.TIMING_1M_5M):
        raise RuntimeError("Connection failed")
    if not hand.set_baudrate(CANFDBitTiming.TIMING_1M_2M):
        raise RuntimeError("Failed to configure bit timing")
finally:
    hand.close()
```

**现在将灵巧手断电再上电**，然后显式指定新 bit timing 连接：

```python
if not hand.open("COM10", slave_id=0x31, baudrate=CANFDBitTiming.TIMING_1M_2M):
    raise RuntimeError("Connection failed")
# 在此执行设备操作，结束后调用 hand.close()。
```

设备保存的新配置在后续上电时仍然有效。后续连接应继续显式传入对应的 `baudrate`，SDK 不会自动探测设备已保存的波特率。

RS-485 波特率档位：

| 档位 | 波特率 |
| --- | --- |
| `0x00` | 57,600 bps |
| `0x01` | 115,200 bps |
| `0x02` | 230,400 bps |
| `0x03` | 460,800 bps |
| `0x04` | 921,600 bps |
| `0x05` | 1,000,000 bps（默认） |

CAN-FD 波特率档位：

| 档位 | 仲裁段 | 数据段 |
| --- | --- | --- |
| `0x00` | 500,000 bps, 80% 采样点 | 1,000,000 bps, 75% 采样点 |
| `0x01` | 500,000 bps, 80% 采样点 | 2,000,000 bps, 80% 采样点 |
| `0x02` | 500,000 bps, 80% 采样点 | 4,000,000 bps, 80% 采样点 |
| `0x03` | 500,000 bps, 80% 采样点 | 5,000,000 bps, 75% 采样点 |
| `0x04` | 1,000,000 bps, 75% 采样点 | 1,000,000 bps, 75% 采样点 |
| `0x05` | 1,000,000 bps, 75% 采样点 | 2,000,000 bps, 80% 采样点 |
| `0x06` | 1,000,000 bps, 75% 采样点 | 4,000,000 bps, 80% 采样点 |
| `0x07` | 1,000,000 bps, 75% 采样点 | 5,000,000 bps, 75% 采样点（默认） |

## 示例

- `examples/tutorial/01.get_basic_info.py`：连接设备并读取基础信息
- `examples/tutorial/02.move_joints.py`：位置控制
- `examples/tutorial/03.current_control.py`：电流控制
- `examples/tutorial/04.velocity_control.py`：速度控制
- `examples/tutorial/05.tactile_callback.py`：触觉数据回调
- `examples/tutorial/06.subscription_demo.py`：数据订阅
- `examples/tutorial/07.multi_hand.py`：多手发现与连接
- `examples/tutorial/12.switch_baud_rate.py`：切换波特率
- `examples/tutorial/13.mit_control.py`：MIT 控制
- `examples/tutorial/14.custom_control.py`：CUSTOM 控制
- `examples/tutorial/15.tactile_display.py`：触觉显示，包含设备连接、订阅和退出清理
- `examples/demo/`：动作和手势演示脚本
- `examples/extension/`：碰撞检测和自适应抓取示例

自适应抓取需要可访问触觉传感器的硬件，配置与运行方法见 [自适应抓取使用说明](src/ghand/adaptive_grasp/README.zh.md)。

触觉显示依赖随 SDK 一起安装，通过示例启动：

```bash
python -m pip install .
python examples/tutorial/15.tactile_display.py
```

示例通过 EtherCAT 连接 GHand5，将已连接的设备传入
`ghand.tactile_display.display.TactileDisplay(hand)`。
显示模块统一管理触觉开关、调零、订阅、工作线程和窗口关闭时的清理。
调用方负责设备连接，在显示结束后断开连接。
自定义数据源仍可使用纯显示组件 `ghand.tactile_display.window.TactileWindow`。

## 项目结构

```text
GHand-Python-SDK/
|-- src/
|   |-- ghand/                  # SDK 包
|   |   |-- ghand.py            # GHand 主类和公开 API
|   |   |-- types/              # 类型枚举与数据对象
|   |   |   |-- __init__.py      # 统一导出公开类型
|   |   |   |-- enums.py         # 产品、协议、关节和传感器枚举
|   |   |   |-- errors.py        # 设备错误与告警位域
|   |   |   `-- data.py          # 命令与设备反馈数据类
|   |   |-- _product_config.py  # 产品配置模型与加载
|   |   |-- gestures.py         # 预定义手势工具
|   |   |-- config/             # 内置产品 JSON 配置
|   |   |   |-- ghand5.json
|   |   |   `-- ghandlite1.json
|   |   |-- comm/               # EtherCAT、CAN-FD、RS-485 驱动
|   |   |-- adaptive_grasp/     # 自适应抓取内部能力
|   |   |-- collision/          # 碰撞检测内部能力
|   |   `-- py.typed            # 类型提示标记
|-- examples/                   # 教程、演示和扩展示例
|-- docs/                       # Sphinx 文档源码
|-- tests/                      # 测试套件
|-- pyproject.toml              # 构建配置
|-- setup.py                    # setuptools 版本加载
|-- LICENSE                     # Apache License 2.0
|-- LICENSES/                   # 第三方许可证文本
|-- THIRD_PARTY_NOTICES.md      # 第三方依赖声明
|-- README.md                   # 英文说明
|-- README.zh.md                # 中文说明
|-- CONTRIBUTING.md             # 贡献指南
`-- CHANGELOG.md                # 更新日志
```

## 开源与生态资源

- **GLI 开源中心**：[GitHub](https://github.com/gli-sdk) / [Gitee](https://gitee.com/glitech)
- **官方文档**：[GHand 灵巧手文档](https://fcnzogxju7xr.feishu.cn/docx/AhZ6ds2iCoguaAxIzBxciYHinNo)
- **C++ SDK**：[GHand SDK C++](https://github.com/gli-sdk/GHand-Cpp-SDK)

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)。

## 贡献指南

欢迎贡献。请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何提交 bug 报告、功能请求和 pull request。

## 支持与反馈

- **技术支持**：项目相关问题请在仓库提交 issue。
- **商务咨询**：[support@glitech.com](mailto:support@glitech.com)

## 许可证

GHand Python SDK 基于 [Apache License 2.0](LICENSE) 开源。

第三方依赖仍遵循各自许可证条款。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 `LICENSES/` 目录。
