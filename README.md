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
    *   固件升级。
*   **关节精细控制**:
    *   设置单个或多个关节的目标角度、速度或力矩。
    *   获取单个或所有关节的当前角度、速度和力矩。
    *   停止所有关节运动。
*   **触觉感知**:
    *   获取单个或所有触觉传感器的8点触觉数据。
    *   复位触觉传感器。

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
sudo venv/bin/python3 examples/1.get_basic_info.py
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

## 贡献

我们欢迎社区的贡献！如果您有任何问题、建议或发现了 Bug，请通过 Issue Tracker 提交。