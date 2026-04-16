# Xiaoyao Python SDK

## 目录

- [简介](#简介)
- [主要功能](#主要功能)
- [Windows 系统安装](#windows-系统安装)
  - [Python 版本要求](#1-python-版本要求)
  - [安装依赖](#2-安装依赖)
  - [安装 SDK](#3-安装-sdk)
  - [运行示例程序](#4-运行示例程序)
- [Linux 系统安装](#linux-系统安装)
  - [系统要求](#1-系统要求)
  - [基础环境准备](#2-基础环境准备)
  - [SDK 安装步骤](#3-sdk-安装步骤)
  - [权限配置（可选）](#4-权限配置可选)
  - [运行示例程序](#5-运行示例程序)
- [日志配置](#日志配置)
- [异常处理](#异常处理)
  - [异常类型](#异常类型)
  - [基本用法](#基本用法)
  - [迁移指南](#迁移指南)
- [生成说明文档](#生成说明文档)
- [贡献](#贡献)


## 简介

Xiaoyao Python SDK 是为枭尧灵巧手设计的官方开发工具包。它提供了一套完整的 Python API，允许开发者轻松地与灵巧手进行交互，实现对关节、传感器以及其他核心功能的精确控制和数据获取。

## 主要功能

*   **手部整体控制**:
    *   获取手部整体运行状态及基本信息（设备ID、版本、手部类型等）。
    *   解除手部保护状态。
    *   配置及获取通讯方式（EtherCAT, CAN, RS485）。
    *   手部重启及位置初始化。
    *   硬件自检（传感器、电机）。
*   **关节精细控制**:
    *   设置单个或多个关节的目标角度、速度或力矩。
    *   获取单个或所有关节的当前角度、速度和力矩。
    *   停止所有关节运动。
*   **触觉感知**:
    *   获取单个或所有触觉传感器的触觉数据。
    *   复位触觉传感器。
*   **碰撞检测**:
    *   自动检测手指间和手指与手掌之间的碰撞。
    *   在检测到碰撞时自动使用安全角度。
    *   支持离线模式（无需连接设备即可进行姿态验证）。

## Windows 系统安装

### 1. Python 版本要求

本 SDK 需要 **Python 3.10.0 或更高版本**。您可以通过以下命令检查您的 Python 版本：
```bash
python --version
# 或
python3 --version
```
如果版本不符，请务必升级您的 Python 环境。

### 2. 安装依赖
正确配置 Python 的环境后，请确保您的系统已安装C/C++编译工具和Npcap库。

使用 pip 安装 requirements.txt 中列出的所有依赖：
```bash
pip install -r requirements.txt --find-links ./wheels
```
### 3. 安装 SDK
```bash
pip install -e .
```

### 4. 运行示例程序
在运行 SDK 前，请确保您的枭尧灵巧手硬件已正确连接到您的计算机，并且已安装相应驱动。

使用示例
在 examples/ 目录下，提供了多个 Python 脚本，演示了如何使用 SDK 的各项功能。您可以通过运行这些脚本来快速了解 SDK 的用法。

```bash
# 运行一个示例
python examples/01.get_basic_info.py
# 更多示例请查看 examples/ 目录
```

---

## Linux 系统安装

本节提供在 Linux 系统上安装和配置 SDK 的详细步骤。

### 1. 系统要求

- **操作系统**: Ubuntu 20.04 或更高版本（或其他 Linux 发行版）
- **Python**: 3.10 或更高版本
- **权限**: 需要 sudo 权限进行系统配置
- **网络**: 需要以太网接口用于 EtherCAT 通信

### 2. 基础环境准备

#### 1. 检查 Python 版本

```bash
python3 --version
```

确保版本为 3.10 或更高。如果未安装 Python 3，请先安装：

```bash
sudo apt install python3.12
```

#### 2. 安装虚拟环境工具

```bash
sudo apt install python3.12-venv
```

#### 3. 安装编译工具和依赖

这些工具是编译某些 Python 包所必需的：

```bash
sudo apt install build-essential python3-dev
```

### 3. SDK 安装步骤

#### 1. 创建并激活虚拟环境
```bash
#进入 SDK 目录，如果 SDK 不在 `~/xiaoyao-sdk`，请使用实际路径。
cd ~/xiaoyao-sdk
```

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate
```

激活成功后，命令提示符前会显示 `(venv)`。

#### 2. 安装依赖

```bash
pip3 install -r requirements.txt

#安装collision_sdk wheel
pip3 install ./wheels/collision_sdk-0.1.0-cp312-cp312-linux_x86_64.whl
```

#### 3. 安装 SDK

使用可编辑模式安装 SDK：

```bash
pip3 install -e .
```

#### 4. 验证 pysoem 安装

pysoem 是 EtherCAT 通信的核心依赖。检查是否已安装：

```bash
pip show pysoem
```

如果未安装，请手动安装：

```bash
pip install pysoem
```

### 4. 权限配置（可选）

为 Python 添加网络原始套接字权限，配置后无需使用 sudo 运行程序。

```bash
# 为 Python3 添加网络原始套接字权限
sudo setcap cap_net_raw+ep /usr/bin/python3.12

# 验证权限
getcap /usr/bin/python3.12
```

如果输出包含 `cap_net_raw+ep`，则表示配置成功。

### 5. 运行示例程序

**重要提示**: 由于 EtherCAT 需要原始套接字权限，在大多数 Linux 系统上需要使用 sudo 运行。

**进入 SDK 目录**：如果 SDK 不在 `~/xiaoyao-sdk`，请使用实际路径。

```bash
cd ~/xiaoyao-sdk
```

**方法 A: 使用 sudo 运行（推荐，最稳定）**

```bash
# 在虚拟环境中使用 sudo 运行
sudo venv/bin/python3 examples/01.get_basic_info.py
```

**方法 B: 不使用 sudo（需要配置 CAP_NET_RAW）**

如果你已经正确配置了 CAP_NET_RAW 权限，可以直接运行：

```bash
source venv/bin/activate
python3 examples/1.get_basic_info.py
```

如果提示权限不足，请使用方法 A。

---

## 生成说明文档

确保已安装 Sphinx 和相关依赖：

```bash
pip install sphinx sphinx-rtd-theme
```

进入 docs 目录：

```bash
cd docs
```

使用 Sphinx 生成 HTML 文档：

```bash
sphinx-build -b html source build/html
```

生成完成后，打开 `docs/build/html/index.html` 文件即可查看完整的 API 文档和使用说明。

---

## 日志配置

### 默认行为

SDK 默认会自动输出 **WARNING** 和 **ERROR** 级别的日志到 stderr，无需任何配置：

```python
from xiaoyao import DexHand

# SDK 自动输出 WARNING 和 ERROR 日志
hand = DexHand()
```

### 升级日志级别

如需查看更多日志信息（INFO 或 DEBUG），可以通过 `configure_logging()` 降低日志级别：

```python
from xiaoyao import configure_logging, DexHand
import logging

# 升级到 INFO 级别（显示 INFO、WARNING、ERROR）
configure_logging(level=logging.INFO)

# 升级到 DEBUG 级别（显示所有日志）
configure_logging(level=logging.DEBUG)
```

**注意：** 只支持三个级别：
- **WARNING**（默认）：仅显示警告和错误
- **INFO**：显示信息、警告和错误
- **DEBUG**：显示所有日志（包括调试信息）

### 文件日志

如需将日志记录到文件，可以使用 `configure_logging_file()`：

```python
from xiaoyao import configure_logging_file

# 将日志写入文件（DEBUG 级别）
configure_logging_file("xiaoyao.log", level=logging.DEBUG)
```

文件日志与控制台日志独立，可以设置不同的级别。例如：
- 控制台：WARNING（默认）
- 文件：DEBUG（记录所有详细信息）

### 同时使用控制台和文件日志

```python
from xiaoyao import configure_logging, configure_logging_file
import logging

# 控制台显示 INFO+，文件记录 DEBUG+
configure_logging(level=logging.INFO)
configure_logging_file("xiaoyao.log", level=logging.DEBUG)
```

#### 模块级别控制

```python
import logging
from xiaoyao import get_logger

# 只显示特定模块的日志
dexhand_logger = get_logger("dexhand")
dexhand_logger.setLevel(logging.DEBUG)
```

## 异常处理

从 v1.1.1 开始，SDK 引入了自定义异常系统，提供结构化的错误信息和强制错误处理，增强硬件安全性。

### 异常类型

SDK 提供以下异常类（继承自基类 `XiaoyaoError`）：

| 异常类 | 使用场景 | 包含信息 |
|--------|----------|----------|
| `DeviceDisconnectedError` | 设备断连或通信失败 | -|
| `DeviceFaultError` | 设备故障 (state=2/3 或 error≠0) | FaultInfo (错误码、状态、描述) |
| `JointFaultError` | 关节故障 | List[JointFaultInfo] (所有故障关节) |
| `DataReceiveError` | 数据接收错误 (长度不符) | 期望长度、实际长度 |

### 基本用法

```python
from xiaoyao import DexHand, DeviceFaultError, JointFaultError, DeviceDisconnectedError

hand = DexHand()

try:
    hand.open()
    info = hand.get_hand_info()  # 可能抛出 DeviceFaultError
    joints = hand.get_joints()   # 可能抛出 JointFaultError

except DeviceFaultError as e:
    print(f"设备故障: {e.fault_info.error_code.name}")
    print(f"状态: {e.fault_info.state.name}")

except JointFaultError as e:
    print(f"检测到 {len(e.faulty_joints)} 个故障关节:")
    for joint in e.faulty_joints:
        print(f"  {joint.joint_id}: {joint.error_code.name}")

except DeviceDisconnectedError as e:
    print(f"设备断连: {e.reason}")

finally:
    hand.close()
```

**访问结构化错误信息：**

```python
except DeviceFaultError as e:
    if e.fault_info:
        # FaultInfo 是一个 dataclass，提供类型安全访问
        error_code = e.fault_info.error_code  # ErrorCode 枚举
        state = e.fault_info.state             # State 枚举
        message = e.fault_info.message         # str

        # 根据具体错误码处理
        if error_code == ErrorCode.MOTOR_STALLED:
            print("电机堵转！")
        elif state == State.PROTECTIVE_STOPED:
            print("保护性停止！")
```

## 碰撞检测

SDK 内置碰撞检测功能，可以自动检测手指间和手指与手掌之间的碰撞，避免硬件损坏。

### 基本使用

```python
from xiaoyao import DexHand, CommType, Joint, JointId
import math

hand = DexHand()
hand.open(CommType.ETHERCAT, "auto")

# 设置安全边距（0.0-1.0，其中1.0=2mm）
hand.set_safety_margin(0.5)

# 准备目标关节
joints = [
    Joint(id=JointId.THUMB_PIP, angle=math.radians(30), speed=100, torque=100),
    Joint(id=JointId.FF_PIP, angle=math.radians(30), speed=100, torque=100),
    # ...
]

# 安全移动（自动检测碰撞并使用安全角度）
success = hand.move_safe_joints(joints)
```

### 离线模式（无需硬件）

碰撞检测支持离线模式，用于路径规划和姿态验证：

```python
hand = DexHand()  # 无需调用 open()
hand.set_safety_margin(0.5)

# 可以直接调用碰撞检测
# （未指定的关节默认为0度）
```

### API 说明

- **`set_safety_margin(margin: float)`** - 设置安全边距
  - `margin`: 范围 [0.0, 1.0]，实际安全距离 = margin × 2mm
  - 例如：0.5 = 1mm 安全边距

- **`move_safe_joints(joints, mode)`** - 安全移动关节
  - 自动进行碰撞检测
  - 检测到碰撞时自动使用安全角度
  - 记录碰撞日志（INFO 级别）

### 示例程序

查看 `examples/` 目录中的示例：
- `22.collision_detection_online.py` - 碰撞检测演示

### 注意事项

- **DIP 关节自动计算**：远端指间关节（DIP）会根据近端指间关节（PIP）自动计算，符合灵巧手的机械约束
- **性能影响**：首次启用时需要 1-2 秒加载数据，单次检测约 10-50ms
- **依赖要求**：碰撞检测依赖（`collision_sdk` 及其传递依赖如 numpy、pandas、trimesh 等，约 200MB）随 SDK 一起自动安装。离线环境可从 `wheels/` 目录安装对应平台的预编译包。

我们欢迎社区的贡献！如果您有任何问题、建议或发现了 Bug，请通过 Issue Tracker 提交。