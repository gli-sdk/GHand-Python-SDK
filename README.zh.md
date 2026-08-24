# GHand Python SDK

[![Version](https://img.shields.io/badge/version-v2.2.1-blue.svg)](src/ghand/version.py)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

[English](README.md)

GHand 灵巧手官方 Python SDK，提供 EtherCAT、CAN-FD、RS-485 通信接入，以及关节控制、触觉感知、碰撞检测和自适应抓取能力。

## 目录

- [主要功能](#主要功能)
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

- **设备控制**
  - 通过 EtherCAT、CAN-FD 或 RS-485 打开和关闭 GHand 设备。
  - 读取固件、硬件、序列号、产品名称、左右手类型和电机驱动版本。
  - 清除故障、初始化关节、停止运动，并执行常用设备操作。

- **关节控制**
  - 按位置、速度或力矩模式控制单个或多个关节。
  - 读取当前关节角度、速度、力矩、状态和错误反馈。
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
- [诊断信息](docs/diagnostics.md)

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
pip install -r requirements.txt
pip install -e .
```

Gitee 镜像：

```bash
git clone https://gitee.com/glitech/GHand-Python-SDK.git
cd GHand-Python-SDK
pip install -r requirements.txt
pip install -e .
```

## 快速开始

运行示例前，请确认 GHand 硬件已连接并上电。

```bash
python examples/tutorial/01.get_basic_info.py
```

最小 EtherCAT 示例：

```python
from ghand import CommType, GHand, ProductType

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)

if hand.open("auto"):
    print("Firmware:", hand.get_firmware_version())
    print("Hardware:", hand.get_hardware_version())
    print("Device:", hand.get_device_name())
    hand.close()
else:
    print("Connection failed")
```

更多设备版本 API 示例：

```python
def format_version(version):
    return "not available" if version == (0, 0, 0) else ".".join(map(str, version))

print("Firmware package:", format_version(hand.get_firmware_package_version()))
print("Position sensor:", format_version(hand.get_position_sensor_version()))
print("Tactile MCU:", format_version(hand.get_tactile_sensor_version()))
print("Motor driver:", format_version(hand.get_motor_driver_version()))
print("Thumb tactile sensor:", format_version(hand.get_thumb_tactile_sensor_version()))
print("Finger tactile sensor:", format_version(hand.get_finger_tactile_sensor_version()))
```

最小 CAN-FD 示例：

```python
from ghand import CommType, GHand, ProductType

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.CANFD)
hand.open("auto", slave_id=0x31)
```

最小 RS-485 示例：

```python
from ghand import CommType, GHand, ProductType

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.RS485)
hand.open("auto", slave_id=0x31)
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

RS-485 和 CAN-FD 设备使用保持寄存器 `0x0000` 作为从站 ID 寄存器。左手默认 ID 为 `0x31`，右手默认 ID 为 `0x32`。

连接时覆盖从站 ID：

```python
hand.open("COM10", slave_id=0x31)
```

修改已连接设备的从站 ID：

```python
ok = hand.set_slave_id(0x32)
hand.close()
```

使用非默认 RS-485 波特率连接：

```python
from ghand import RS485BaudRate

hand.open("COM10", slave_id=0x31, baud_rate=RS485BaudRate.BAUD_1000000)
```

写入 RS-485 波特率配置：

```python
ok = hand.set_baudrate_config(RS485BaudRate.BAUD_1000000)
```

CAN-FD 使用 bit timing 配置枚举，不使用 RS-485 波特率枚举：

```python
from ghand import CANFDBitTiming

hand.open("COM10", slave_id=0x31, baud_rate=CANFDBitTiming.TIMING_1M_5M)
ok = hand.set_baudrate_config(CANFDBitTiming.TIMING_1M_5M)
```

波特率/bit timing 配置由设备保存，并在下一次上电后生效。设备断电重启后，需要在 `open()` 中显式传入已配置的枚举值。

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
| `0x04` | 1,000,000 bps, 75% 采样点 | 4,000,000 bps, 80% 采样点 |
| `0x05` | 1,000,000 bps, 75% 采样点 | 5,000,000 bps, 75% 采样点（默认） |

## 示例

- `examples/tutorial/01.get_basic_info.py`：连接设备并读取基础信息
- `examples/tutorial/02.move_joints.py`：位置控制
- `examples/tutorial/03.torque_control.py`：力矩控制
- `examples/tutorial/04.speed_control.py`：速度控制
- `examples/tutorial/05.tactile_callback.py`：触觉数据回调
- `examples/tutorial/06.subscription_demo.py`：数据订阅
- `examples/tutorial/07.multi_hand.py`：多手发现与连接
- `examples/demo/`：动作和手势演示脚本
- `examples/extension/`：碰撞检测和自适应抓取示例

## 项目结构

```text
GHand-Python-SDK/
|-- src/
|   |-- ghand/                  # SDK 包
|   |   |-- ghand.py            # GHand 主类和公开 API
|   |   |-- types.py            # 数据类型、枚举和结构体
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
|-- requirements.txt            # 核心运行时依赖
|-- pyproject.toml              # 构建配置
|-- setup.cfg                   # 打包元数据
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
