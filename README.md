# Xiaoyao Python SDK

## 简介

Xiaoyao Python SDK 是为枭尧灵巧手设计的官方开发工具包。它提供了一套完整的 Python API，允许开发者轻松地与灵巧手进行交互，实现对关节、传感器以及其他核心功能的精确控制和数据获取。

## 主要功能

*   **手部整体控制**:
    *   获取手部整体运行状态及基本信息（设备ID、版本、手部类型等）。
    *   解除手部保护状态。
    *   配置及获取通讯方式（EtherCAT, CAN, RS485）。
    *   手部重启及位置初始化。
    *   硬件自检（传感器、电机）。
    *   固件升级。
*   **关节精细控制**:
    *   设置单个或多个关节的目标角度、速度或力矩。
    *   获取单个或所有关节的当前角度、速度和力矩。
    *   停止所有关节运动。
*   **触觉感知**:
    *   获取单个或所有触觉传感器的8点触觉数据。
    *   复位触觉传感器。
*   **LED 指示**:
    *   设置LED灯颜色、显示模式及闪烁频率。

## 安装

### 1. Python 版本要求

本 SDK 需要 **Python 3.9.0 或更高版本**。您可以通过以下命令检查您的 Python 版本：
```bash
python --version
# 或
python3 --version
```
如果版本不符，请务必升级您的 Python 环境。

### 2. 安装依赖
激活虚拟环境后，使用 pip 安装 requirements.txt 中列出的所有依赖：
```bash
pip install -r requirements.txt
```
### 3. 安装 SDK
```bash
python setup.py install
```
### 4. 运行示例程序
在运行 SDK 前，请确保您的枭尧灵巧手硬件已正确连接到您的计算机，并且已安装相应驱动。

使用示例
在 examples/ 目录下，提供了多个 Python 脚本，演示了如何使用 SDK 的各项功能。您可以通过运行这些脚本来快速了解 SDK 的用法。

```bash
# 运行一个示例
python examples/1.get_basic_info.py
# 更多示例请查看 examples/ 目录
```

## 贡献
我们欢迎社区的贡献！如果您有任何问题、建议或发现了 Bug，请通过 Issue Tracker 提交。