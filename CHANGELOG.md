# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2026-08-17

### Added
- Baud rate gear configuration for RS485 and CANFD, including documented gear mappings and connection-time gear selection.
- Firmware package, position sensor, tactile sensor, motor driver, thumb tactile sensor, and finger tactile sensor version query APIs.

### Changed
- Refactored CANFD and RS485 register address handling for clearer protocol maintenance.
- Improved state and error handling names for clearer diagnostics.
- Updated README and dependency guidance for current installation flows.

### Fixed
- Handled unavailable motor driver version values without failing device information reads.
- Constrained NumPy to `>=1.24.0,<1.25.0` to remain compatible with SciPy 1.8 environments.

## [2.1.0] - 2026-08-10

### Added
- Linux support improvements for EtherCAT, CANFD, and RS485 adapter discovery and connection.
- RS485 and CANFD slave ID configuration APIs.
- Adaptive grasp module and examples.
- Additional motor and tactile sensor error codes.

### Changed
- Updated product naming and configuration references to `GHand5` and `GHandLite1`.
- Updated GHand 5 and GHand Lite 1 model identifiers in product configuration files.
- Reordered GHand Lite 1 joint definitions to match the runtime configuration.
- Optimized CANFD register writing.
- Improved adaptive grasp release behavior and position tolerance defaults.

### Fixed
- Removed timeout text from error-code messages for clearer reporting.

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
