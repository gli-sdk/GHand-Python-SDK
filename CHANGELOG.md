# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Kept collision runtime dependencies in core metadata and moved visualization-only dependencies (`matplotlib`, `meshcat`) to the adaptive extra.
- Made `TactileVisualizer` and collision 3D visualization imports optional so the SDK imports cleanly without matplotlib/meshcat installed.
- Disabled `enable_visualization` by default in `AdaptiveGraspConfig`.
- Updated `README.md` and `README.zh.md` to reflect the simplified dependency set.

## [2.2.0] - 2026-08-17

### Added
- Baud rate gear configuration for RS485 and CANFD, including documented gear mappings and connection-time gear selection.
- Firmware package, position sensor, tactile sensor, motor driver, thumb tactile sensor, and finger tactile sensor version query APIs.

### Changed
- Refactored CANFD and RS485 register address handling for clearer protocol maintenance.
- Improved state and error handling names for clearer diagnostics.
- Updated README and dependency guidance for current installation flows.

### Fixed
- Added Python SDK operation result APIs and stable SDK error classes for bool-returning operations.
- Added a compatible `GHand.get_diagnostics()` API with connection, subscription, and last-error fields.
- Made default logging import-safe with `NullHandler`; console logging is now opt-in.
- Removed the fixed one-second wait from `GHand.close()`.
- Stored subscription intervals per subscriber and avoided worker-thread self-join during shutdown.
- Handled unavailable motor driver version values without failing device information reads.
- Moved collision detection source into the SDK package as `ghand.collision`; no runtime Git download or external `collision_sdk` package is required.
- Collision modules import normally while collision resources are initialized and checks are executed only when requested.
- Prevented duplicate dispatch of the same subscription frame and made subscription shutdown deterministic after the last unsubscribe.
- Removed high-frequency success-path INFO logs from movement and polling APIs.

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
- **Dependencies**: Collision resources are initialized on first use while SDK modules load normally.
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
