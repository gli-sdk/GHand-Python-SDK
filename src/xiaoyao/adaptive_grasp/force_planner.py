import math
from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .tactile import TactileAnalysis


_G = 9.8


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


class ForcePlanner:
    def __init__(self, config: AdaptiveGraspConfig, profile: Optional[ObjectProfile] = None):
        self.config = config
        self.profile = profile
        self.F_init = self._compute_F_init()
        self.is_fragile_mode = profile.is_fragile if profile else False

        self._pid_integral: float = 0.0
        self._pid_prev_error: float = 0.0
        self._hold_joint_angles: dict[JointId, float] = {}
        self._hold_joint_angle_baseline: dict[JointId, float] = {}

    def _compute_F_init(self) -> float:
        cfg = self.config
        if self.profile is None:
            return cfg.base_holding_force
        F = self.profile.weight_kg * _G * cfg.safety_factor + cfg.base_holding_force
        return self._clip(F, self.profile.safe_force_min, self.profile.safe_force_max)

    def compute(self, analysis: TactileAnalysis, current_angles: dict[JointId, float]) -> ForceDecision:
        cfg = self.config
        finger_count = max(len(analysis.finger_fz), 1)
        F_n_ref = self.F_init / finger_count
        max_fz = max(analysis.finger_fz.values()) if analysis.finger_fz else 0.0

        # 前馈
        s_k = analysis.slip_risk
        e_nk = max(0.0, (max_fz - cfg.max_normal_force_per_finger) / (cfg.max_normal_force_per_finger + cfg.epsilon))
        u_ff = cfg.K_s * s_k - cfg.K_n * e_nk

        # PID 围绕法向力误差（V2.0 核心变更）
        e_k = F_n_ref - max_fz
        self._pid_integral = self._clip(
            self._pid_integral + e_k * cfg.control_period_s,
            cfg.I_min, cfg.I_max
        )
        derivative = (e_k - self._pid_prev_error) / cfg.control_period_s
        self._pid_prev_error = e_k
        u_pid = cfg.K_p * e_k + cfg.K_i * self._pid_integral + cfg.K_d * derivative

        control_u = u_ff + u_pid

        # 损伤防护：达到 100% 阈值后截断正向控制量
        if self.is_fragile_mode and max_fz >= cfg.max_normal_force_per_finger:
            control_u = min(control_u, 0.0)

        # 角增量分配
        total_delta = control_u * math.radians(0.5)
        delta_limit = cfg.delta_theta_limit
        if self.is_fragile_mode:
            delta_limit *= cfg.fragile_step_reduction
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

        # 易损模式速度限制
        speed_limit = cfg.position_speed_limit
        if self.is_fragile_mode:
            speed_limit = int(speed_limit * cfg.fragile_speed_reduction)
        next_torque = min(speed_limit, cfg.position_torque_limit)

        return ForceDecision(
            control_u=control_u,
            next_torque=next_torque,
            target_angles=target_angles,
            is_fragile_mode=self.is_fragile_mode,
        )

    def reset(self) -> None:
        self._pid_integral = 0.0
        self._pid_prev_error = 0.0
        self._hold_joint_angles = {}
        self._hold_joint_angle_baseline = {}

    def set_baseline_angles(self, angles: dict[JointId, float]) -> None:
        self._hold_joint_angles = dict(angles)
        self._hold_joint_angle_baseline = dict(angles)

    @staticmethod
    def _clip(value: float, lower: float, upper: float) -> float:
        if upper < lower:
            upper = lower
        return max(lower, min(upper, value))
