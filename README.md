# GHand Python SDK

[![Version](https://img.shields.io/badge/version-v1.1.2-blue.svg)](src/ghand/version.py)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
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
| Linux    | Ubuntu 20.04/22.04 LTS (x86_64 / aarch64), glibc >= 2.31 |
| macOS    | 10.15+ |
| Windows  | 10 / 11 |

## Installation

### Prerequisites

- **Python** 3.10 or higher
- **Windows**: [Npcap](https://npcap.com/) (required for EtherCAT)
- **Linux**: `build-essential` and `python3-dev` (for compiling native extensions)

### Install from Source

```bash
git clone https://github.com/gli-sdk/GHand-Python-SDK
cd GHand-SDK
pip install -r requirements.txt
pip install -e .
```

> **Linux Note:** EtherCAT needs raw socket access. If you see permission errors, grant the capability to your Python interpreter:
> ```bash
> sudo setcap cap_net_raw+ep $(which python3)
> ```

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
ghand-sdk/
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

- **GLI Open Source Hub**: [GLI GitHub Organization](https://github.com/gli-sdk)
- **Official Documentation**: [GHand Dexterous Hand Docs](https://fcnzogxju7xr.feishu.cn/docx/AhZ6ds2iCoguaAxIzBxciYHinNo)
- **C++ SDK**: [GHand SDK C++](https://github.com/gli-sdk/ghand_sdk_cpp)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on bug reports, feature requests, and pull requests.

## Support & Feedback

- 📋 **Technical Support:** For project-specific issues, open an Issue in this repository.
- 📧 **General Inquiries:** [support@glitech.com](mailto:support@glitech.com)

## License

This project is licensed under the [MIT License](LICENSE).