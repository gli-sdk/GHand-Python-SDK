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

"""GHand SDK type definitions.

All enums, dataclasses, and exceptions are centralized here to avoid
circular imports.
"""

import enum
from dataclasses import dataclass, field
from typing import Optional

# ============================================================================
# Base enums
# ============================================================================


class JointId(enum.IntEnum):
    THUMB_IP = 0
    THUMB_MCP = 1
    THUMB_TMC_FE = 2
    THUMB_TMC_AA = 3
    THUMB_TMC_PS = 4
    FF_DIP = 5
    FF_PIP = 6
    FF_MCP = 7
    FF_MCP_AA = 8
    MF_DIP = 9
    MF_PIP = 10
    MF_MCP = 11
    RF_DIP = 12
    RF_PIP = 13
    RF_MCP = 14
    LF_DIP = 15
    LF_PIP = 16
    LF_MCP = 17


class RS485BaudRate(enum.IntEnum):
    """Predefined RS485 baud rates mapped to GHand protocol gear values."""

    BAUD_57600 = 0x00
    BAUD_115200 = 0x01
    BAUD_230400 = 0x02
    BAUD_460800 = 0x03
    BAUD_921600 = 0x04
    BAUD_1000000 = 0x05


class CANFDBitTiming(enum.IntEnum):
    """Predefined CAN FD bit timing profiles.

    Names use ``TIMING_<arbitration bitrate>_<data bitrate>``. Each value maps
    directly to the protocol gear stored by the GHand device.
    """

    # Arbitration: 500 Kbps @ 80%; data: 1 Mbps @ 75%.
    TIMING_500K_1M = 0x00
    # Arbitration: 500 Kbps @ 80%; data: 2 Mbps @ 80%.
    TIMING_500K_2M = 0x01
    # Arbitration: 500 Kbps @ 80%; data: 4 Mbps @ 80%.
    TIMING_500K_4M = 0x02
    # Arbitration: 500 Kbps @ 80%; data: 5 Mbps @ 75%.
    TIMING_500K_5M = 0x03
    # Arbitration: 1 Mbps @ 75%; data: 4 Mbps @ 80%.
    TIMING_1M_4M = 0x04
    # Arbitration: 1 Mbps @ 75%; data: 5 Mbps @ 75%.
    TIMING_1M_5M = 0x05


def _unknown_member(cls, fallback, value):
    """Build a pseudo-member named after *fallback* but carrying *value*.

    Lets an unrecognized device code stay inside the enum type (so ``.name``
    and ``.value`` always work) without discarding the number reported by the
    device: ``ErrorCode(176)`` is ``<ErrorCode.UNKNOWN_ERROR: 176>``.
    """
    if type(value) is not int:
        return None
    pseudo = int.__new__(cls, value)
    pseudo._name_ = fallback.name
    pseudo._value_ = value
    return pseudo


_NUMERIC_FORMAT_TYPES = "bcdeEfFgGnoxX%"


class DeviceCode(enum.IntEnum):
    """IntEnum whose text form is ``NAME(value)`` rather than a bare number.

    Device codes are reported as plain integers, and an unrecognized one is
    folded into a catch-all member, so the numeric value has to travel
    alongside the name to stay diagnosable.
    """

    def __str__(self):
        return f"{self.name}({self.value})"

    def __format__(self, format_spec):
        # Numeric specs ("d", "03d") keep int semantics so existing callers
        # that format these as numbers are unaffected; everything else pads
        # the NAME(value) text.
        if format_spec and format_spec[-1] in _NUMERIC_FORMAT_TYPES:
            return int.__format__(self, format_spec)
        return str.__format__(str(self), format_spec)


class State(DeviceCode):
    STOPPED = 0
    RUNNING = 1
    ABNORMAL_RUNNING = 2
    PROTECTIVE_STOPPED = 3
    UNKNOWN_STATE = 255

    @classmethod
    def _missing_(cls, value):
        """Map any undefined state to UNKNOWN_STATE, keeping the raw value."""
        return _unknown_member(cls, cls.UNKNOWN_STATE, value)

    @property
    def is_abnormal(self) -> bool:
        """True for protective stop, abnormal running, or any undefined state."""
        return self not in (State.STOPPED, State.RUNNING)


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
        return _unknown_member(cls, cls.UNKNOWN_ERROR, value)


class HandType(enum.Enum):
    NONE = "none"
    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"


class CommType(enum.Enum):
    UNKNOWN = "unknown"
    ETHERCAT = "ethercat"
    CANFD = "canfd"
    RS485 = "rs485"


class CtrlMode(enum.Enum):
    POSITION = 0
    TORQUE = 1
    SPEED = 2


class TactileSensorId(enum.IntEnum):
    THUMB = 0
    FF = 1
    MF = 2
    RF = 3
    LF = 4


class ProductType(enum.Enum):
    GHand5 = "GHand5"
    GHandLite1 = "GHandLite1"


class GestureType(enum.Enum):
    OPEN_HAND = "open_hand"
    FIST = "fist"
    OK = "ok"
    THUMBS_UP = "thumbs_up"
    SIX_SIGN = "six_sign"


class SelfTestError(enum.IntFlag):
    """A0 summary bit mask. Multiple bits may be set simultaneously."""

    NONE = 0x00
    MOTOR = 0x01
    POSITION_SENSOR_UNMAPPED = 0x02
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


# ============================================================================
# Dataclasses
# ============================================================================


@dataclass
class TactileRegionConfig:
    """Configuration for a single tactile sensor region."""

    id: TactileSensorId
    count: int


@dataclass
class ProductConfig:
    """Product-specific configuration loaded from JSON."""

    name: str = ""
    model: str = ""
    valid_joints: list[JointId] = field(default_factory=list)
    joint_limits: dict[JointId, tuple[float, float]] = field(default_factory=dict)
    has_tactile: bool = False
    tactile_regions: list[TactileRegionConfig] = field(default_factory=list)
    product_type: ProductType | None = None
    slave_id: int = 0x31


@dataclass
class HandFaultInfo:
    """Aggregated fault information for the hand device."""

    state: State
    error_code: ErrorCode
    temperature: Optional[int] = None

    def __str__(self):
        """Return a human-readable fault description."""
        if self.error_code != ErrorCode.NORMAL:
            base_msg = _ERROR_MESSAGES.get(
                self.error_code, _ERROR_MESSAGES[ErrorCode.UNKNOWN_ERROR]
            )
        else:
            base_msg = "Device operating normally"

        if self.state.is_abnormal:
            state_msg = _STATE_MESSAGES.get(self.state, _STATE_MESSAGES[State.UNKNOWN_STATE])
            if self.error_code == ErrorCode.NORMAL:
                base_msg = f"{state_msg}, but error code is 0"
            else:
                base_msg = f"{state_msg}, {base_msg}"

        parts = []
        if self.temperature is not None:
            parts.append(f"Temperature: {self.temperature}°C")

        msg = base_msg
        if parts:
            msg = f"{base_msg} ({', '.join(parts)})"
        return (
            f"State: {self.state}, Error: {self.error_code} - {msg}"
        )


@dataclass
class JointFaultInfo:
    """Fault information for an individual joint."""

    joint_id: str
    state: State
    error_code: ErrorCode

    def __str__(self):
        """Return a human-readable joint fault description."""
        return f"{self.joint_id}: State={self.state}, Error={self.error_code}"


@dataclass
class HandState:
    """High-level status of the dexterous hand."""

    state: State = State.STOPPED
    error: ErrorCode = ErrorCode.NORMAL
    temperature: int = 0


@dataclass
class JointCommand:
    """Single joint command sent to the device."""

    id: int = JointId.THUMB_IP
    angle: float = 0.0  # degrees
    speed: int = 0
    torque: int = 0


@dataclass
class JointData:
    """Single joint state received from the device."""

    id: int = JointId.THUMB_IP
    state: State = State.STOPPED
    error: ErrorCode = ErrorCode.NORMAL
    angle: float = 0.0  # degrees
    speed: int = 0
    torque: int = 0


@dataclass
class TactileInfo:
    """Tactile sensor reading for a single finger."""

    state: bool = False
    resultant_force: list[float] | None = None
    distributed_force: list[float] | None = None


@dataclass
class DeviceData:
    """Unified data carrier for subscription callbacks across all protocols."""

    hand: HandState
    joints: list[JointData]
    tactile: dict[TactileSensorId, TactileInfo] | None = None
    timestamp: float | None = None

    def __post_init__(self):
        for joint in self.joints:
            jid = JointId(joint.id)
            setattr(self, jid.name.lower(), joint)


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

        if self.summary & SelfTestError.POSITION_SENSOR_UNMAPPED:
            lines.append("position_sensor_unmapped: position sensor unmapped")
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


# ============================================================================
# Exceptions
# ============================================================================

_ERROR_MESSAGES = {
    ErrorCode.MOTOR_HARDWARE_OVERCURRENT: "Motor hardware overcurrent",
    ErrorCode.MOTOR_SOFTWARE_OVERCURRENT: "Motor software overcurrent",
    ErrorCode.MOTOR_BUS_OVERCURRENT: "Motor bus overcurrent",
    ErrorCode.MOTOR_PHASE_LOST: "Motor phase lost",
    ErrorCode.MOTOR_STALLED: "Motor stalled",
    ErrorCode.MOTOR_DRIVER_OVERTEMP: "Motor driver overtemperature",
    ErrorCode.MOTOR_COMM_ERROR: "Motor communication error",
    ErrorCode.MOTOR_OVERTEMP: "Motor temperature too high",
    ErrorCode.JOINT_CONFLICT: "Joint conflict",
    ErrorCode.TIP_CONFLICT: "Tip conflict",
    ErrorCode.JOINT_POSITION_ABNORMAL: "Joint position abnormal",
    ErrorCode.LOW_TEMP: "Low temperature",
    ErrorCode.HIGH_TEMP: "High temperature",
    ErrorCode.LOW_VOLTAGE: "Low voltage",
    ErrorCode.HIGH_VOLTAGE: "High voltage",
    ErrorCode.TACTILE_DISCONNECTED: "Tactile sensor disconnected",
    ErrorCode.TACTILE_DATA_ABNORMAL: "Tactile sensor data abnormal",
    ErrorCode.SELF_TEST_ERROR: "Self-test error",
    ErrorCode.PARAM_ERROR: "Parameter error",
    ErrorCode.UNKNOWN_ERROR: "Unknown error",
}

_STATE_MESSAGES = {
    State.PROTECTIVE_STOPPED: "Device entered protective stop",
    State.ABNORMAL_RUNNING: "Device running abnormally",
    State.UNKNOWN_STATE: "Device in unknown state",
}
