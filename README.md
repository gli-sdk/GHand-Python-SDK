# GHand Python SDK

[![Version](https://img.shields.io/badge/version-v3.1.0-blue.svg)](src/ghand/version.py)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

[中文](README.zh.md)

The official Python SDK for the GHand dexterous hand. It provides high-level APIs for EtherCAT, CAN-FD, and RS-485 communication, joint control, tactile sensing, collision detection, and adaptive grasp examples.

## Table of Contents

- [Key Features](#key-features)
  - [Product Support Matrix](#product-support-matrix)
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

### Product Support Matrix

The capabilities below apply to GHand5 with the current V3.1.0 release. **For GHandLite1 (L1), use SDK 2.xx (2.x)** and follow that version's README, API and protocol documentation.

| Product | SDK version | Transports | Control and tactile capabilities |
| --- | --- | --- | --- |
| GHand5 | Current V3.1.0 | EtherCAT, CAN-FD, RS-485 | Position, velocity, current, MIT, CUSTOM; tactile feedback, callbacks, on/off, zeroing and display |
| GHandLite1 (L1) | Use 2.xx (2.x), e.g. [V2.2.2](https://github.com/gli-sdk/GHand-Python-SDK/tree/V2.2.2) | See the corresponding 2.x documentation | See the corresponding 2.x documentation |

The GHandLite1 types and configuration files retained in this repository do not indicate support for connecting that product with V3.1.0. L1 users should check out the corresponding 2.x version before following its installation instructions.

- **Device control**
  - Open and close GHand devices over EtherCAT, CAN-FD, or RS-485.
  - Read firmware, firmware package, serial number, product name, hand type, and component versions.
  - Clear faults, initialize joints, stop motion, and run common device operations.

- **Joint control**
  - Command one or more joints by position, velocity, or current.
  - Read current joint angle, velocity, current, state, and error feedback.
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
pip install -e .
```

Install collision-detection dependencies only when needed:

```bash
pip install -e ".[collision]"
```

Gitee mirror:

```bash
git clone https://gitee.com/glitech/GHand-Python-SDK.git
cd GHand-Python-SDK
pip install -e .
```

Install collision-detection dependencies only when needed:

```bash
pip install -e ".[collision]"
```

## Quick Start

Make sure your GHand hardware is connected and powered on before running examples.

```bash
python examples/tutorial/01.get_basic_info.py
```

Minimal EtherCAT example:

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

Place these additional version queries after connecting and before closing the device:

```python
print("Firmware package:", hand.get_firmware_package_version())
print("Position sensor:", hand.get_position_sensor_version())
print("Tactile MCU:", hand.get_tactile_sensor_version())
print("Motor driver:", hand.get_motor_driver_version())
print("Thumb tactile sensor:", hand.get_thumb_tactile_sensor_version())
print("Finger tactile sensor:", hand.get_finger_tactile_sensor_version())
```

Hand-level CUSTOM mode uses each joint's `control_mode`, `loop_type` and
`control_state`. Run this code after connecting and before closing the device:

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

Angles are in degrees; velocity and current are percentages. In position mode, velocity and current are limits and should be nonzero. Control modes and feedback loops must match within each finger arbitration group; see the [CUSTOM example](examples/tutorial/14.custom_control.py).

A successful `move_joints()` return means the command was sent; confirm execution with `get_hand_info()` and `get_joints()`. `close()` closes the communication link. To stop holding or release drive torque, send `stop()` or `disable_hand()` as appropriate and confirm feedback before closing.

Minimal CAN-FD example:

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

Minimal RS-485 example:

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

RS-485 and CAN-FD devices use holding register `0x0003` as the slave ID register; `0x0000` is the connection-control register. The left hand defaults to `0x31`, and the right hand defaults to `0x32`.

Override the slave ID for a connection:

```python
hand.open("COM10", slave_id=0x31)
```

Change the connected device ID:

```python
ok = hand.set_slave_id(0x32)
hand.close()
```

Default baud rates:

- RS-485: 1,000,000 bps, `RS485BaudRate.BAUD_1000000` (gear `0x05`).
- CAN-FD: 1 Mbps arbitration and 5 Mbps data, both at a 75% sample point, `CANFDBitTiming.TIMING_1M_5M` (gear `0x07`).

The `baudrate` argument to `open()` selects the rate for the connection; it does not change the device's saved configuration. `set_baudrate()` writes that configuration. **After a successful change, turn the hand's power off and back on for the new rate to take effect. Closing and reopening the SDK connection alone does not apply it.**

The examples below assume the device currently uses the default rate and `hand` was created with the corresponding transport. If the device's rate was previously changed, specify its current rate for the initial connection too.

RS-485: connect at the current rate and configure 115,200 bps:

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

**Now turn the hand's power off and back on**, then connect with the new rate explicitly:

```python
if not hand.open("COM10", slave_id=0x31, baudrate=RS485BaudRate.BAUD_115200):
    raise RuntimeError("Connection failed")
# Perform device operations here, then call hand.close().
```

CAN-FD: use `CANFDBitTiming`, connect with the current profile and configure 1 Mbps arbitration / 2 Mbps data:

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

**Now turn the hand's power off and back on**, then connect with the new profile explicitly:

```python
if not hand.open("COM10", slave_id=0x31, baudrate=CANFDBitTiming.TIMING_1M_2M):
    raise RuntimeError("Connection failed")
# Perform device operations here, then call hand.close().
```

The device retains the saved configuration across power cycles. Continue passing the corresponding `baudrate` explicitly on subsequent connections; the SDK does not automatically detect the device's saved rate.

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
| `0x04` | 1,000,000 bps, 75% sample point | 1,000,000 bps, 75% sample point |
| `0x05` | 1,000,000 bps, 75% sample point | 2,000,000 bps, 80% sample point |
| `0x06` | 1,000,000 bps, 75% sample point | 4,000,000 bps, 80% sample point |
| `0x07` | 1,000,000 bps, 75% sample point | 5,000,000 bps, 75% sample point (default) |

## Examples

- `examples/tutorial/01.get_basic_info.py`: connect and read device information
- `examples/tutorial/02.move_joints.py`: position control
- `examples/tutorial/03.current_control.py`: current control
- `examples/tutorial/04.velocity_control.py`: velocity control
- `examples/tutorial/05.tactile_callback.py`: tactile data callback
- `examples/tutorial/06.subscription_demo.py`: data subscription
- `examples/tutorial/07.multi_hand.py`: multi-hand discovery and connection
- `examples/tutorial/12.switch_baud_rate.py`: baud-rate configuration
- `examples/tutorial/13.mit_control.py`: MIT control
- `examples/tutorial/14.custom_control.py`: CUSTOM control
- `examples/tutorial/15.tactile_display.py`: tactile display with device setup, subscription, and cleanup
- `examples/demo/`: action and gesture demonstrations
- `examples/extension/`: collision detection and adaptive grasp examples

Adaptive grasp requires hardware with accessible tactile sensors; see the [adaptive grasp guide](src/ghand/adaptive_grasp/README.md).

Tactile display dependencies are included with the SDK. Install and launch the example:

```bash
python -m pip install .
python examples/tutorial/15.tactile_display.py
```

The example connects GHand5 via EtherCAT and passes the connected device to
`ghand.tactile_display.display.TactileDisplay(hand)`. The display manages tactile
commands, subscriptions, its worker thread, and cleanup when the window closes.
The caller owns the device connection and closes it after the display exits.
For custom data sources, `ghand.tactile_display.window.TactileWindow` remains
available as a display-only component.

## Project Structure

```text
GHand-Python-SDK/
|-- src/
|   |-- ghand/                  # Core SDK package
|   |   |-- ghand.py            # Main GHand class and public API
|   |   |-- types/              # Typed enums and data objects
|   |   |   |-- __init__.py      # Public type exports
|   |   |   |-- enums.py         # Product, protocol, joint, and sensor enums
|   |   |   |-- errors.py        # Device errors and warning bitfields
|   |   |   `-- data.py          # Command and feedback dataclasses
|   |   |-- _product_config.py  # Product configuration models and loading
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
|-- pyproject.toml              # Build configuration
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
