# GHand Python SDK

[![Version](https://img.shields.io/badge/version-v1.1.2-blue.svg)](src/ghand/version.py)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

[English](README.md)

GHand 灵巧手官方 Python SDK，为机器人操作研究与开发提供精确的关节控制、触觉感知和碰撞检测能力。

## 目录

- [主要功能](#主要功能)
- [文档](#文档)
- [系统要求](#系统要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [开源与生态资源](#开源与生态资源)
- [更新日志](#更新日志)
- [贡献指南](#贡献指南)
- [支持与反馈](#支持与反馈)
- [许可证](#许可证)

## 主要功能

- **手部整体控制**
  - 获取手部整体运行状态及设备信息（ID、版本、手部类型）。
  - 清除故障和保护状态。
  - 配置通信模式（EtherCAT、CAN、RS485）。
  - 重启并初始化手部位姿。
  - 运行传感器和电机的硬件自检。

- **关节精细控制**
  - 设置单个或多个关节的目标角度、速度或力矩。
  - 读取当前角度、速度和力矩反馈。
  - 紧急停止所有关节运动。

- **触觉感知**
  - 读取单个或所有触觉传感器的触觉数据。
  - 复位并校准触觉传感器基准。

- **碰撞检测**
  - 检测手指间以及手指与手掌之间的碰撞。
  - 自动计算并应用安全关节角度。
  - 支持离线姿态验证，无需物理设备。

## 文档

如需查看详细的技术规格和 API 参考，请访问 [Python SDK 开发者文档](https://fcnzogxju7xr.feishu.cn/docx/PlY7dUod5o3tZYxzXiUc0BN1nyd)。

## 系统要求

| 平台   | 要求                                          |
|--------|-----------------------------------------------|
| Python | 3.10 ~ 3.13                                   |
| Linux  | Ubuntu 20.04/22.04 LTS (x86_64 / aarch64), glibc >= 2.31 |
| macOS  | 10.15+                                        |
| Windows| 10 / 11                                       |

## 安装

### 前置条件

- **Python** 3.10 或更高版本
- **Windows**：[Npcap](https://npcap.com/)（使用 EtherCAT 时需要）
- **Linux**：`build-essential` 和 `python3-dev`（用于编译原生扩展）

### 从源码安装（推荐用于开发）

```bash
git clone https://github.com/gli-sdk/GHand-Python-SDK
cd GHand-Python-SDK
pip install -r requirements.txt
pip install -e .
```

> **Linux 说明：** EtherCAT 需要原始套接字权限。如果遇到权限错误，请为 Python 解释器授予该能力：
> ```bash
> sudo setcap cap_net_raw+ep $(which python3)
> ```

## 快速开始

在运行示例前，请确保 GHand 硬件已连接并上电。

```bash
python examples/tutorial/01.get_basic_info.py
```

```python
from ghand import GHand, CommType

hand = GHand()
hand.open(CommType.ETHERCAT, "auto")

info = hand.get_hand_info()
print(f"设备 ID: {info.device_id}, 版本: {info.version}")

hand.close()
```

更多示例请查看 `examples/tutorial/` 和 `examples/demo/` 目录。

## 项目结构

```
GHand-Python-SDK/
├── src/ghand/              # 核心 SDK 源码
│   ├── ghand.py            # GHand 主类与公共 API
│   ├── types.py            # 数据类型、枚举与结构体
│   ├── _config.py          # 产品配置加载器
│   ├── _converter.py       # 关节数据转换器
│   ├── _subscription.py    # 数据订阅管理器
│   ├── gestures.py         # 预定义手势工具
│   ├── logging_config.py   # 日志配置辅助
│   └── comm/               # 通信驱动
│       ├── ethercat_comm.py
│       ├── ethercat_client.py
│       ├── ethercat_protocol.py
│       ├── canfd_comm.py
│       ├── rs485_comm.py
│       └── icomm.py
├── config/                 # 产品 JSON 配置
├── examples/               # 示例程序
│   ├── tutorial/           # 入门教程
│   ├── demo/               # 动作演示脚本
│   └── extension/          # 高级功能示例
├── docs/                   # Sphinx 文档源码
├── tests/                  # 单元测试（待补充）
├── requirements.txt        # 运行时依赖
├── pyproject.toml          # 构建配置
├── setup.py                # 包安装配置
├── LICENSE                 # MIT 许可证
├── README.md               # 英文说明
├── CONTRIBUTING.md         # 贡献指南
└── CHANGELOG.md            # 版本历史
```

## 开源与生态资源

- **GLI 开源中心**：[GLI GitHub 组织](https://github.com/gli-sdk)
- **官方文档**：[GHand 灵巧手文档](https://fcnzogxju7xr.feishu.cn/docx/AhZ6ds2iCoguaAxIzBxciYHinNo)
- **C++ SDK**：[GHand SDK C++](https://github.com/gli-sdk/GHand-Cpp-SDK)

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)。

## 贡献指南

欢迎社区贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解缺陷报告、功能请求和提交 PR 的规范。

## 支持与反馈

- **技术支持**：如有项目相关问题，请在本仓库提交 Issue。
- **商务咨询**：[support@glitech.com](mailto:support@glitech.com)

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
