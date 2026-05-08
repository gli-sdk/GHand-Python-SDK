import time
from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId

from .config import AdaptiveGraspConfig
from .object_profile import ObjectProfile
from .tactility import PerFingerAnalysis, TactileAnalysis
from .utils import JOINT_TO_FINGER, clip


_G = 9.8
_FRAGILE_SAFE_FORCE_SCALE = 0.9
_NEAR_FORCE_LIMIT_RATIO = 0.9
_NEAR_LIMIT_STEP_SCALE = 0.8
_MAX_DT_S = 1.0

FingerForces = dict[TactileSensorId, float]
JointAngles = dict[JointId, float]


@dataclass
class ForceDecision:
    control_u: float
    next_torque: int
    target_angles: JointAngles
    is_fragile_mode: bool
    near_limit: bool = False


ForceDecisions = dict[TactileSensorId, ForceDecision]


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

    def compute(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        dt: Optional[float] = None,
    ) -> ForceDecisions:
        actual_dt = self._compute_dt(dt)
        finger_count = self._get_effective_contact_count(analysis.finger_fz)
        near_limit = self._is_near_limit(analysis.finger_fz, finger_count)

        if analysis.per_finger:
            return self._compute_per_finger_decisions(
                analysis,
                current_angles,
                finger_count,
                actual_dt,
                near_limit,
            )
        return self._compute_unified_decisions(
            analysis,
            current_angles,
            finger_count,
            actual_dt,
            near_limit,
        )

    def reset(self) -> None:
        self._finger_pid.clear()
        self._last_compute_time = None

    def _compute_per_finger_decisions(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        finger_count: int,
        dt: float,
        near_limit: bool,
    ) -> ForceDecisions:
        decisions: ForceDecisions = {}
        for finger in self.config.active_fingers:
            finger_analysis = analysis.per_finger.get(finger)
            if finger_analysis is None:
                continue
            decisions[finger] = self._build_decision_from_finger_analysis(
                finger,
                finger_analysis,
                finger_count,
                dt,
                current_angles,
                near_limit,
            )
        return decisions

    def _compute_unified_decisions(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        finger_count: int,
        dt: float,
        near_limit: bool,
    ) -> ForceDecisions:
        control_u = self._compute_unified_control_u(analysis, finger_count, dt)
        control_u = self._apply_hold_strategy(control_u, analysis.slip_confirmed)
        return {
            finger: self._build_decision(finger, control_u, current_angles, near_limit)
            for finger in self.config.active_fingers
        }

    def _build_decision_from_finger_analysis(
        self,
        finger: TactileSensorId,
        finger_analysis: PerFingerAnalysis,
        finger_count: int,
        dt: float,
        current_angles: JointAngles,
        near_limit: bool,
    ) -> ForceDecision:
        control_u = self._compute_finger_control_u(
            finger,
            finger_analysis,
            finger_count,
            dt,
        )
        control_u = self._apply_hold_strategy(
            control_u,
            finger_analysis.slip_confirmed,
        )
        return self._build_decision(finger, control_u, current_angles, near_limit)

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
            max_force *= _FRAGILE_SAFE_FORCE_SCALE
        return clip(raw_force, self.profile.safe_force_min, max_force)

    def _compute_dt(self, dt: Optional[float]) -> float:
        now = self._get_monotonic_time()
        if dt is not None and dt > 0:
            actual_dt = dt
        elif self._last_compute_time is not None:
            actual_dt = now - self._last_compute_time
            if actual_dt <= 0 or actual_dt > _MAX_DT_S:
                actual_dt = self.config.control_period_s
        else:
            actual_dt = self.config.control_period_s
        self._last_compute_time = now
        return actual_dt

    def _get_effective_contact_count(self, finger_fz: FingerForces) -> int:
        active_finger_count = max(len(self.config.active_fingers), 1)
        contacting_fingers = sum(
            1
            for finger in self.config.active_fingers
            if finger_fz.get(finger, 0.0) > self.config.epsilon
        )
        return contacting_fingers or active_finger_count

    def _is_near_limit(self, finger_fz: FingerForces, finger_count: int) -> bool:
        threshold = _NEAR_FORCE_LIMIT_RATIO * self._get_max_normal_force_per_finger(finger_count)
        return any(
            finger_fz.get(finger, 0.0) >= threshold
            for finger in self.config.active_fingers
        )

    def _apply_hold_strategy(self, control_u: float, slip_confirmed: bool) -> float:
        return control_u if self._is_control_enabled(slip_confirmed) else 0.0

    def _is_control_enabled(self, slip_confirmed: bool) -> bool:
        strategy = self.profile.hold_strategy if self.profile is not None else None
        if strategy in (None, "fixed"):
            return False
        if strategy == "slip_triggered":
            return slip_confirmed
        return True

    def _compute_finger_control_u(
        self,
        finger: TactileSensorId,
        per_finger_analysis: PerFingerAnalysis,
        finger_count: int,
        dt: float,
    ) -> float:
        fz_ref = self.F_init / finger_count
        fz_limit = self._get_max_normal_force_per_finger(finger_count)
        return self._compute_pid_control_u(
            finger,
            s_k=per_finger_analysis.s_total,
            fz=per_finger_analysis.fz,
            fz_limit=fz_limit,
            F_n_ref=fz_ref,
            dt=dt,
        )

    def _compute_unified_control_u(
        self,
        analysis: TactileAnalysis,
        finger_count: int,
        dt: float,
    ) -> float:
        fz_ref = self.F_init / finger_count
        fz_limit = self._get_max_normal_force_per_finger(finger_count)
        max_fz = max(analysis.finger_fz.values()) if analysis.finger_fz else 0.0
        return self._compute_pid_control_u(
            TactileSensorId.THUMB,
            s_k=analysis.slip_risk,
            fz=max_fz,
            fz_limit=fz_limit,
            F_n_ref=fz_ref,
            dt=dt,
        )

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
        error = F_n_ref - fz
        params = self._get_pid_params(finger)

        pid_state.integral = clip(
            pid_state.integral + error * dt,
            params.I_min,
            params.I_max,
        )
        if pid_state._initialized:
            derivative = (error - pid_state.prev_error) / dt
        else:
            derivative = 0.0
            pid_state._initialized = True
        pid_state.prev_error = error

        feedforward_u = self._compute_feedforward_control_u(s_k, fz, fz_limit)
        pid_u = (
            params.K_p * error
            + params.K_i * pid_state.integral
            + params.K_d * derivative
        )
        control_u = feedforward_u + pid_u
        if self.is_fragile_mode and fz >= fz_limit:
            control_u = min(control_u, 0.0)
        return control_u

    def _compute_feedforward_control_u(self, s_k: float, fz: float, fz_limit: float) -> float:
        normal_overlimit_error = max(0.0, (fz - fz_limit) / (fz_limit + self.config.epsilon))
        return self.config.K_s * s_k - self.config.K_n * normal_overlimit_error

    def _build_decision(
        self,
        finger: TactileSensorId,
        control_u: float,
        current_angles: JointAngles,
        near_limit: bool,
    ) -> ForceDecision:
        total_delta = self._limited_total_delta(control_u, near_limit)
        mcp_delta = total_delta * self.config.K_MCP
        pip_delta = total_delta * self.config.K_PIP
        
        target_angles: JointAngles = {}
        for joint_id, angle in current_angles.items():
            if JOINT_TO_FINGER.get(joint_id) != finger:
                continue
            target_angles[joint_id] = self._offset_joint_angle(
                joint_id,
                angle,
                mcp_delta,
                pip_delta,
            )

        return ForceDecision(
            control_u=control_u,
            next_torque=self._compute_next_torque(),
            target_angles=target_angles,
            is_fragile_mode=self.is_fragile_mode,
            near_limit=near_limit,
        )

    def _limited_total_delta(self, control_u: float, near_limit: bool) -> float:
        delta_limit = self.config.delta_theta_limit
        if self.is_fragile_mode:
            delta_limit *= self.config.fragile_step_reduction
        if near_limit:
            delta_limit *= _NEAR_LIMIT_STEP_SCALE
        return clip(control_u, -delta_limit, delta_limit)

    @staticmethod
    def _offset_joint_angle(
        joint_id: JointId,
        angle: float,
        mcp_delta: float,
        pip_delta: float,
    ) -> float:
        if "MCP" in joint_id.name:
            return angle + mcp_delta
        if "PIP" in joint_id.name:
            return angle + pip_delta
        return angle

    def _get_max_normal_force_per_finger(self, finger_count: int) -> float:
        if self.profile is not None:
            return self.profile.safe_force_max / finger_count
        return self.config.max_normal_force_per_finger

    def _compute_next_torque(self) -> int:
        next_torque = self.config.position_torque_limit
        if self.is_fragile_mode:
            next_torque = int(next_torque * self.config.fragile_torque_reduction)
        return next_torque

    def _get_or_create_pid(self, finger: TactileSensorId) -> _FingerPidState:
        if finger not in self._finger_pid:
            self._finger_pid[finger] = _FingerPidState()
        return self._finger_pid[finger]

    def _get_pid_param(self, finger: TactileSensorId, param_name: str) -> float:
        per_finger_cfg = self.config.per_finger_pid.get(finger)
        if per_finger_cfg is not None:
            value = getattr(per_finger_cfg, param_name, None)
            if value is not None:
                return value
        return getattr(self.config, param_name)

    def _get_pid_params(self, finger: TactileSensorId) -> _PidParams:
        return _PidParams(
            K_p=self._get_pid_param(finger, "K_p"),
            K_i=self._get_pid_param(finger, "K_i"),
            K_d=self._get_pid_param(finger, "K_d"),
            I_min=self._get_pid_param(finger, "I_min"),
            I_max=self._get_pid_param(finger, "I_max"),
        )
