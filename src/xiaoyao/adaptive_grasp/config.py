import math
from dataclasses import dataclass, field
from typing import Optional

from xiaoyao.dexhand import JointId


_PASSIVE_DIP_JOINTS = {
    JointId.THUMB_DIP,
    JointId.FF_DIP,
    JointId.MF_DIP,
    JointId.RF_DIP,
    JointId.LF_DIP,
}

_ACTIVE_PRE_GRASP_JOINTS = (
    JointId.LF_MCP,
    JointId.LF_PIP,
    JointId.RF_MCP,
    JointId.RF_PIP,
    JointId.MF_MCP,
    JointId.MF_PIP,
    JointId.FF_SWING,
    JointId.FF_MCP,
    JointId.FF_PIP,
    JointId.THUMB_ROTATION,
    JointId.THUMB_SWING,
    JointId.THUMB_MCP,
    JointId.THUMB_PIP,
)

_PRE_GRASP_PRESET_DEGREE = {
    # 两指捏(食指-大拇指)
    "two_finger_pinch": {
        JointId.LF_MCP: 0.0,
        JointId.LF_PIP: 0.0,
        JointId.RF_MCP: 0.0,
        JointId.RF_PIP: 0.0,
        JointId.MF_MCP: 0.0,
        JointId.MF_PIP: 0.0,
        JointId.FF_SWING: 0.0,
        JointId.FF_MCP: 45.0,
        JointId.FF_PIP: 45.0,
        JointId.THUMB_ROTATION: 2.0,
        JointId.THUMB_SWING: 46.0,
        JointId.THUMB_MCP: 22.0,
        JointId.THUMB_PIP: 20.0,
    },
    # 三指捏(食指-中指-大拇指)
    "three_finger_pinch": {
        JointId.LF_MCP: 0.0,
        JointId.LF_PIP: 0.0,
        JointId.RF_MCP: 0.0,
        JointId.RF_PIP: 0.0,
        JointId.MF_MCP: 49.0,
        JointId.MF_PIP: 45.0,
        JointId.FF_SWING: 0.0,
        JointId.FF_MCP: 45.0,
        JointId.FF_PIP: 45.0,
        JointId.THUMB_ROTATION: 2.0,
        JointId.THUMB_SWING: 60.0,
        JointId.THUMB_MCP: 22.0,
        JointId.THUMB_PIP: 20.0,
    },
    # 五指握
    "five_finger_grasp": {
        JointId.LF_MCP: 45.0,
        JointId.LF_PIP: 30.0,
        JointId.RF_MCP: 60.0,
        JointId.RF_PIP: 25.0,
        JointId.MF_MCP: 53.0,
        JointId.MF_PIP: 30.0,
        JointId.FF_SWING: 0.0,
        JointId.FF_MCP: 45.0,
        JointId.FF_PIP: 35.0,
        JointId.THUMB_ROTATION: 2.0,
        JointId.THUMB_SWING: 60.0,
        JointId.THUMB_MCP: 2.0,
        JointId.THUMB_PIP: 21.0,
    },
}


@dataclass
class AdaptiveGraspConfig:
    pre_grasp_pose: dict[JointId, float] = field(default_factory=dict)
    pre_grasp_preset: str = "three_finger_pinch"

    base_torque: int = 10
    contact_threshold_z: float = 0.5
    sliding_window_size: int = 10
    torque_adjust_step: int = 5
    max_torque: int = 50
    phase_timeout: float = 10.0
    control_period_s: float = 0.005

    stiffness: float = 0.5
    max_normal_force_per_finger: Optional[float] = None
    variance_threshold: Optional[float] = None

    enable_phase4_ext: bool = False
    load_gain: float = 1.0
    ext_smoothing_alpha: float = 0.4
    ext_safety_margin_ratio: float = 0.9

    def __post_init__(self) -> None:
        if not 0.0 <= self.stiffness <= 1.0:
            raise ValueError("stiffness must be in [0.0, 1.0]")
        if not 0.0 <= self.ext_smoothing_alpha <= 1.0:
            raise ValueError("ext_smoothing_alpha must be in [0.0, 1.0]")
        if not 0.0 < self.ext_safety_margin_ratio <= 1.0:
            raise ValueError("ext_safety_margin_ratio must be in (0.0, 1.0]")
        if self.sliding_window_size < 3:
            raise ValueError("sliding_window_size must be >= 3")
        if self.control_period_s <= 0:
            raise ValueError("control_period_s must be > 0")
        if self.max_torque <= 0:
            raise ValueError("max_torque must be > 0")
        if self.phase_timeout <= 0:
            raise ValueError("phase_timeout must be > 0")
        if self.torque_adjust_step <= 0:
            raise ValueError("torque_adjust_step must be > 0")
        if self.load_gain <= 0:
            raise ValueError("load_gain must be > 0")

        if self.max_normal_force_per_finger is None:
            self.max_normal_force_per_finger = 0.1 + 2.9 * self.stiffness
        if self.variance_threshold is None:
            self.variance_threshold = 0.05 + 0.15 * self.stiffness

        if self.max_normal_force_per_finger <= 0:
            raise ValueError("max_normal_force_per_finger must be > 0")
        if self.variance_threshold < 0:
            raise ValueError("variance_threshold must be >= 0")

        if self.pre_grasp_pose:
            filtered = self._filter_passive_dip_joints(self.pre_grasp_pose)
            self.pre_grasp_pose = filtered if filtered else self._build_pre_grasp_pose_from_preset()
        else:
            self.pre_grasp_pose = self._build_pre_grasp_pose_from_preset()

    def _build_pre_grasp_pose_from_preset(self) -> dict[JointId, float]:
        if self.pre_grasp_preset not in _PRE_GRASP_PRESET_DEGREE:
            supported = ", ".join(sorted(_PRE_GRASP_PRESET_DEGREE.keys()))
            raise ValueError(f"pre_grasp_preset must be one of: {supported}")

        # 预设表按角度维护，统一在这里转换成弧度，避免单位混用。
        degrees_map = _PRE_GRASP_PRESET_DEGREE[self.pre_grasp_preset]
        pose: dict[JointId, float] = {}
        for joint_id in _ACTIVE_PRE_GRASP_JOINTS:
            pose[joint_id] = math.radians(degrees_map.get(joint_id, 0.0))
        return pose

    @staticmethod
    def _filter_passive_dip_joints(
        pose: dict[JointId, float],
    ) -> dict[JointId, float]:
        return {
            joint_id: angle
            for joint_id, angle in pose.items()
            if joint_id not in _PASSIVE_DIP_JOINTS
        }
