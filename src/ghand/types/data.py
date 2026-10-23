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

"""Device feedback dataclasses and error-bit descriptions."""

from dataclasses import dataclass

from .enums import JointId, TactileSensorId
from .errors import HandCriticalError, HandFault, HandWarning, JointErrorCode
from .states import ClosedLoopType, CtrlMode, JointState, State


@dataclass
class HandState:
    """High-level status of the dexterous hand."""

    state: State = State.DISABLED
    error_warn: bytes = b"\x00" * 6
    error_fault: bytes = b"\x00" * 12
    error_critical: bytes = b"\x00" * 6
    temperature: int = 0

    @property
    def warnings(self) -> HandWarning:
        """Return the warning bitfield as a typed flag set."""
        return HandWarning(int.from_bytes(self.error_warn, "little"))

    @property
    def faults(self) -> HandFault:
        """Return categories that contain at least one active fault."""
        raw = int.from_bytes(self.error_fault, "little")
        categories = HandFault.NONE
        for category, offset, _, _ in _HAND_FAULT_LAYOUT:
            if raw & (_HAND_FAULT_CHANNEL_MASK << offset):
                categories |= category
        return categories

    def fault_indices(self, category: HandFault) -> list[int]:
        """Return active 0-based channel indices for one fault category."""
        try:
            offset = next(
                offset
                for candidate, offset, _, _ in _HAND_FAULT_LAYOUT
                if candidate == category
            )
        except StopIteration as exc:
            raise ValueError("category must be one HandFault member") from exc

        bits = (int.from_bytes(self.error_fault, "little") >> offset)
        bits &= _HAND_FAULT_CHANNEL_MASK
        return [index for index in range(13) if bits & (1 << index)]

    @property
    def critical_errors(self) -> HandCriticalError:
        """Return the critical-error bitfield as a typed flag set."""
        return HandCriticalError(int.from_bytes(self.error_critical, "little"))

    def active_errors(self) -> list[tuple[str, int, int, str]]:
        """Return active hand-level warn/fault/critical bit descriptions."""
        return describe_hand_state_errors(self)


@dataclass
class JointData:
    """Single joint state received from the device."""

    id: int = JointId.THUMB_IP
    state: JointState = JointState.DISABLED
    error: JointErrorCode = JointErrorCode.NORMAL
    mode: int = 0
    stop: int = 0
    angle: float = 0.0  # degrees
    speed: int = 0
    current: int = 0

    @property
    def control_mode(self) -> CtrlMode | None:
        """Return the control mode encoded in bits 0..3 of ``mode``."""
        try:
            return CtrlMode(self.mode & 0x0F)
        except ValueError:
            return None

    @property
    def closed_loop_type(self) -> ClosedLoopType:
        """Return the feedback loop type encoded in bits 4..7 of ``mode``."""
        return ClosedLoopType((self.mode >> 4) & 0x0F)


@dataclass
class TactileData:
    """Tactile sensor reading for a single finger, with forces in Newtons."""

    state: bool = False
    resultant_force: list[float] | None = None
    distributed_force: list[float] | None = None


@dataclass
class DeviceData:
    """Unified data carrier for subscription callbacks across all protocols."""

    hand: HandState
    joints: list[JointData]
    tactile: dict[TactileSensorId, TactileData] | None = None
    timestamp: float | None = None

    def __post_init__(self):
        for joint in self.joints:
            jid = JointId(joint.id)
            setattr(self, jid.name.lower(), joint)


_HAND_WARN_MESSAGES = {
    (0, 0): "Temperature sensor 1 abnormal",
    (0, 1): "Temperature sensor 2 abnormal",
    (0, 2): "Fan abnormal",
    (0, 3): "Tactile board communication abnormal",
    (0, 4): "Thumb tactile sensor disconnected",
    (0, 5): "Forefinger tactile sensor disconnected",
    (0, 6): "Middle finger tactile sensor disconnected",
    (0, 7): "Ring finger tactile sensor disconnected",
    (1, 0): "Little finger tactile sensor disconnected",
    (1, 1): "Self-test error",
}


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


_HAND_CRITICAL_MESSAGES = {
    (0, 0): "Unknown error",
    (0, 2): "Position sensor version mismatch",
    (0, 3): "Tactile sensor version mismatch",
    (0, 4): "Motor driver version mismatch",
    (0, 5): "Position board detection abnormal",
    (0, 6): "Temperature too high",
    (0, 7): "Temperature too low",
    (1, 0): "Zeroing global timeout",
}


def describe_hand_state_errors(hand_state: HandState) -> list[tuple[str, int, int, str]]:
    """Decode active hand-level error bitfields."""
    decoded: list[tuple[str, int, int, str]] = []
    groups = (
        ("warn", hand_state.error_warn, _HAND_WARN_MESSAGES),
        ("fault", hand_state.error_fault, _HAND_FAULT_MESSAGES),
        ("critical", hand_state.error_critical, _HAND_CRITICAL_MESSAGES),
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
