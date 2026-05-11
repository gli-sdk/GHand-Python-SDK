import math
from typing import Mapping, Optional

from xiaoyao.dexhand import Joint, JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .utils import clip


TORQUE_CONTROL_JOINTS = (
    JointId.THUMB_PIP, JointId.THUMB_MCP,
    JointId.FF_PIP, JointId.FF_MCP,
    JointId.MF_PIP, JointId.MF_MCP,
    JointId.RF_PIP, JointId.RF_MCP,
    JointId.LF_PIP, JointId.LF_MCP,
)

FINGER_TORQUE_JOINTS = {
    TactileSensorId.THUMB: (JointId.THUMB_MCP, JointId.THUMB_PIP),
    TactileSensorId.FOREFINGER: (JointId.FF_MCP, JointId.FF_PIP),
    TactileSensorId.MIDDLE_FINGER: (JointId.MF_MCP, JointId.MF_PIP),
    TactileSensorId.RING_FINGER: (JointId.RF_MCP, JointId.RF_PIP),
    TactileSensorId.LITTLE_FINGER: (JointId.LF_MCP, JointId.LF_PIP),
}


class JointCommandBuilder:
    _TORQUE_JOINTS = TORQUE_CONTROL_JOINTS

    def __init__(self, config: AdaptiveGraspConfig, torque_joints: tuple[JointId, ...]):
        self._config = config
        self._torque_joints = torque_joints

    @property
    def torque_joints(self) -> tuple[JointId, ...]:
        return self._torque_joints

    def open_pose(self) -> dict[JointId, float]:
        return {
            JointId.THUMB_PIP: math.radians(0),
            JointId.THUMB_MCP: math.radians(0),
            JointId.THUMB_SWING: math.radians(20),
            JointId.THUMB_ROTATION: math.radians(0),
            JointId.FF_PIP: math.radians(0),
            JointId.FF_MCP: math.radians(0),
            JointId.FF_SWING: math.radians(0),
            JointId.MF_PIP: math.radians(0),
            JointId.MF_MCP: math.radians(0),
            JointId.RF_PIP: math.radians(0),
            JointId.RF_MCP: math.radians(0),
            JointId.LF_PIP: math.radians(0),
            JointId.LF_MCP: math.radians(0),
        }

    def init_hold_angles(self) -> dict[JointId, float]:
        return {
            joint_id: self._config.pre_grasp_pose.get(joint_id, 0.0)
            for joint_id in self._torque_joints
        }

    def position_command(self, angles: dict[JointId, float], speed: int, torque: int) -> list[Joint]:
        return [
            Joint(id=joint_id, angle=angle, speed=speed, torque=torque)
            for joint_id, angle in angles.items()
        ]

    def torque_command(self, torque: int, thumb_torque: Optional[int] = None) -> list[Joint]:
        thumb_aux_torque = self._config.thumb_aux_torque if thumb_torque is None else thumb_torque
        active = set(self._torque_joints)
        joints = [
            Joint(id=joint_id, torque=torque)
            if joint_id in active
            else Joint(id=joint_id, angle=0.0, speed=0, torque=0)
            for joint_id in TORQUE_CONTROL_JOINTS
        ]
        joints += [
            Joint(id=JointId.THUMB_ROTATION, angle=0.0, speed=0, torque=thumb_aux_torque),
            Joint(id=JointId.THUMB_SWING, angle=0.0, speed=0, torque=thumb_aux_torque),
        ]
        return joints

    def hold_torque_command(self, torque: int) -> list[Joint]:
        return self.torque_command(torque)

    def hold_per_finger_torque_command(
        self,
        finger_torques: Mapping[TactileSensorId, float],
    ) -> list[Joint]:
        active_joints = set(self._torque_joints)
        joint_torques: dict[JointId, int] = {}

        for finger, torque in finger_torques.items():
            for joint_id in FINGER_TORQUE_JOINTS.get(finger, ()):
                if joint_id in active_joints:
                    joint_torques[joint_id] = round(
                        clip(torque, -100.0, self._config.max_torque)
                    )

        joints = [
            Joint(id=joint_id, torque=joint_torques[joint_id])
            if joint_id in joint_torques
            else Joint(id=joint_id, angle=0.0, speed=0, torque=0)
            for joint_id in TORQUE_CONTROL_JOINTS
        ]
        joints += [
            Joint(id=JointId.THUMB_ROTATION, angle=0.0, speed=0, torque=self._config.thumb_aux_torque),
            Joint(id=JointId.THUMB_SWING, angle=0.0, speed=0, torque=self._config.thumb_aux_torque),
        ]
        return joints

    def hold_position_command(
        self,
        torque: int,
        angles: Optional[Mapping[JointId, float]] = None,
        speed: Optional[int] = None,
    ) -> list[Joint]:
        limited_torque = int(clip(abs(torque), 0.0, float(self._config.position_torque_limit)))
        limited_speed = int(clip(
            self._config.position_speed_limit if speed is None else speed,
            0.0,
            100.0,
        ))
        hold_angles = angles or self.init_hold_angles()
        return [
            Joint(
                id=joint_id,
                angle=hold_angles.get(joint_id, 0.0),
                speed=limited_speed,
                torque=limited_torque,
            )
            for joint_id in self._torque_joints
        ]
