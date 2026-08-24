# GHand Python SDK

[![Version](https://img.shields.io/badge/version-v2.2.1-blue.svg)](src/ghand/version.py)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

[中文](README.zh.md)

The official Python SDK for the GHand dexterous hand. It provides high-level APIs for EtherCAT, CAN-FD, and RS-485 communication, joint control, tactile sensing, collision detection, and adaptive grasp examples.

## Table of Contents

- [Key Features](#key-features)
- [Documentation](#documentation)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Communication Notes](#communication-notes)
- [Examples](#examples)
- [Project Structure](#project-structure)
- [Open Source & Ecosystem Resources](#open-source--ecosystem-resources)
- [Changelog](#changelog)
- [Contributing](#contributing)
- [Support & Feedback](#support--feedback)
- [License](#license)

## Key Features

- **Device control**
  - Open and close GHand devices over EtherCAT, CAN-FD, or RS-485.
  - Read firmware, hardware, serial number, product name, hand type, and motor driver version.
  - Clear faults, initialize joints, stop motion, and run common device operations.

- **Joint control**
  - Command one or more joints by position, speed, or torque.
  - Read current joint angle, speed, torque, state, and error feedback.
  - Clamp active joint commands to product-specific limits.

- **Tactile sensing**
  - Enable or disable tactile sensors on supported products.
  - Read tactile sensor data and zero-calibrate tactile baselines.

- **Collision detection**
  - Check target poses before motion.
  - Configure a safety margin and get safe angles when a collision is detected.

- **Adaptive grasp extension**
  - Includes the `adaptive_grasp` package and examples for force-aware hold and grasp workflows.

## Documentation

For detailed technical specifications and API references, visit the [Python SDK Developer Documentation](https://fcnzogxju7xr.feishu.cn/docx/PlY7dUod5o3tZYxzXiUc0BN1nyd).

Local Sphinx sources are also available under `docs/`.

Additional local notes:

- [Logging](docs/logging.md)
- [Error handling](docs/error_handling.md)
- [Subscription and threading](docs/subscription_threading.md)
- [Diagnostics](docs/diagnostics.md)

## System Requirements

| Platform | Requirement |
|----------|-------------|
| Python | 3.10 or higher |
| Linux | Ubuntu 22.04/24.04 LTS (x86_64 / aarch64), glibc >= 2.35 |
| Windows | 10 / 11 |
| macOS | 12+ (Intel x86_64 / Apple Silicon arm64) |

## Installation

### Prerequisites

- **Python** 3.10 or higher
- **Windows**: [Npcap](https://npcap.com/) when using EtherCAT
- **Linux**: `build-essential` and `python3-dev` for building native dependencies
- **macOS**: No additional prerequisites for CAN-FD or RS-485. For EtherCAT, raw socket access via pcap requires `sudo` (no persistent capability equivalent to Linux `setcap` on macOS).

### Install from Source

```bash
git clone https://github.com/gli-sdk/GHand-Python-SDK.git
cd GHand-Python-SDK
pip install -r requirements.txt
pip install -e .
```

Gitee mirror:

```bash
git clone https://gitee.com/glitech/GHand-Python-SDK.git
cd GHand-Python-SDK
pip install -r requirements.txt
pip install -e .
```

## Quick Start

Make sure your GHand hardware is connected and powered on before running examples.

```bash
python examples/tutorial/01.get_basic_info.py
```

Minimal EtherCAT example:

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

Additional device version APIs:

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

Minimal CAN-FD example:

```python
from ghand import CommType, GHand, ProductType

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.CANFD)
hand.open("auto", slave_id=0x31)
```

Minimal RS-485 example:

```python
from ghand import CommType, GHand, ProductType

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.RS485)
hand.open("auto", slave_id=0x31)
```

## Communication Notes

### EtherCAT on Linux

EtherCAT needs raw socket access. If you see permission errors, grant the capability to your Python interpreter:

```bash
sudo setcap 'cap_net_raw,cap_net_admin=eip' $(which python3)
```

### EtherCAT on macOS

EtherCAT on macOS uses raw sockets via pcap and requires root privileges. Run Python scripts with `sudo`:

```bash
sudo python3 examples/tutorial/01.get_basic_info.py
```

### RS-485 Serial Ports on Linux

When using a USB-RS485 adapter on Linux, the SDK auto-discovery prefers `/dev/serial/by-id/*`, `/dev/ttyUSB*`, `/dev/ttyACM*`, and `/dev/ttyAMA*`. It does not auto-scan `/dev/ttyS*` because those are usually built-in motherboard serial ports. If you use a built-in serial port, pass the device path explicitly to `open()`.

Useful checks:

```bash
lsusb
ls -l /dev/ttyUSB* /dev/ttyACM* /dev/serial/by-id/ 2>/dev/null
python3 -m serial.tools.list_ports
```

If the serial device exists but cannot be opened, make sure your user belongs to the `dialout` group:

```bash
groups
sudo usermod -aG dialout $USER
```

Log out and back in after changing groups.

### CAN-FD Adapters

CAN-FD mode supports ZQWL-CANFD CDC serial adapters. On Linux they usually appear as `/dev/ttyACM0` or a `/dev/serial/by-id/...` alias; on Windows they usually appear as `COMx`.

Useful checks:

```bash
lsusb
lsusb -t
ls -l /dev/ttyACM* /dev/serial/by-id/ 2>/dev/null
python3 -m serial.tools.list_ports
```

If `lsusb -t` shows `Driver=cdc_acm`, the adapter is in CDC serial mode and can be scanned by the SDK in CAN-FD mode.

### RS-485/CAN-FD Slave ID and Baud Rate

RS-485 and CAN-FD devices use holding register `0x0000` as the slave ID register. The left hand defaults to `0x31`, and the right hand defaults to `0x32`.

Override the slave ID for a connection:

```python
hand.open("COM10", slave_id=0x31)
```

Change the connected device ID:

```python
ok = hand.set_slave_id(0x32)
hand.close()
```

Connect with a non-default RS-485 baud rate:

```python
from ghand import RS485BaudRate

hand.open("COM10", slave_id=0x31, baud_rate=RS485BaudRate.BAUD_1000000)
```

Write the RS-485 baud-rate configuration to the device:

```python
ok = hand.set_baudrate_config(RS485BaudRate.BAUD_1000000)
```

For CAN-FD, use a bit timing profile instead of an RS-485 baud-rate enum:

```python
from ghand import CANFDBitTiming

hand.open("COM10", slave_id=0x31, baud_rate=CANFDBitTiming.TIMING_1M_5M)
ok = hand.set_baudrate_config(CANFDBitTiming.TIMING_1M_5M)
```

The baud-rate/timing configuration is stored by the device and takes effect after the next power-up. After the device is power-cycled, pass the configured enum explicitly to `open()`.

RS-485 baud-rate gears:

| Gear | Baud rate |
|------|-----------|
| `0x00` | 57,600 bps |
| `0x01` | 115,200 bps |
| `0x02` | 230,400 bps |
| `0x03` | 460,800 bps |
| `0x04` | 921,600 bps |
| `0x05` | 1,000,000 bps (default) |

CAN-FD baud-rate gears:

| Gear | Arbitration phase | Data phase |
|------|-------------------|------------|
| `0x00` | 500,000 bps, 80% sample point | 1,000,000 bps, 75% sample point |
| `0x01` | 500,000 bps, 80% sample point | 2,000,000 bps, 80% sample point |
| `0x02` | 500,000 bps, 80% sample point | 4,000,000 bps, 80% sample point |
| `0x03` | 500,000 bps, 80% sample point | 5,000,000 bps, 75% sample point |
| `0x04` | 1,000,000 bps, 75% sample point | 4,000,000 bps, 80% sample point |
| `0x05` | 1,000,000 bps, 75% sample point | 5,000,000 bps, 75% sample point (default) |

## Examples

- `examples/tutorial/01.get_basic_info.py`: connect and read device information
- `examples/tutorial/02.move_joints.py`: position control
- `examples/tutorial/03.torque_control.py`: torque control
- `examples/tutorial/04.speed_control.py`: speed control
- `examples/tutorial/05.tactile_callback.py`: tactile data callback
- `examples/tutorial/06.subscription_demo.py`: data subscription
- `examples/tutorial/07.multi_hand.py`: multi-hand discovery and connection
- `examples/demo/`: action and gesture demonstrations
- `examples/extension/`: collision detection and adaptive grasp examples

## Project Structure

```text
GHand-Python-SDK/
|-- src/
|   |-- ghand/                  # Core SDK package
|   |   |-- ghand.py            # Main GHand class and public API
|   |   |-- types.py            # Data types, enums, and structures
|   |   |-- gestures.py         # Predefined gesture utilities
|   |   |-- config/             # Bundled product JSON configurations
|   |   |   |-- ghand5.json
|   |   |   `-- ghandlite1.json
|   |   |-- comm/               # EtherCAT, CAN-FD, and RS-485 drivers
|   |   |-- adaptive_grasp/     # Adaptive grasp internal capability
|   |   |-- collision/          # Collision detection internal capability
|   |   `-- py.typed            # Type hint marker
|-- examples/                   # Tutorial, demo, and extension examples
|-- docs/                       # Sphinx documentation source
|-- tests/                      # Test suite
|-- requirements.txt            # Runtime dependencies
|-- pyproject.toml              # Build configuration
|-- setup.cfg                   # Packaging metadata
|-- setup.py                    # Version loader for setuptools
|-- LICENSE                     # Apache License 2.0
|-- LICENSES/                   # Third-party license texts
|-- THIRD_PARTY_NOTICES.md      # Third-party dependency notices
|-- README.md                   # English README
|-- README.zh.md                # Chinese README
|-- CONTRIBUTING.md             # Contribution guidelines
`-- CHANGELOG.md                # Version history
```

## Open Source & Ecosystem Resources

- **GLI Open Source Hub**: [GitHub](https://github.com/gli-sdk) / [Gitee](https://gitee.com/glitech)
- **Official Documentation**: [GHand Dexterous Hand Docs](https://fcnzogxju7xr.feishu.cn/docx/AhZ6ds2iCoguaAxIzBxciYHinNo)
- **C++ SDK**: [GHand SDK C++](https://github.com/gli-sdk/GHand-Cpp-SDK)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on bug reports, feature requests, and pull requests.

## Support & Feedback

- **Technical support**: For project-specific issues, open an issue in this repository.
- **General inquiries**: [support@glitech.com](mailto:support@glitech.com)

## License

GHand Python SDK is licensed under the [Apache License 2.0](LICENSE).

Third-party dependencies remain subject to their own license terms. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the `LICENSES/` directory
for details.
