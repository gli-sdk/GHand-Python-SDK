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
from .errors import JointErrorCode
from .states import JointState, State


@dataclass
class HandState:
    """High-level status of the dexterous hand."""

    state: State = State.STOPPED
    error_warn: bytes = b"\x00" * 6
    error_fault: bytes = b"\x00" * 6
    error_critical: bytes = b"\x00" * 6
    temperature: int = 0

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


@dataclass
class TactileData:
    """Tactile sensor reading for a single finger."""

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
}


_HAND_FAULT_MESSAGES = {
    (0, 0): "Joint motor fault - Thumb2",
    (0, 1): "Joint motor fault - Thumb3",
    (0, 2): "Joint motor fault - Thumb4",
    (0, 3): "Joint motor fault - Thumb5",
    (0, 4): "Joint motor fault - FF2",
    (0, 5): "Joint motor fault - FF3",
    (0, 6): "Joint motor fault - FF4",
    (0, 7): "Joint motor fault - MF2",
    (1, 0): "Joint motor fault - MF3",
    (1, 1): "Joint motor fault - RF2",
    (1, 2): "Joint motor fault - RF3",
    (1, 3): "Joint motor fault - LF2",
    (1, 4): "Joint motor fault - LF3",
    (1, 5): "Thumb tactile sensor abnormal",
    (1, 6): "Index finger tactile sensor abnormal",
    (1, 7): "Middle finger tactile sensor abnormal",
    (2, 0): "Ring finger tactile sensor abnormal",
    (2, 1): "Little finger tactile sensor abnormal",
    (2, 2): "Position sensor abnormal - Thumb2",
    (2, 3): "Position sensor abnormal - Thumb3",
    (2, 4): "Position sensor abnormal - Thumb4",
    (2, 5): "Position sensor abnormal - Thumb5",
    (2, 6): "Position sensor abnormal - FF2",
    (2, 7): "Position sensor abnormal - FF3",
    (3, 0): "Position sensor abnormal - FF4",
    (3, 1): "Position sensor abnormal - MF2",
    (3, 2): "Position sensor abnormal - MF3",
    (3, 3): "Position sensor abnormal - RF2",
    (3, 4): "Position sensor abnormal - RF3",
    (3, 5): "Position sensor abnormal - LF2",
    (3, 6): "Position sensor abnormal - LF3",
    (3, 7): "Position sensor uncalibrated - Thumb2",
    (4, 0): "Position sensor uncalibrated - Thumb3",
    (4, 1): "Position sensor uncalibrated - Thumb4",
    (4, 2): "Position sensor uncalibrated - Thumb5",
    (4, 3): "Position sensor uncalibrated - FF2",
    (4, 4): "Position sensor uncalibrated - FF3",
    (4, 5): "Position sensor uncalibrated - FF4",
    (4, 6): "Position sensor uncalibrated - MF2",
    (4, 7): "Position sensor uncalibrated - MF3",
    (5, 0): "Position sensor uncalibrated - RF2",
    (5, 1): "Position sensor uncalibrated - RF3",
    (5, 2): "Position sensor uncalibrated - LF2",
    (5, 3): "Position sensor uncalibrated - LF3",
}


_HAND_CRITICAL_MESSAGES = {
    (0, 0): "Unknown error",
    (0, 1): "Self-test error",
    (0, 2): "Position sensor version mismatch",
    (0, 3): "Tactile sensor version mismatch",
    (0, 4): "Motor driver version mismatch",
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
