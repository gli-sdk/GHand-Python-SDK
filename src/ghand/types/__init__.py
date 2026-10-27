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

from .data import (
    JointCommand,
    DeviceData,
    HandData,
    JointData,
    TactileData,
)
from .enums import (
    HandControlMode,
    JointControlMode,
    JointLoopType,
    JointControlState,
    HandRuntimeState,
    JointState,
    HandControlState,
    CANFDBitTiming,
    CommType,
    GestureType,
    HandType,
    JointId,
    ProductType,
    RS485BaudRate,
    TactileSensorId,
)
from .errors import (
    HandCriticalError,
    HandFault,
    HandWarning,
    JointErrorCode,
    OperationResult,
    SdkError,
)

__all__ = [
    "CANFDBitTiming",
    "CommType",
    "JointLoopType",
    "HandControlMode",
    "JointControlMode",
    "DeviceData",
    "GestureType",
    "HandCriticalError",
    "HandFault",
    "HandData",
    "HandRuntimeState",
    "HandType",
    "HandWarning",
    "JointCommand",
    "JointControlState",
    "JointData",
    "JointErrorCode",
    "JointId",
    "JointState",
    "OperationResult",
    "ProductType",
    "RS485BaudRate",
    "SdkError",
    "HandControlState",
    "TactileData",
    "TactileSensorId",
]
