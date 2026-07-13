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

from __future__ import annotations

from typing import Optional

import numpy as np

from .types import JointCommand, JointData, JointId


class JointConverter:
    """Convert between joint objects and numpy arrays."""

    @staticmethod
    def joints_to_nparray(
        joints: list[JointCommand | JointData],
        current_joints: Optional[list[JointData]] = None,
    ) -> np.ndarray:
        """Convert a list of JointCommand or JointData to an 18-dimensional numpy array.

        Unspecified joints are filled from ``current_joints`` if provided,
        otherwise default to 0.0.

        Args:
            joints: List of JointCommand objects to convert.
            current_joints: Optional list of current JointData states used for filling
                unspecified joints.

        Returns:
            An 18-element numpy array of joint angles in degrees.
        """
        angles = np.zeros(18, dtype=float)
        if current_joints is not None:
            for j in current_joints:
                angles[int(j.id)] = float(j.angle)
        for j in joints:
            angles[int(j.id)] = float(j.angle)
        return angles

    @staticmethod
    def nparray_to_joints(
        angles: np.ndarray, speed: int = 100, torque: int = 100
    ) -> list[JointCommand]:
        """Convert an 18-dimensional numpy array back to a list of JointCommand objects.

        The returned list uses ids 0-17, matching the ``ghand.JointId``
        enumeration order.

        Args:
            angles: 18-element numpy array of joint angles in degrees.
            speed: Speed percentage (0-100) applied to all joints. Defaults to 100.
            torque: Torque percentage (0-100) applied to all joints. Defaults to 100.

        Returns:
            List of 18 JointCommand objects.
        """
        return [
            JointCommand(id=JointId(i), angle=float(angles[i]), speed=speed, torque=torque)
            for i in range(18)
        ]


joints_to_nparray = JointConverter.joints_to_nparray
nparray_to_joints = JointConverter.nparray_to_joints
