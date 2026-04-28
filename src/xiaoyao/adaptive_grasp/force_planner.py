import time
from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId

from .config import AdaptiveGraspConfig
from .object_profile import ObjectProfile
from .tactility import PerFingerAnalysis, TactileAnalysis
from .utils import JOINT_TO_FINGER, clip


_G = 9.8


@dataclass
class ForceDecision:
    control_u: float
    next_torque: int
    target_angles: dict[JointId, float]
    is_fragile_mode: bool
    near_limit: bool = False


@dataclass
class _PidParams:
    K_p: float
    K_i: float
    K_d: float
    I_min: float
    I_max: float


class _FingerPidState:
    def __init__(self):
        self.integral: float = 0.0
        self.prev_error: float = 0.0
        self._initialized: bool = False


class ForcePlanner:
    """Compute adaptive grasp force targets and per-finger joint corrections."""

    def __init__(self, config: AdaptiveGraspConfig, profile: Optional[ObjectProfile] = None):
        self.config = config
        self.profile = profile
        self.F_init = self._compute_F_init()
        self.is_fragile_mode = profile.is_fragile if profile else False

        self._finger_pid: dict[TactileSensorId, _FingerPidState] = {}
        self._last_compute_time: Optional[float] = None
        self._get_monotonic_time = time.monotonic

    def _compute_F_init(self) -> float:
        """Return the total target normal force for the grasp."""
        cfg = self.config
        if self.profile is None:
            return cfg.base_holding_force

        raw_force = (
            self.profile.weight_kg
            * _G
            / self.profile.friction_coeff
            * cfg.safety_factor
            + cfg.base_holding_force
        )
        max_force = self.profile.safe_force_max
        if self.profile.is_fragile:
            max_force *= 0.9
        return clip(raw_force, self.profile.safe_force_min, max_force)

    def _get_max_normal_force_per_finger(self, finger_count: int) -> float:
        if self.profile is not None:
            return self.profile.safe_force_max / finger_count
        return self.config.max_normal_force_per_finger

    def _get_effective_contact_count(self, finger_fz: dict[TactileSensorId, float]) -> int:
        active_finger_count = max(len(self.config.active_fingers), 1)
        contacting_fingers = sum(
            1
            for finger in self.config.active_fingers
            if finger_fz.get(finger, 0.0) > self.config.epsilon
        )
        return contacting_fingers or active_finger_count

    def _is_near_limit(self, finger_fz: dict[TactileSensorId, float], finger_count: int) -> bool:
        threshold = 0.9 * self._get_max_normal_force_per_finger(finger_count)
        return any(finger_fz.get(finger, 0.0) >= threshold for finger in self.config.active_fingers)

    def compute(
        self,
        analysis: TactileAnalysis,
        current_angles: dict[JointId, float],
        dt: Optional[float] = None,
    ) -> dict[TactileSensorId, ForceDecision]:
        cfg = self.config

        now = self._get_monotonic_time()
        if dt is not None and dt > 0:
            actual_dt = dt
        elif self._last_compute_time is not None:
            actual_dt = now - self._last_compute_time
            if actual_dt <= 0 or actual_dt > 1.0:
                actual_dt = cfg.control_period_s
        else:
            actual_dt = cfg.control_period_s
        self._last_compute_time = now

        finger_count = self._get_effective_contact_count(analysis.finger_fz)
        near_limit = self._is_near_limit(analysis.finger_fz, finger_count)
        decisions: dict[TactileSensorId, ForceDecision] = {}

        if analysis.per_finger:
            for finger in cfg.active_fingers:
                finger_analysis = analysis.per_finger.get(finger)
                if finger_analysis is None:
                    continue
                control_u = self._compute_finger_control_u(
                    finger,
                    finger_analysis,
                    finger_count,
                    actual_dt,
                )
                decisions[finger] = self._build_finger_decision(
                    finger,
                    control_u,
                    current_angles,
                    near_limit,
                )
        else:
            control_u = self._compute_unified_control_u(analysis, finger_count, actual_dt)
            for finger in cfg.active_fingers:
                decisions[finger] = self._build_finger_decision(
                    finger,
                    control_u,
                    current_angles,
                    near_limit,
                )

        return decisions

    def _compute_pid_control_u(
        self,
        finger: TactileSensorId,
        s_k: float,
        fz: float,
        fz_limit: float,
        F_n_ref: float,
        dt: float,
    ) -> float:
        pid_state = self._get_or_create_pid(finger)
        e_k = F_n_ref - fz
        pid_param = self._get_pid_params(finger)
        pid_state.integral = clip(pid_state.integral + e_k * dt, pid_param.I_min, pid_param.I_max)
        if pid_state._initialized:
            derivative = (e_k - pid_state.prev_error) / dt
        else:
            derivative = 0.0
            pid_state._initialized = True
        pid_state.prev_error = e_k

        control_u = (
            pid_param.K_p * e_k
            + pid_param.K_i * pid_state.integral
            + pid_param.K_d * derivative
        )
        if self.is_fragile_mode and fz >= fz_limit:
            control_u = min(control_u, 0.0)
        return control_u

    def _compute_finger_control_u(
        self,
        finger: TactileSensorId,
        per_finger_analysis: PerFingerAnalysis,
        finger_count: int,
        dt: float,
    ) -> float:
        F_n_ref = self.F_init / finger_count
        fz_limit = self._get_max_normal_force_per_finger(finger_count)
        return self._compute_pid_control_u(
            finger,
            s_k=per_finger_analysis.s_total,
            fz=per_finger_analysis.fz,
            fz_limit=fz_limit,
            F_n_ref=F_n_ref,
            dt=dt,
        )

    def _compute_unified_control_u(
        self,
        analysis: TactileAnalysis,
        finger_count: int,
        dt: float,
    ) -> float:
        F_n_ref = self.F_init / finger_count
        max_fz_limit = self._get_max_normal_force_per_finger(finger_count)
        max_fz = max(analysis.finger_fz.values()) if analysis.finger_fz else 0.0
        return self._compute_pid_control_u(
            TactileSensorId.THUMB,
            s_k=analysis.slip_risk,
            fz=max_fz,
            fz_limit=max_fz_limit,
            F_n_ref=F_n_ref,
            dt=dt,
        )

    def _build_finger_decision(
        self,
        finger: TactileSensorId,
        control_u: float,
        current_angles: dict[JointId, float],
        near_limit: bool,
    ) -> ForceDecision:
        cfg = self.config
        target_angles: dict[JointId, float] = {}

        total_delta = control_u
        delta_limit = cfg.delta_theta_limit
        if self.is_fragile_mode:
            delta_limit *= cfg.fragile_step_reduction
        if near_limit:
            delta_limit *= 0.8
        total_delta = clip(total_delta, -delta_limit, delta_limit)

        mcp_delta = total_delta * cfg.K_MCP
        pip_delta = total_delta * cfg.K_PIP

        for joint_id, angle in current_angles.items():
            mapped_finger = JOINT_TO_FINGER.get(joint_id)
            if mapped_finger != finger:
                continue
            if "MCP" in joint_id.name:
                target_angles[joint_id] = angle + mcp_delta
            elif "PIP" in joint_id.name:
                target_angles[joint_id] = angle + pip_delta
            else:
                target_angles[joint_id] = angle

        return ForceDecision(
            control_u=control_u,
            next_torque=self._compute_next_torque(),
            target_angles=target_angles,
            is_fragile_mode=self.is_fragile_mode,
            near_limit=near_limit,
        )

    def _compute_next_torque(self) -> int:
        next_torque = self.config.position_torque_limit
        if self.is_fragile_mode:
            next_torque = int(next_torque * self.config.fragile_torque_reduction)
        return next_torque

    def reset(self) -> None:
        self._finger_pid.clear()
        self._last_compute_time = None

    def _get_or_create_pid(self, finger: TactileSensorId) -> _FingerPidState:
        if finger not in self._finger_pid:
            self._finger_pid[finger] = _FingerPidState()
        return self._finger_pid[finger]

    def _get_pid_param(self, finger: TactileSensorId, param_name: str) -> float:
        per_finger_cfg = self.config.per_finger_pid.get(finger)
        if per_finger_cfg is not None:
            val = getattr(per_finger_cfg, param_name, None)
            if val is not None:
                return val
        return getattr(self.config, param_name)

    def _get_pid_params(self, finger: TactileSensorId) -> _PidParams:
        return _PidParams(
            K_p=self._get_pid_param(finger, "K_p"),
            K_i=self._get_pid_param(finger, "K_i"),
            K_d=self._get_pid_param(finger, "K_d"),
            I_min=self._get_pid_param(finger, "I_min"),
            I_max=self._get_pid_param(finger, "I_max"),
        )
