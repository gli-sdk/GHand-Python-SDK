# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

# Copyright 2026 GLITech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Device error codes, diagnostic results, SDK errors, and exceptions."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from enum import Enum

from .enums import CommType, DeviceCode, JointId, unknown_member


class ErrorCode(DeviceCode):
    NORMAL = 0
    MOTOR_HARDWARE_OVERCURRENT = 1
    MOTOR_SOFTWARE_OVERCURRENT = 2
    MOTOR_BUS_OVERCURRENT = 3
    MOTOR_PHASE_LOST = 4
    MOTOR_STALLED = 5
    MOTOR_DRIVER_OVERTEMP = 6
    MOTOR_COMM_ERROR = 7
    MOTOR_OVERTEMP = 8
    JOINT_CONFLICT = 11
    TIP_CONFLICT = 12
    JOINT_POSITION_ABNORMAL = 13
    LOW_TEMP = 21
    HIGH_TEMP = 22
    LOW_VOLTAGE = 23
    HIGH_VOLTAGE = 24
    TACTILE_DISCONNECTED = 31
    TACTILE_ERROR = 31
    TACTILE_DATA_ABNORMAL = 32
    SELF_TEST_ERROR = 41
    PARAM_ERROR = 101
    UNKNOWN_ERROR = 201

    @classmethod
    def _missing_(cls, value):
        """Map any undefined code to UNKNOWN_ERROR, keeping the raw value."""
        return unknown_member(cls, cls.UNKNOWN_ERROR, value)


class JointErrorCode(DeviceCode):
    NORMAL = 0
    MOTOR_HARDWARE_OVERCURRENT = 1
    MOTOR_CONTINUOUS_CURRENT_HIGH = 2
    MOTOR_BUS_OVERCURRENT = 3
    MOTOR_HARDWARE_OVERVOLTAGE = 4
    MOTOR_HARDWARE_UNDERVOLTAGE = 5
    MOTOR_PHASE_LOSS = 6
    MOTOR_STALLED = 7
    MOTOR_CHIP_OVERTEMPERATURE = 8
    COMMUNICATION_LOST = 9
    MOTOR_SOFTWARE_OVERVOLTAGE = 10
    MOTOR_SOFTWARE_UNDERVOLTAGE = 11
    MOTOR_OVERTEMPERATURE = 12
    MOTOR_WINDING_OVERTEMPERATURE = 13
    UNKNOWN_ERROR = 255

    @classmethod
    def _missing_(cls, value):
        """Map undefined joint error codes to UNKNOWN_ERROR, keeping the raw value."""
        return unknown_member(cls, cls.UNKNOWN_ERROR, value)


class HandWarning(enum.IntFlag):
    """Hand-level warning bits from the EtherCAT V2.1 TPDO."""

    NONE = 0
    TEMPERATURE_SENSOR_1_ABNORMAL = 1 << 0
    TEMPERATURE_SENSOR_2_ABNORMAL = 1 << 1
    FAN_ABNORMAL = 1 << 2
    TACTILE_BOARD_COMMUNICATION_ABNORMAL = 1 << 3
    THUMB_TACTILE_SENSOR_DISCONNECTED = 1 << 4
    FOREFINGER_TACTILE_SENSOR_DISCONNECTED = 1 << 5
    MIDDLE_FINGER_TACTILE_SENSOR_DISCONNECTED = 1 << 6
    RING_FINGER_TACTILE_SENSOR_DISCONNECTED = 1 << 7
    LITTLE_FINGER_TACTILE_SENSOR_DISCONNECTED = 1 << 8


class HandFault(enum.IntFlag):
    """Hand-level fault categories from the EtherCAT V2.1 TPDO."""

    NONE = 0
    JOINT_MOTOR = 1 << 0
    POSITION_SENSOR_ABNORMAL = 1 << 1
    POSITION_SENSOR_UNCALIBRATED = 1 << 2
    ZEROING_JOINT_STALL = 1 << 3
    ZEROING_BRAKE_TIMEOUT = 1 << 4
    ZEROING_MOTOR_COMMUNICATION = 1 << 5


class HandCriticalError(enum.IntFlag):
    """Hand-level critical-error bits from the EtherCAT V2.1 TPDO."""

    NONE = 0
    UNKNOWN_ERROR = 1 << 0
    SELF_TEST_ERROR = 1 << 1
    POSITION_SENSOR_VERSION_MISMATCH = 1 << 2
    TACTILE_SENSOR_VERSION_MISMATCH = 1 << 3
    MOTOR_DRIVER_VERSION_MISMATCH = 1 << 4
    POSITION_BOARD_DETECTION_ABNORMAL = 1 << 5
    TEMPERATURE_TOO_HIGH = 1 << 6
    TEMPERATURE_TOO_LOW = 1 << 7
    ZEROING_GLOBAL_TIMEOUT = 1 << 8


class SelfTestError(enum.IntFlag):
    """A0 summary bit mask. Multiple bits may be set simultaneously."""

    NONE = 0x00
    MOTOR = 0x01
    ZEROING = 0x04
    FAN = 0x08
    TEMPERATURE_SENSOR = 0x10
    TACTILE_SENSOR = 0x20
    POSITION_SENSOR = 0x40
    VERSION = 0x80


class VersionCheckError(enum.IntFlag):
    """A1 version-mismatch bit mask."""

    NONE = 0x00
    MOTOR_DRIVER = 0x20
    TACTILE_SENSOR = 0x40
    POSITION_SENSOR = 0x80


class TactileCheckError(enum.IntFlag):
    """A3 tactile-sensor bit mask per motor channel."""

    NONE = 0x00
    THUMB_TIP_DISCONNECTED = 0x01
    FF_TIP_DISCONNECTED = 0x02
    MF_TIP_DISCONNECTED = 0x04
    RF_TIP_DISCONNECTED = 0x08
    LF_TIP_DISCONNECTED = 0x10
    COMMUNICATION_FAILED = 0x80


class ZeroingError(enum.IntEnum):
    """A6 zeroing error per motor channel (single-value enum)."""

    NONE = 0x00
    MOTOR_ABNORMAL = 0x01
    JOINT_STALL = 0x02
    BRAKE_TIMEOUT = 0x03
    GLOBAL_TIMEOUT = 0x04
    COMMUNICATION_FAULT = 0x05


class MotorCheckError(enum.IntEnum):
    """A8 motor-detection error per motor channel."""

    NONE = 0x00
    HARDWARE_OVER_CURRENT = 0x01
    SOFTWARE_OVER_CURRENT = 0x02
    BUS_OVER_CURRENT = 0x03
    HARDWARE_OVER_VOLTAGE = 0x04
    HARDWARE_UNDER_VOLTAGE = 0x05
    PHASE_LOSS = 0x06
    STALL = 0x07
    HARDWARE_OVER_TEMPERATURE = 0x08
    COMMUNICATION_LOST = 0x09
    SOFTWARE_OVER_VOLTAGE = 0x0A
    SOFTWARE_UNDER_VOLTAGE = 0x0B
    SOFTWARE_OVER_TEMPERATURE = 0x0C
    POSITION_SENSOR_ERROR = 0x0D


@dataclass
class MotorDiagnosticError:
    """Self-test error for a single 13-channel motor slot."""

    motor_index: int
    joint_id: JointId | None
    error_code: int


@dataclass
class SelfTestErrorInfo:
    """Structured result of the self-test error query (Command 0xA0)."""

    summary: SelfTestError = SelfTestError.NONE
    version: VersionCheckError = VersionCheckError.NONE
    position_sensor: list[MotorDiagnosticError] = field(default_factory=list)
    tactile_sensor: list[MotorDiagnosticError] = field(default_factory=list)
    temperature: int = 0
    fan: int = 0
    zeroing: list[MotorDiagnosticError] = field(default_factory=list)
    motor: list[MotorDiagnosticError] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return self.summary != SelfTestError.NONE

    def describe(self) -> str:
        """Return a human-readable description of all self-test errors."""
        lines = [f"summary: 0x{int(self.summary):02X}"]

        if self.summary != SelfTestError.NONE:
            names = [
                flag.name
                for flag in SelfTestError
                if flag != SelfTestError.NONE and self.summary & flag
            ]
            lines[0] += f" ({', '.join(names)})"

        if self.summary & SelfTestError.VERSION:
            names = [
                flag.name
                for flag in VersionCheckError
                if flag != VersionCheckError.NONE and self.version & flag
            ]
            lines.append(
                f"version: 0x{int(self.version):02X} ({', '.join(names) or 'none'})"
            )
        if self.summary & SelfTestError.POSITION_SENSOR:
            lines.append(
                "position_sensor: "
                + _describe_motor_errors(
                    self.position_sensor,
                    lambda c: "position sensor abnormal" if c else "unknown",
                )
            )
        if self.summary & SelfTestError.TACTILE_SENSOR:
            lines.append(
                "tactile_sensor: "
                + _describe_motor_errors(self.tactile_sensor, _describe_tactile_code)
            )
        if self.summary & SelfTestError.TEMPERATURE_SENSOR:
            desc = "temperature sensor abnormal" if self.temperature else "none"
            lines.append(f"temperature: 0x{self.temperature:02X} ({desc})")
        if self.summary & SelfTestError.FAN:
            desc = "fan abnormal" if self.fan else "none"
            lines.append(f"fan: 0x{self.fan:02X} ({desc})")
        if self.summary & SelfTestError.ZEROING:
            lines.append(
                "zeroing: "
                + _describe_motor_errors(
                    self.zeroing, lambda c: _enum_name_or_unknown(ZeroingError, c)
                )
            )
        if self.summary & SelfTestError.MOTOR:
            lines.append(
                "motor: "
                + _describe_motor_errors(
                    self.motor, lambda c: _enum_name_or_unknown(MotorCheckError, c)
                )
            )
        return "\n  ".join(lines)


def _enum_name_or_unknown(enum_type, code: int) -> str:
    try:
        return enum_type(code).name
    except ValueError:
        return f"unknown (0x{code:02X})"


def _describe_tactile_code(code: int) -> str:
    names = [
        flag.name
        for flag in TactileCheckError
        if flag != TactileCheckError.NONE and code & flag
    ]
    return ", ".join(names) if names else f"unknown (0x{code:02X})"


def _describe_motor_errors(errors: list[MotorDiagnosticError], describe_code) -> str:
    if not errors:
        return "none"
    return "; ".join(
        f"motor={e.motor_index} "
        f"joint={e.joint_id.name if e.joint_id is not None else 'unknown'} "
        f"code=0x{e.error_code:02X} ({describe_code(e.error_code)})"
        for e in errors
    )


class SdkError(Enum):
    OK = "ok"
    NOT_CONNECTED = "not_connected"
    INVALID_ARGUMENT = "invalid_argument"
    NOT_SUPPORTED = "not_supported"
    TIMEOUT = "timeout"
    TRANSPORT_ERROR = "transport_error"
    PROTOCOL_ERROR = "protocol_error"
    CONFIG_ERROR = "config_error"
    DEVICE_REJECTED = "device_rejected"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class OperationResult:
    code: SdkError = SdkError.OK
    message: str = ""
    comm: CommType | None = None


class GHandError(Exception):
    """Base class for GHand SDK exceptions."""


class CommunicationError(GHandError):
    """Raised when a communication operation fails unexpectedly."""


class HandStateError(GHandError):
    """Raised when device state prevents an operation."""
