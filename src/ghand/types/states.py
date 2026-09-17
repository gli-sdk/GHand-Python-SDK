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

"""Device state and control-mode enums."""

import enum

from .enums import DeviceCode, unknown_member


class CtrlMode(enum.Enum):
    POSITION = 0
    SPEED = 1
    CURRENT = 2
    MIT = 3
    CUSTOM = 0x0F


class JointControlState(enum.IntEnum):
    """Per-joint control state sent to the device."""

    DISABLED = 0
    RUNNING = 1
    STOPPED = 2


class State(DeviceCode):
    DISABLED = 0
    ENABLED = 1
    UNKNOWN_STATE = 255

    @classmethod
    def _missing_(cls, value):
        """Map any undefined state to UNKNOWN_STATE, keeping the raw value."""
        return unknown_member(cls, cls.UNKNOWN_STATE, value)

    @property
    def is_abnormal(self) -> bool:
        """True for values outside the defined hand states."""
        return self not in (State.DISABLED, State.ENABLED)


class HandType(enum.Enum):
    NONE = "none"
    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"


class JointState(DeviceCode):
    DISABLED = 0
    RUNNING = 1
    STOPPED = 2
    FAULT = 3
    UNKNOWN_STATE = 255

    @classmethod
    def _missing_(cls, value):
        """Map any undefined joint state to UNKNOWN_STATE, keeping the raw value."""
        return unknown_member(cls, cls.UNKNOWN_STATE, value)

    @property
    def is_abnormal(self) -> bool:
        """True for fault or any undefined joint state."""
        return self not in (
            JointState.DISABLED,
            JointState.RUNNING,
            JointState.STOPPED,
        )
