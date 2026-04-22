import math
from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .tactile import TactileAnalysis


_G = 9.8

_JOINT_TO_FINGER: dict[JointId, TactileSensorId] = {
    JointId.THUMB_MCP: TactileSensorId.THUMB,
    JointId.THUMB_PIP: TactileSensorId.THUMB,
    JointId.FF_MCP: TactileSensorId.FOREFINGER,
    JointId.FF_PIP: TactileSensorId.FOREFINGER,
    JointId.FF_SWING: TactileSensorId.FOREFINGER,
    JointId.MF_MCP: TactileSensorId.MIDDLE_FINGER,
    JointId.MF_PIP: TactileSensorId.MIDDLE_FINGER,
    JointId.RF_MCP: TactileSensorId.RING_FINGER,
    JointId.RF_PIP: TactileSensorId.RING_FINGER,
    JointId.LF_MCP: TactileSensorId.LITTLE_FINGER,
    JointId.LF_PIP: TactileSensorId.LITTLE_FINGER,
}


@dataclass
class ObjectProfile:
    name: str
    weight_kg: float
    material: str
    safe_force_min: float
    safe_force_max: float
    friction_coeff: float
    is_fragile: bool


@dataclass
class ForceDecision:
    control_u: float
    next_torque: int
    target_angles: dict[JointId, float]
    is_fragile_mode: bool
    near_limit: bool = False


class _FingerPidState:
    def __init__(self):
        self.integral: float = 0.0
        self.prev_error: float = 0.0


class ForcePlanner:
    def __init__(self, config: AdaptiveGraspConfig, profile: Optional[ObjectProfile] = None):
        self.config = config
        self.profile = profile
        self.F_init = self._compute_F_init()
        self.is_fragile_mode = profile.is_fragile if profile else False

        self._finger_pid: dict[TactileSensorId, _FingerPidState] = {}
        self._hold_joint_angles: dict[JointId, float] = {}
        self._hold_joint_angle_baseline: dict[JointId, float] = {}

    def _compute_F_init(self) -> float:
        cfg = self.config
        if self.profile is None:
            return cfg.base_holding_force
        F = self.profile.weight_kg * _G * cfg.safety_factor + cfg.base_holding_force
        return self._clip(F, self.profile.safe_force_min, self.profile.safe_force_max)

    def _is_near_limit(self, finger_fz: dict[TactileSensorId, float]) -> bool:
        threshold = 0.9 * self.config.max_normal_force_per_finger
        return any(fz >= threshold for fz in finger_fz.values())

    def compute(self, analysis: TactileAnalysis, current_angles: dict[JointId, float]) -> ForceDecision:
        cfg = self.config

        if analysis.per_finger:
            return self._compute_per_finger(analysis, current_angles)

        # 统一控制回退（兼容无 per_finger 的情况）
        near_limit = self._is_near_limit(analysis.finger_fz)
        finger_count = max(len(analysis.finger_fz), 1)
        F_n_ref = self.F_init / finger_count
        max_fz = max(analysis.finger_fz.values()) if analysis.finger_fz else 0.0

        s_k = analysis.slip_risk
        e_nk = max(0.0, (max_fz - cfg.max_normal_force_per_finger) / (cfg.max_normal_force_per_finger + cfg.epsilon))
        u_ff = cfg.K_s * s_k - cfg.K_n * e_nk

        pid_state = self._get_or_create_pid(TactileSensorId.THUMB)
        e_k = F_n_ref - max_fz
        pid_state.integral = self._clip(pid_state.integral + e_k * cfg.control_period_s, cfg.I_min, cfg.I_max)
        derivative = (e_k - pid_state.prev_error) / cfg.control_period_s
        pid_state.prev_error = e_k
        u_pid = cfg.K_p * e_k + cfg.K_i * pid_state.integral + cfg.K_d * derivative

        control_u = u_ff + u_pid

        if self.is_fragile_mode and max_fz >= cfg.max_normal_force_per_finger:
            control_u = min(control_u, 0.0)

        target_angles = self._allocate_delta_to_joints(control_u, current_angles, near_limit=near_limit)
        next_torque = self._compute_next_torque()

        return ForceDecision(
            control_u=control_u,
            next_torque=next_torque,
            target_angles=target_angles,
            is_fragile_mode=self.is_fragile_mode,
            near_limit=near_limit,
        )

    def _compute_per_finger(
        self, analysis: TactileAnalysis, current_angles: dict[JointId, float]
    ) -> ForceDecision:
        cfg = self.config
        finger_count = max(len(analysis.per_finger), 1)
        F_n_ref = self.F_init / finger_count

        target_angles = dict(current_angles)
        control_u_values: list[float] = []
        near_limit = self._is_near_limit(analysis.finger_fz)

        for finger, fa in analysis.per_finger.items():
            s_total = fa.s_total
            fz = fa.fz

            e_nk = max(0.0, (fz - cfg.max_normal_force_per_finger) / (cfg.max_normal_force_per_finger + cfg.epsilon))
            u_ff = cfg.K_s * s_total - cfg.K_n * e_nk

            pid_state = self._get_or_create_pid(finger)
            e_k = F_n_ref - fz
            pid_state.integral = self._clip(pid_state.integral + e_k * cfg.control_period_s, cfg.I_min, cfg.I_max)
            derivative = (e_k - pid_state.prev_error) / cfg.control_period_s
            pid_state.prev_error = e_k
            u_pid = cfg.K_p * e_k + cfg.K_i * pid_state.integral + cfg.K_d * derivative

            control_u = u_ff + u_pid

            if self.is_fragile_mode and fz >= cfg.max_normal_force_per_finger:
                control_u = min(control_u, 0.0)

            control_u_values.append(control_u)

            # 将该手指的 control_u 映射到对应关节
            total_delta = control_u * math.radians(0.5)
            delta_limit = cfg.delta_theta_limit
            if self.is_fragile_mode:
                delta_limit *= cfg.fragile_step_reduction
            if near_limit:
                delta_limit *= 0.5
            total_delta = self._clip(total_delta, -delta_limit, delta_limit)

            mcp_delta = total_delta * cfg.K_MCP
            pip_delta = total_delta * cfg.K_PIP

            for joint_id, angle in current_angles.items():
                mapped_finger = _JOINT_TO_FINGER.get(joint_id)
                if mapped_finger != finger:
                    continue
                baseline = self._hold_joint_angle_baseline.get(joint_id, 0.0)
                min_a = baseline - math.radians(20.0)
                max_a = baseline + math.radians(20.0)
                if "MCP" in joint_id.name:
                    target_angles[joint_id] = self._clip(angle + mcp_delta, min_a, max_a)
                elif "PIP" in joint_id.name:
                    target_angles[joint_id] = self._clip(angle + pip_delta, min_a, max_a)
                else:
                    # SWING/ROTATION 等辅助关节沿用当前角（不参与闭环微调）
                    target_angles[joint_id] = angle

        next_torque = self._compute_next_torque()

        # 返回绝对值最大的 control_u，保留符号，用于外部判断是否需要更新
        representative_control_u = max(control_u_values, key=abs) if control_u_values else 0.0
        return ForceDecision(
            control_u=representative_control_u,
            next_torque=next_torque,
            target_angles=target_angles,
            is_fragile_mode=self.is_fragile_mode,
            near_limit=near_limit,
        )

    def _allocate_delta_to_joints(
        self, control_u: float, current_angles: dict[JointId, float], *, near_limit: bool = False
    ) -> dict[JointId, float]:
        cfg = self.config
        total_delta = control_u * math.radians(0.5)
        delta_limit = cfg.delta_theta_limit
        if self.is_fragile_mode:
            delta_limit *= cfg.fragile_step_reduction
        if near_limit:
            delta_limit *= 0.5
        total_delta = self._clip(total_delta, -delta_limit, delta_limit)

        mcp_delta = total_delta * cfg.K_MCP
        pip_delta = total_delta * cfg.K_PIP

        target_angles = dict(current_angles)
        for joint_id in current_angles:
            baseline = self._hold_joint_angle_baseline.get(joint_id, 0.0)
            min_a = baseline - math.radians(20.0)
            max_a = baseline + math.radians(20.0)
            if "MCP" in joint_id.name:
                target_angles[joint_id] = self._clip(current_angles[joint_id] + mcp_delta, min_a, max_a)
            elif "PIP" in joint_id.name:
                target_angles[joint_id] = self._clip(current_angles[joint_id] + pip_delta, min_a, max_a)

        return target_angles

    def _compute_next_torque(self) -> int:
        cfg = self.config
        speed_limit = cfg.position_speed_limit
        if self.is_fragile_mode:
            speed_limit = int(speed_limit * cfg.fragile_speed_reduction)
        return min(speed_limit, cfg.position_torque_limit)

    def reset(self) -> None:
        self._finger_pid.clear()
        self._hold_joint_angles = {}
        self._hold_joint_angle_baseline = {}

    def set_baseline_angles(self, angles: dict[JointId, float]) -> None:
        self._hold_joint_angles = dict(angles)
        self._hold_joint_angle_baseline = dict(angles)

    def _get_or_create_pid(self, finger: TactileSensorId) -> _FingerPidState:
        if finger not in self._finger_pid:
            self._finger_pid[finger] = _FingerPidState()
        return self._finger_pid[finger]

    @staticmethod
    def _clip(value: float, lower: float, upper: float) -> float:
        if upper < lower:
            upper = lower
        return max(lower, min(upper, value))


class ObjectProfileRegistry:
    _profiles: dict[str, ObjectProfile] = {}

    @classmethod
    def register(cls, profile: ObjectProfile) -> None:
        cls._profiles[profile.name] = profile

    @classmethod
    def get(cls, name: str) -> Optional[ObjectProfile]:
        return cls._profiles.get(name)

    @classmethod
    def list_names(cls) -> list[str]:
        return list(cls._profiles.keys())


ObjectProfileRegistry.register(
    ObjectProfile(
        name="metal_block",
        weight_kg=0.5,
        material="metal",
        safe_force_min=2.0,
        safe_force_max=15.0,
        friction_coeff=0.3,
        is_fragile=False,
    )
)
ObjectProfileRegistry.register(
    ObjectProfile(
        name="plastic_cup",
        weight_kg=0.1,
        material="plastic",
        safe_force_min=0.5,
        safe_force_max=5.0,
        friction_coeff=0.4,
        is_fragile=False,
    )
)
ObjectProfileRegistry.register(
    ObjectProfile(
        name="tofu",
        weight_kg=0.05,
        material="tofu",
        safe_force_min=0.5,
        safe_force_max=3.0,
        friction_coeff=0.2,
        is_fragile=True,
    )
)
ObjectProfileRegistry.register(
    ObjectProfile(
        name="banana",
        weight_kg=0.12,
        material="fruit",
        safe_force_min=0.5,
        safe_force_max=4.0,
        friction_coeff=0.3,
        is_fragile=True,
    )
)
