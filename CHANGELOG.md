# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Added MIT License and improved project configuration.
- Added community governance files: CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md.
- Added pre-commit hooks configuration.
- Added mypy static type checking configuration.

### Changed
- Refactored DexHand to GHand class to unify naming conventions.
- Renamed project from XiaoYao SDK to GHand SDK and refactored project structure.
- All Chinese text in source code and examples translated to English.
- Improved data structure definitions and joint limit management.
- `TactileRegionConfig.name` changed to `TactileRegionConfig.id` using `TactileSensorId` enum.
- Dynamic PDO sizing and configuration-driven product behavior via JSON config.

### Fixed
- Fixed f-string usage in logging calls to comply with Google Python Style Guide.
- Fixed import ordering and type annotations across the codebase.
- Fixed module-level docstrings and line length issues.

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
