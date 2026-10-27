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

"""Command and feedback dataclasses."""

from dataclasses import dataclass

from .enums import (
    JointControlMode, JointLoopType, JointControlState, JointId, JointState,
    HandControlState, TactileSensorId,
)
from .errors import HandCriticalError, HandFault, HandWarning, JointErrorCode


@dataclass
class JointCommand:
    """Single joint command sent to the device."""

    id: int = JointId.THUMB_IP  # Target joint ID; see JointId.
    control_mode: JointControlMode = JointControlMode.POSITION  # Joint control mode.
    loop_type: JointLoopType = JointLoopType.CLOSED_LOOP  # Only effective in hand CUSTOM mode.
    control_state: JointControlState = JointControlState.DISABLED  # Disable, run, or stop and hold the joint.
    angle: float = 0.0  # Target angle in degrees; see the corresponding product JSON in src/ghand/config/ for joint limits.
    velocity: int = 0  # Target velocity (%), range: -100 to 100; recommended magnitude <= 5% in MIT mode.
    current: int = 0  # Target current (%), range: -100 to 100; recommended magnitude <= 20% in MIT mode.
    kp: int = 0  # MIT position gain; explicitly set to 10-2000 in MIT mode; must be greater than kd.
    kd: int = 0  # MIT damping gain, range: 0-50; must be less than kp.


@dataclass
class HandData:
    """High-level status of the dexterous hand."""

    joints_state: HandControlState = HandControlState.DISABLED  # Overall joint enable state.
    error_warn: HandWarning = HandWarning.NONE  # Warning flags; the hand remains usable.
    error_fault: HandFault = HandFault.NONE  # Fault flags; only the affected finger cannot move; other fingers remain usable.
    error_critical: HandCriticalError = HandCriticalError.NONE  # Critical error flags; the entire hand is unusable until all faults are cleared.
    temperature: int = 0  # Hand temperature in degrees Celsius.


@dataclass
class JointData:
    """Single joint state received from the device."""

    id: int = JointId.THUMB_IP  # Joint ID; see JointId.
    state: JointState = JointState.DISABLED  # Reported joint operating state; see JointState.
    error: JointErrorCode = JointErrorCode.NORMAL  # Reported joint error code; see JointErrorCode.
    control_mode: JointControlMode = JointControlMode.POSITION  # Reported joint control mode.
    loop_type: JointLoopType = JointLoopType.CLOSED_LOOP  # Reported joint feedback loop type.
    angle: float = 0.0  # Measured angle in degrees; see the corresponding product JSON in src/ghand/config/ for joint limits.
    velocity: int = 0  # Reported velocity (%), range: -100 to 100.
    current: int = 0  # Reported current (%), range: -100 to 100.


@dataclass
class TactileData:
    """Tactile sensor reading for a single finger, with forces in Newtons."""

    state: bool = False  # Reported tactile sensor status.
    # Resultant [Fx, Fy, Fz] in sensor X/Y/Z directions, in Newtons; None if unavailable.
    # Protocol ranges: Fx/Fy -10 to 10 N; Fz 0 to 25 N; resolution 0.1 N.
    resultant_force: list[float] | None = None
    # Per-point [Fx0, Fy0, Fz0, Fx1, Fy1, Fz1, ...] in sensor X/Y/Z directions, in Newtons.
    # Per-point ranges: Fx/Fy -10 to 10 N; Fz 0 to 25 N; resolution 0.1 N.
    # Point counts: see tactile_regions[].count in the corresponding product JSON in src/ghand/config/.
    distributed_force: list[float] | None = None  # None if unavailable.


@dataclass
class DeviceData:
    """Unified data carrier for subscription callbacks across all protocols."""

    hand: HandData  # Overall hand status, including errors and temperature.
    joints: list[JointData]  # Joint feedback entries; each entry identifies its joint by ID.
    tactile: dict[TactileSensorId, TactileData] | None = None  # Tactile readings keyed by sensor ID; None if unavailable or not included.
    timestamp: float | None = None  # Timestamp associated with this update; None if not provided.
