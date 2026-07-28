# GHand Python SDK

[![Version](https://img.shields.io/badge/version-v2.0.2-blue.svg)](src/ghand/version.py)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

[中文](README.zh.md)

The official Python SDK for the GHand Dexterous Hand — providing precise joint control, tactile sensing, and collision detection for robotic manipulation research and development.

## Table of Contents

- [Key Features](#key-features)
- [Documentation](#documentation)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Open Source & Ecosystem Resources](#open-source--ecosystem-resources)
- [Changelog](#changelog)
- [Support & Feedback](#support--feedback)
- [Contributing](#contributing)
- [License](#license)

## Key Features

- **Hand-level Control**
  - Get overall hand status and device information (ID, version, hand type).
  - Clear fault and protection states.
  - Configure communication mode (EtherCAT, CAN, RS485).
  - Reboot and initialize hand position.
  - Run hardware self-tests for sensors and motors.

- **Fine Joint Control**
  - Set target angle, speed, or torque for single or multiple joints.
  - Read current angle, speed, and torque feedback.
  - Emergency stop for all joint motion.

- **Tactile Sensing**
  - Read tactile data from individual or all tactile sensors.
  - Reset and calibrate tactile sensor baselines.

- **Collision Detection**
  - Detect collisions between fingers and between fingers and the palm.
  - Automatically compute and apply safe joint angles.
  - Support offline pose validation without a physical device.

## Documentation

For detailed technical specifications and API references, visit the [Python SDK Developer Documentation](https://fcnzogxju7xr.feishu.cn/docx/PlY7dUod5o3tZYxzXiUc0BN1nyd).

## System Requirements

| Platform | Requirement |
|----------|-------------|
| Python   | 3.10 ~ 3.13 |
| Linux    | Ubuntu 22.04/24.04 LTS (x86_64), glibc >= 2.35 |
| Windows  | 10 / 11 |

## Installation

### Prerequisites

- **Python** 3.10 or higher
- **Windows**: [Npcap](https://npcap.com/) (required for EtherCAT)
- **Linux**: `build-essential` and `python3-dev` (for compiling native extensions)

### Install a Specific Version

Install version `v2.0.2` directly from either repository:

```bash
pip install "ghand_python_sdk @ git+https://github.com/gli-sdk/GHand-Python-SDK.git@v2.0.2"
```

```bash
pip install "ghand_python_sdk @ git+https://gitee.com/glitech/GHand-Python-SDK.git@v2.0.2"
```

### Install from Source

```bash
git clone -b v2.0.2 https://github.com/gli-sdk/GHand-Python-SDK.git
cd GHand-Python-SDK
pip install -r requirements.txt
pip install -e .
```

Gitee mirror:

```bash
git clone -b v2.0.2 https://gitee.com/glitech/GHand-Python-SDK.git
cd GHand-Python-SDK
pip install -r requirements.txt
pip install -e .
```

### Linux EtherCAT Notes

EtherCAT needs raw socket access. If you see permission errors, grant the capability to your Python interpreter:

```bash
sudo setcap 'cap_net_raw,cap_net_admin=eip' $(which python3)
```

### Linux RS485 Serial Ports

When using a USB-RS485 adapter on Linux, the SDK auto-discovery prefers `/dev/serial/by-id/*`, `/dev/ttyUSB*`, `/dev/ttyACM*`, and `/dev/ttyAMA*`. It does not auto-scan `/dev/ttyS*` because those are usually built-in motherboard serial ports. If you really use a built-in serial port, pass the device path explicitly to `open()`.

Useful checks:

```bash
lsusb
ls -l /dev/ttyUSB* /dev/ttyACM* /dev/serial/by-id/ 2>/dev/null
python3 -m serial.tools.list_ports
```

CH340/CH341 USB-RS485 adapters usually appear as `1a86:7523 QinHeng Electronics CH340 serial converter`, and should create `/dev/ttyUSB0` or a `/dev/serial/by-id/...` alias. If `dmesg` shows `brltty` claiming the interface and disconnecting `ttyUSB0`, stop or remove `brltty`:

```bash
sudo systemctl stop brltty
sudo systemctl disable brltty
# If you do not use braille terminal devices:
sudo apt remove brltty
```

If the serial device exists but cannot be opened, make sure your user belongs to the `dialout` group:

```bash
groups
sudo usermod -aG dialout $USER
```

Log out and back in after changing groups. The default RS485 baud rate is `1000000`; override it with:

```bash
export GHAND_RS485_BAUDRATE=1000000
```

### CANFD Adapter Notes

CANFD mode supports ZQWL-CANFD CDC serial adapters.

ZQWL-CANFD CDC serial adapters appear as `3562:0101 ZQWL-CANFD` on USB. On Linux they usually create `/dev/ttyACM0` or a `/dev/serial/by-id/...` alias; on Windows they usually appear as `COMx`. These adapters use the ZQWL serial protocol.

Useful checks:

```bash
lsusb
lsusb -t
ls -l /dev/ttyACM* /dev/serial/by-id/ 2>/dev/null
python3 -m serial.tools.list_ports
```

If `lsusb -t` shows `Driver=cdc_acm`, the adapter is in CDC serial mode. In CANFD mode, the SDK scans ZQWL CDC serial adapters.

### RS485/CANFD Slave IDs

RS485 and CANFD devices use holding register `0x0000` as the slave ID register. The product JSON config provides the default `slave_id`, and `open()` can override it when a device was previously assigned a different ID:

```python
hand = GHand(product_type=ProductType.G5, comm_type=CommType.CANFD)
hand.open("COM10", slave_id=0x31)
```

To change the connected device ID, use `set_slave_id()`. Connect only one target hand on the bus while changing IDs:

```python
ok = hand.set_slave_id(0x32)
hand.close()
```

After changing the ID, reconnect with the new value:

```python
hand = GHand(product_type=ProductType.G5, comm_type=CommType.CANFD)
hand.open("COM10", slave_id=0x32)
```

The helper script `examples/tutorial/11.set_slave_id.py` provides a guarded workflow for testing ID changes.

## Quick Start

Make sure your GHand hardware is connected and powered on before running examples.

```bash
python examples/tutorial/01.get_basic_info.py
```

```python
from ghand import GHand, CommType

hand = GHand()
hand.open(CommType.ETHERCAT, "auto")

info = hand.get_hand_info()
print(f"Device ID: {info.device_id}, Version: {info.version}")

hand.close()
```

## Project Structure

```
GHand-Python-SDK/
├── src/ghand/              # Core SDK source code
│   ├── ghand.py            # Main GHand class and public API
│   ├── types.py            # Data types, enums, and structures
│   ├── _config.py          # Product configuration loader
│   ├── _converter.py       # Joint data converters
│   ├── _subscription.py    # Data subscription manager
│   ├── gestures.py         # Predefined gesture utilities
│   ├── logging_config.py   # Logging setup helpers
│   └── comm/               # Communication drivers
│       ├── ethercat_comm.py
│       ├── ethercat_client.py
│       ├── ethercat_protocol.py
│       ├── canfd_comm.py
│       ├── rs485_comm.py
│       └── icomm.py
├── config/                 # Product JSON configurations
├── examples/               # Example programs
│   ├── tutorial/           # Getting-started tutorials
│   ├── demo/               # Action demonstration scripts
│   └── extension/          # Advanced feature examples
├── docs/                   # Sphinx documentation source
├── tests/                  # Unit tests (to be added)
├── requirements.txt        # Runtime dependencies
├── pyproject.toml          # Build configuration
├── setup.py                # Package setup
├── LICENSE                 # MIT License
├── README.md               # This file
├── CONTRIBUTING.md         # Contribution guidelines
└── CHANGELOG.md            # Version history
```

## Open Source & Ecosystem Resources

- **GLI Open Source Hub**: [GitHub](https://github.com/gli-sdk) / [Gitee](https://gitee.com/glitech)
- **Official Documentation**: [GHand Dexterous Hand Docs](https://fcnzogxju7xr.feishu.cn/docx/AhZ6ds2iCoguaAxIzBxciYHinNo)
- **C++ SDK**: [GHand SDK C++](https://github.com/gli-sdk/GHand-Cpp-SDK)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on bug reports, feature requests, and pull requests.

## Support & Feedback

- 📋 **Technical Support:** For project-specific issues, open an Issue in this repository.
- 📧 **General Inquiries:** [support@glitech.com](mailto:support@glitech.com)

## License

This project is licensed under the [Apache License 2.0](LICENSE).
