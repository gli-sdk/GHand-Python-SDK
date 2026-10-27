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

"""Command and feedback dataclasses and error-bit descriptions."""

from dataclasses import dataclass

from .enums import (
    JointControlMode, JointLoopType, JointControlState, JointId, JointState,
    HandControlState, TactileSensorId,
)
from .errors import HandCriticalError, HandFault, HandWarning, JointErrorCode


@dataclass
class JointCommand:
    """Single joint command sent to the device."""

    id: int = JointId.THUMB_IP
    control_mode: JointControlMode = JointControlMode.POSITION
    loop_type: JointLoopType = JointLoopType.CLOSED_LOOP  # Effective in hand CUSTOM mode.
    control_state: JointControlState = JointControlState.DISABLED
    angle: float = 0.0  # degrees
    speed: int = 0
    current: int = 0
    kp: int = 0
    kd: int = 0


@dataclass(frozen=True)
class HandFaultData:
    """Complete hand fault bitfield, including per-channel and reserved bits."""

    value: int = 0

    def __bool__(self) -> bool:
        return bool(self.value)

    @property
    def categories(self) -> HandFault:
        """Return categories that contain at least one active fault."""
        raw = self.value
        categories = HandFault.NONE
        for category, _, _, _ in _HAND_FAULT_LAYOUT:
            if raw & category:
                categories |= category
        return categories

    def indices(self, category: HandFault) -> list[int]:
        """Return active 0-based channel indices for one fault category."""
        try:
            offset = next(
                offset
                for candidate, offset, _, _ in _HAND_FAULT_LAYOUT
                if candidate == category
            )
        except StopIteration as exc:
            raise ValueError("category must be one HandFault member") from exc

        bits = (self.value >> offset)
        bits &= _HAND_FAULT_CHANNEL_MASK
        return [index for index in range(13) if bits & (1 << index)]


@dataclass
class HandData:
    """High-level status of the dexterous hand."""

    joints_state: HandControlState = HandControlState.DISABLED
    error_warn: HandWarning = HandWarning.NONE
    error_fault: HandFaultData = HandFaultData()
    error_critical: HandCriticalError = HandCriticalError.NONE
    temperature: int = 0

    @property
    def warnings(self) -> HandWarning:
        """Return the warning bitfield as a typed flag set."""
        return self.error_warn

    @property
    def faults(self) -> HandFault:
        """Return categories that contain at least one active fault."""
        return self.error_fault.categories

    def fault_indices(self, category: HandFault) -> list[int]:
        """Return active 0-based channel indices for one fault category."""
        return self.error_fault.indices(category)

    @property
    def critical_errors(self) -> HandCriticalError:
        """Return the critical-error bitfield as a typed flag set."""
        return self.error_critical

    def active_errors(self) -> list[tuple[str, int, int, str]]:
        """Return active hand-level warn/fault/critical bit descriptions."""
        return describe_hand_state_errors(self)


@dataclass
class JointData:
    """Single joint state received from the device."""

    id: int = JointId.THUMB_IP
    state: JointState = JointState.DISABLED
    error: JointErrorCode = JointErrorCode.NORMAL
    control_mode: JointControlMode = JointControlMode.POSITION
    loop_type: JointLoopType = JointLoopType.CLOSED_LOOP  
    angle: float = 0.0  # degrees
    speed: int = 0
    current: int = 0

@dataclass
class TactileData:
    """Tactile sensor reading for a single finger, with forces in Newtons."""

    state: bool = False
    resultant_force: list[float] | None = None
    distributed_force: list[float] | None = None


@dataclass
class DeviceData:
    """Unified data carrier for subscription callbacks across all protocols."""

    hand: HandData
    joints: list[JointData]
    tactile: dict[TactileSensorId, TactileData] | None = None
    timestamp: float | None = None

    def __post_init__(self):
        for joint in self.joints:
            jid = JointId(joint.id)
            setattr(self, jid.name.lower(), joint)


_ACTIVE_JOINT_NAMES = (
    "Thumb2",
    "Thumb3",
    "Thumb4",
    "Thumb5",
    "FF2",
    "FF3",
    "FF4",
    "MF2",
    "MF3",
    "RF2",
    "RF3",
    "LF2",
    "LF3",
)


_HAND_FAULT_CHANNEL_MASK = (1 << 13) - 1
_HAND_FAULT_LAYOUT = (
    (HandFault.JOINT_MOTOR, 0, "Joint motor fault", _ACTIVE_JOINT_NAMES),
    (
        HandFault.POSITION_SENSOR_ABNORMAL,
        13,
        "Position sensor abnormal",
        _ACTIVE_JOINT_NAMES,
    ),
    (
        HandFault.POSITION_SENSOR_UNCALIBRATED,
        26,
        "Position sensor uncalibrated",
        _ACTIVE_JOINT_NAMES,
    ),
    (HandFault.ZEROING_JOINT_STALL, 39, "Zeroing joint stalled", _ACTIVE_JOINT_NAMES),
    (HandFault.ZEROING_BRAKE_TIMEOUT, 52, "Zeroing brake timeout", _ACTIVE_JOINT_NAMES),
    (
        HandFault.ZEROING_MOTOR_COMMUNICATION,
        65,
        "Zeroing motor communication fault",
        tuple(f"Motor{index}" for index in range(13)),
    ),
)


_HAND_FAULT_MESSAGES = {
    divmod(offset + index, 8): f"{message} - {name}"
    for _, offset, message, names in _HAND_FAULT_LAYOUT
    for index, name in enumerate(names)
}


def describe_hand_state_errors(hand_state: HandData) -> list[tuple[str, int, int, str]]:
    """Decode active hand-level error bitfields."""
    decoded: list[tuple[str, int, int, str]] = []
    groups = (
        ("warn", hand_state.error_warn.to_bytes(6, "little"), {
            divmod(warning.value.bit_length() - 1, 8): warning.name
            for warning in HandWarning
        }),
        ("fault", hand_state.error_fault.value.to_bytes(12, "little"), _HAND_FAULT_MESSAGES),
        ("critical", hand_state.error_critical.to_bytes(6, "little"), {
            divmod(error.value.bit_length() - 1, 8): error.name
            for error in HandCriticalError
        }),
    )
    for level, data, messages in groups:
        for byte_index, value in enumerate(data):
            for bit_index in range(8):
                if value & (1 << bit_index):
                    decoded.append(
                        (
                            level,
                            byte_index,
                            bit_index,
                            messages.get((byte_index, bit_index), "Reserved"),
                        )
                    )
    return decoded
