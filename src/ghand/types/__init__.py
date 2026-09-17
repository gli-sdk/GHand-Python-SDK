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

"""Public SDK types, available directly from ``ghand.types``."""

from .commands import JointCommand
from .config import (
    ProductConfig,
    TactileRegionConfig,
)
from .data import (
    DeviceData,
    HandState,
    JointData,
    TactileData,
    describe_hand_state_errors,
)
from .enums import (
    CANFDBitTiming,
    CommType,
    DeviceCode,
    GestureType,
    JointId,
    ProductType,
    RS485BaudRate,
    TactileSensorId,
)
from .errors import (
    CommunicationError,
    ErrorCode,
    GHandError,
    HandCriticalError,
    HandFault,
    HandStateError,
    HandWarning,
    JointErrorCode,
    MotorCheckError,
    MotorDiagnosticError,
    OperationResult,
    SdkError,
    SelfTestError,
    SelfTestErrorInfo,
    TactileCheckError,
    VersionCheckError,
    ZeroingError,
)
from .states import (
    CtrlMode,
    HandType,
    JointControlState,
    JointState,
    State,
)

__all__ = [
    "CANFDBitTiming",
    "CommType",
    "CommunicationError",
    "CtrlMode",
    "DeviceCode",
    "DeviceData",
    "ErrorCode",
    "GHandError",
    "GestureType",
    "HandCriticalError",
    "HandFault",
    "HandState",
    "HandStateError",
    "HandType",
    "HandWarning",
    "JointCommand",
    "JointControlState",
    "JointData",
    "JointErrorCode",
    "JointId",
    "JointState",
    "MotorCheckError",
    "MotorDiagnosticError",
    "OperationResult",
    "ProductConfig",
    "ProductType",
    "RS485BaudRate",
    "SdkError",
    "SelfTestError",
    "SelfTestErrorInfo",
    "State",
    "TactileCheckError",
    "TactileData",
    "TactileRegionConfig",
    "TactileSensorId",
    "VersionCheckError",
    "ZeroingError",
    "describe_hand_state_errors",
]
