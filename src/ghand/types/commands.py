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

"""Command dataclasses sent to the device."""

from dataclasses import dataclass

from .enums import JointId
from .states import CtrlMode, JointControlState


@dataclass
class JointCommand:
    """Single joint command sent to the device."""

    id: int = JointId.THUMB_IP
    mode: CtrlMode | None = None
    stop: JointControlState | int = JointControlState.RUNNING
    angle: float = 0.0  # degrees
    speed: int = 0
    current: int = 0
    kp: int = 0
    kd: int = 0
