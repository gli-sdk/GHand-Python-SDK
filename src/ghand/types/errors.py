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

"""Device error codes, diagnostic results, and SDK errors."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from enum import Enum

from .enums import CommType


class JointErrorCode(enum.IntEnum):
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
    SELF_TEST_ERROR = 1 << 9


class HandFault(enum.IntFlag):
    """Protocol masks for the six 13-channel hand fault groups."""

    NONE = 0
    JOINT_MOTOR = ((1 << 13) - 1) << 0  # byte0:bit0 .. byte1:bit4
    POSITION_SENSOR_ABNORMAL = ((1 << 13) - 1) << 13  # byte1:bit5 .. byte3:bit1
    POSITION_SENSOR_UNCALIBRATED = ((1 << 13) - 1) << 26  # byte3:bit2 .. byte4:bit6
    ZEROING_JOINT_STALL = ((1 << 13) - 1) << 39  # byte4:bit7 .. byte6:bit3
    ZEROING_BRAKE_TIMEOUT = ((1 << 13) - 1) << 52  # byte6:bit4 .. byte8:bit0
    ZEROING_MOTOR_COMMUNICATION = ((1 << 13) - 1) << 65  # byte8:bit1 .. byte9:bit5


class HandCriticalError(enum.IntFlag):
    """Hand-level critical-error bits from the EtherCAT V2.1 TPDO."""

    NONE = 0
    UNKNOWN_ERROR = 1 << 0
    POSITION_SENSOR_VERSION_MISMATCH = 1 << 2
    TACTILE_SENSOR_VERSION_MISMATCH = 1 << 3
    MOTOR_DRIVER_VERSION_MISMATCH = 1 << 4
    POSITION_BOARD_DETECTION_ABNORMAL = 1 << 5
    TEMPERATURE_TOO_HIGH = 1 << 6
    TEMPERATURE_TOO_LOW = 1 << 7
    ZEROING_GLOBAL_TIMEOUT = 1 << 8


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
