# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GHand5 computed per-sensor CAD forces and moments in polling/subscription snapshots, with configurable reference point, bundled PX geometry and explicit CAD-to-taxel rotation convention. Unknown or unhealthy tactile data yields unavailable derived fields.
- Five-finger Mx/My/Mz table, reference coordinates and a moment-history tab in the tactile display; stale readings clear after 0.5 seconds.
- Adaptive force/moment display ranges based on the last five seconds, a fixed-range toggle, larger tactile points, continuous small-force arrows and absolute pale-to-deep force coloring.

### Fixed
- Aligned retained GHandLite1 configuration with the C++ SDK: TMC_AA limits of 30–60 degrees, tactile sensing enabled, and 38/31/31/31/31 tactile sample groups.
- Added L1 Modbus joint addresses, four-register commands and eleven-register hand status, plus EtherCAT's 22-byte hand header, ten-byte joint feedback and eight-byte joint commands.
- Reject unsupported L1 MIT control, nonzero MIT gains, semi-closed-loop commands and parameter access; return `N/A` for unavailable sensor component versions. The V3.1.0 product support policy remains unchanged; L1 users should use SDK 2.x.

## [3.1.0]

### Changed
- Removed the last-operation result query APIs, `OperationResult`, and `SdkError`; diagnostics no longer include cached error fields.
- Aligned existing communication APIs with protocol V2.4: serial-number subindex, parameter refresh commands, and firmware version queries. EtherCAT tactile data is decoded as resultant force followed by distributed force for each finger.
- CANFD and RS485 PID and stall-tolerance operations retain the base interface's unsupported behavior until device firmware implements them.
- Standardized distributed tactile forces to Newtons on all transports (CANFD/RS485 values are now divided by 10).
- Updated CANFD timing profiles to V2.4 gears 0x00–0x07, with default gear 0x07. Enum values changed; the unsupported 500K/5M profile was removed.

### Removed
- Removed `GHand.get_diagnostics()` and the `Diagnostics` data types. Firmware version and hand type are now read from the device on each call.

## [2.2.1] - 2026-08-24

### Added
- Support for Linux ARM64 (aarch64) architecture
- Support for macOS (Intel x86_64 and Apple Silicon arm64)

### Changed
- Replaced unmaintained `netifaces` dependency with `psutil` for better cross-platform compatibility and macOS Apple Silicon support
- Kept the GHand Python SDK under Apache License 2.0.
- Updated the PySOEM dependency to the MIT-licensed `>=1.0.2,<2.0.0` release range.
- Split collision and visualization dependencies into optional extras.
- Added missing optional dependency declarations for `trimesh`, `meshcat`, and `matplotlib`.
- Added third-party license notices and license text files.
- Added `RS485BaudRate` and `CANFDBitTiming` enums for RS485/CANFD baud-rate configuration and updated public examples to avoid raw protocol gear values.
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
