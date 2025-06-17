# 枭尧灵巧手 SDK

## 简介

枭尧灵巧手 SDK (Software Development Kit) 是为枭尧灵巧手机器人设计的官方开发工具包。它提供了一套完整的 Python API，允许开发者轻松地与灵巧手进行交互，实现对关节、指尖、传感器以及其他核心功能的精确控制和数据获取。

本 SDK 旨在简化机器人应用开发流程，为研究、教育和工业应用提供可靠的软件接口。

## 主要功能

*   **手部整体控制**:
    *   执行预设手势（如张开、握拳、对指等）。
    *   获取手部整体运行状态及基本信息（设备ID、版本、温度等）。
    *   解除手部保护状态。
    *   设置手部温度保护阈值。
    *   配置及获取通讯方式（EtherCAT, CAN, RS485）。
    *   手部重启及位置初始化。
    *   硬件自检（传感器、电机）。
    *   固件升级。
    *   获取手部类型（左右手）。
*   **关节精细控制**:
    *   设置单个或多个关节的目标角度、速度或力矩（支持弧度单位）。
    *   获取单个或所有关节的当前角度、速度和力矩。
    *   设置单个或所有关节的最大输出力矩。
    *   查询被动关节列表及联动关节信息。
    *   停止所有关节运动。
    *   订阅关节实时数据流。
*   **指尖姿态控制**:
    *   设置单个或多个指尖在三维空间中的精确姿态（位置+方向）。
    *   订阅指尖位置实时数据。
*   **触觉感知**:
    *   获取单个或所有触觉传感器的 3x3 二维数据矩阵。
    *   订阅触觉传感器实时数据流。
    *   复位触觉传感器。
*   **电机管理**:
    *   获取和设置指定电机的运行状态（启用、禁用、停止、错误重置）。
*   **LED 指示**:
    *   设置LED灯颜色、显示模式及闪烁频率。

## 安装

### 1. Python 版本要求

本 SDK 需要 **Python 3.8.0 或更高版本**。您可以通过以下命令检查您的 Python 版本：
```bash
python --version
# 或
python3 --version

如果版本不符，请务必升级您的 Python 环境。

### 2. 创建并激活虚拟环境 (推荐)
为了避免依赖冲突，强烈建议在独立的虚拟环境中安装 SDK：

Generated bash
python -m venv venv_xiaoyao_sdk
# Windows:
.\venv_xiaoyao_sdk\Scripts\activate
# macOS/Linux:
source venv_xiaoyao_sdk/bin/activate

### 3. 安装依赖
激活虚拟环境后，使用 pip 安装 requirements.txt 中列出的所有依赖：

Generated bash
pip install -r requirements.txt

### 4. 硬件驱动和连接
在运行 SDK 前，请确保您的枭尧灵巧手硬件已正确连接到您的计算机，并且所有必要的硬件驱动（如 EtherCAT 主站驱动、CAN 适配器驱动等）已安装并配置完毕。具体连接和驱动安装请参考硬件配套手册。

使用示例
在 examples/ 目录下，提供了多个 Python 脚本，演示了如何使用 SDK 的各项功能。您可以通过运行这些脚本来快速了解 SDK 的用法。

Generated bash
# 激活虚拟环境 (如果尚未激活)
# source venv_xiaoyao_sdk/bin/activate

# 运行一个示例
python examples/example_get_basic_info.py
# 更多示例请查看 examples/ 目录

许可证
本 SDK 使用 MIT 许可证 发布。

贡献
我们欢迎社区的贡献！如果您有任何问题、建议或发现了 Bug，请通过 Issue Tracker 提交。