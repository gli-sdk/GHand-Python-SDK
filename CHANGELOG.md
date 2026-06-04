# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-06-04

### Added
- Apache License 2.0 and community governance files.
- CANFD and RS485 protocol support.
- Unified `DeviceData` dataclass for cross-protocol subscription callbacks.
- Support for different products via JSON configuration.

### Changed
- **Project**: Renamed from XiaoYao SDK to GHand SDK; `DexHand` refactored to `GHand`.
- **Dependencies**: Deferred `numpy` and `collision_sdk` loading to first use.
- **API**: `move_joints()` no longer mutates input objects; `get_joints()` / `get_hand_info()` are pure getters.
- **Subscription**: Unified callback signature to `Callable[[DeviceData], None]` across all protocols.

## [1.1.2] - 2025-05-20

### Added
- Collision detection support (`check_collision`, `set_safety_margin`).
- Custom exception system (`GHandError`, `CommunicationError`, `HandStateError`).
- Multi-hand controller example.
- Glove control example.

### Changed
- Improved logging configuration with `configure_logging` and `configure_logging_file`.

## [1.1.1] - 2025-05-18

### Added
- Subscription-based data callback API.
- Tactile sensor data support.

### Fixed
- Various EtherCAT communication stability fixes.

## [1.1.0] - 2025-05-15

### Added
- Initial public release of GHand SDK.
- Support for EtherCAT, CAN, and RS485 communication.
- Joint control API (position, speed, torque modes).
- Preset gestures support.

### Changed
- Migrated from internal GHand SDK to open-source GHand SDK.
