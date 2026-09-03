# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

from typing import Mapping, Optional

from ..types import JointCommand, JointId
from .config import AdaptiveGraspConfig
from .utils import clip


CURRENT_CONTROL_JOINTS = (
    JointId.THUMB_MCP, JointId.THUMB_TMC_FE,
    JointId.FF_PIP, JointId.FF_MCP,
    JointId.MF_PIP, JointId.MF_MCP,
    JointId.RF_PIP, JointId.RF_MCP,
    JointId.LF_PIP, JointId.LF_MCP,
)

class JointCommandBuilder:
    _current_joints = CURRENT_CONTROL_JOINTS

    def __init__(self, config: AdaptiveGraspConfig, current_joints: tuple[JointId, ...]):
        self._config = config
        self._current_joints = current_joints

    @property
    def current_joints(self) -> tuple[JointId, ...]:
        return self._current_joints

    def open_pose(self) -> dict[JointId, float]:
        return {
            JointId.THUMB_MCP: 0.0,
            JointId.THUMB_TMC_FE: 0.0,
            JointId.THUMB_TMC_AA: 80.0,
            JointId.THUMB_TMC_PS: 0.0,
            JointId.FF_PIP: 0.0,
            JointId.FF_MCP: 0.0,
            JointId.FF_MCP_AA: 0.0,
            JointId.MF_PIP: 0.0,
            JointId.MF_MCP: 0.0,
            JointId.RF_PIP: 0.0,
            JointId.RF_MCP: 0.0,
            JointId.LF_PIP: 0.0,
            JointId.LF_MCP: 0.0,
        }

    def init_hold_angles(self) -> dict[JointId, float]:
        return {
            joint_id: self._config.pre_grasp_pose.get(joint_id, 0.0)
            for joint_id in self._current_joints
        }

    def position_command(self, angles: dict[JointId, float], speed: int, current: int) -> list[JointCommand]:
        return [
            JointCommand(id=joint_id, angle=angle, speed=speed, current=current)
            for joint_id, angle in angles.items()
        ]

    def current_command(self, current: int, thumb_current: Optional[int] = None) -> list[JointCommand]:
        thumb_aux_current = self._config.thumb_aux_current if thumb_current is None else thumb_current
        active = set(self._current_joints)
        joints = [
            JointCommand(id=joint_id, current=current)
            if joint_id in active
            else JointCommand(id=joint_id, angle=0.0, speed=0, current=0)
            for joint_id in CURRENT_CONTROL_JOINTS
        ]
        joints += [
            JointCommand(id=JointId.THUMB_TMC_PS, angle=0.0, speed=0, current=thumb_aux_current),
            JointCommand(id=JointId.THUMB_TMC_AA, angle=20.0, speed=0, current=thumb_aux_current),
        ]
        return joints

    def hold_position_command(
        self,
        current: int,
        angles: Optional[Mapping[JointId, float]] = None,
        speed: Optional[int] = None,
    ) -> list[JointCommand]:
        limited_current = int(clip(abs(current), 0.0, float(self._config.max_current)))
        limited_speed = int(clip(0 if speed is None else speed, 0.0, 100.0))
        hold_angles = angles or self.init_hold_angles()
        return [
            JointCommand(
                id=joint_id,
                angle=hold_angles.get(joint_id, 0.0),
                speed=limited_speed,
                current=limited_current,
            )
            for joint_id in self._current_joints
        ]
