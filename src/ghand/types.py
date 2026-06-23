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
    THUMB_DIP = 0
    THUMB_PIP = 1
    THUMB_MCP = 2
    THUMB_SWING = 3
    THUMB_ROTATION = 4
    FF_DIP = 5
    FF_PIP = 6
    FF_MCP = 7
    FF_SWING = 8
    MF_DIP = 9
    MF_PIP = 10
    MF_MCP = 11
    RF_DIP = 12
    RF_PIP = 13
    RF_MCP = 14
    LF_DIP = 15
    LF_PIP = 16
    LF_MCP = 17


class State(enum.IntEnum):
    STOPPED = 0
    RUNNING = 1
    ABNORMAL_RUNNING = 2
    PROTECTIVE_STOPPED = 3


class ErrorCode(enum.IntEnum):
    NORMAL = 0
    MOTOR_HARDWARE_OVERCURRENT = 1
    MOTOR_SOFTWARE_OVERCURRENT = 2
    MOTOR_BUS_OVERCURRENT = 3
    MOTOR_PHASE_LOST = 4
    MOTOR_STALLED = 5
    MOTOR_DRIVER_OVERTEMP = 6
    MOTOR_COMM_ERROR = 7
    JOINT_CONFLICT = 11
    TIP_CONFLICT = 12
    LOW_TEMP = 21
    HIGH_TEMP = 22
    LOW_VOLTAGE = 23
    HIGH_VOLTAGE = 24
    TACTILE_ERROR = 31
    PARAM_ERROR = 101
    TIMEOUT = 102
    UNKNOWN_ERROR = 201


class HandType(enum.Enum):
    UNKNOWN = "unknown"
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
    G5 = "G5"
    L1 = "L1"


class GestureType(enum.Enum):
    OPEN_HAND = "open_hand"
    FIST = "fist"
    OK = "ok"
    THUMBS_UP = "thumbs_up"
    SIX_SIGN = "six_sign"


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
    aliases: list[str] = field(default_factory=list)
    valid_joints: list[JointId] = field(default_factory=list)
    joint_limits: dict[JointId, tuple[float, float]] = field(default_factory=dict)
    has_tactile: bool = False
    tactile_regions: list[TactileRegionConfig] = field(default_factory=list)
    slave_id: int = 0x31
    modbus_profile: str = "g5"
    ethercat_input_sizes: tuple[int, ...] = field(default_factory=tuple)
    ethercat_output_size: int | None = None
    ethercat_rpdo_layout: str = "shared_mode_float"
    ethercat_tpdo_layout: str = "default"


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
                self.error_code, f"Unknown error: {self.error_code.name}"
            )
        else:
            base_msg = "Device operating normally"

        if self.state in [State.PROTECTIVE_STOPPED, State.ABNORMAL_RUNNING]:
            state_msg = _STATE_MESSAGES.get(self.state, f"Abnormal state: {self.state.name}")
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
            f"State: {self.state.name}, Error: {self.error_code.name} "
            f"({self.error_code.value}) - {msg}"
        )


@dataclass
class JointFaultInfo:
    """Fault information for an individual joint."""

    joint_id: str
    state: State
    error_code: ErrorCode

    def __str__(self):
        """Return a human-readable joint fault description."""
        return f"{self.joint_id}: State={self.state.name}, " f"Error={self.error_code.name}"


@dataclass
class HandState:
    """High-level status of the dexterous hand."""

    state: State = State.STOPPED
    error: ErrorCode = ErrorCode.NORMAL
    temperature: int = 0


@dataclass
class JointCommand:
    """Single joint command sent to the device."""

    id: int = JointId.THUMB_DIP
    angle: float = 0.0  # degrees
    speed: int = 0
    torque: int = 0


@dataclass
class JointData:
    """Single joint state received from the device."""

    id: int = JointId.THUMB_DIP
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
    ErrorCode.JOINT_CONFLICT: "Joint conflict",
    ErrorCode.TIP_CONFLICT: "Tip conflict",
    ErrorCode.LOW_TEMP: "Low temperature",
    ErrorCode.HIGH_TEMP: "High temperature",
    ErrorCode.LOW_VOLTAGE: "Low voltage",
    ErrorCode.HIGH_VOLTAGE: "High voltage",
    ErrorCode.TACTILE_ERROR: "Tactile sensor error",
    ErrorCode.PARAM_ERROR: "Parameter error",
    ErrorCode.TIMEOUT: "Timeout",
    ErrorCode.UNKNOWN_ERROR: "Unknown error",
}

_STATE_MESSAGES = {
    State.PROTECTIVE_STOPPED: "Device entered protective stop",
    State.ABNORMAL_RUNNING: "Device running abnormally",
}


