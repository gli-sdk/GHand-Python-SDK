from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId

from .config import AdaptiveGraspConfig
from .force_reference_planner import ForceReferenceDecision
from .object_profile import ObjectProfile
from .pid_controller import PidController, PidParams
from .tactility import TactileAnalysis
from .utils import JOINT_TO_FINGER, clip


_NEAR_FORCE_LIMIT_RATIO = 0.9
_NEAR_LIMIT_STEP_SCALE = 0.8

JointAngles = dict[JointId, float]
FingerForces = dict[TactileSensorId, float]


@dataclass
class ForceDecision:
    control_u: float
    next_torque: int
    target_angles: JointAngles
    is_fragile_mode: bool
    near_limit: bool = False


ForceDecisions = dict[TactileSensorId, ForceDecision]


class PositionHoldPlanner:
    """Plans position-mode joint corrections from shared force references."""

    def __init__(self, config: AdaptiveGraspConfig, profile: Optional[ObjectProfile] = None):
        self.config = config
        self.profile = profile
        self.is_fragile_mode = profile.is_fragile if profile else False
        self._finger_pid: dict[TactileSensorId, PidController] = {}

    def compute(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        force_reference: ForceReferenceDecision,
        dt: float,
    ) -> ForceDecisions:
        finger_count = self._get_effective_contact_count(analysis.finger_fz)
        near_limit = self._is_near_limit(analysis.finger_fz, finger_count)
        return {
            finger: self._build_decision(
                finger,
                self._compute_finger_control_u(
                    finger,
                    analysis,
                    force_reference,
                    finger_count,
                    dt,
                ),
                current_angles,
                near_limit,
            )
            for finger in self.config.active_fingers
        }

    def reset(self) -> None:
        self._finger_pid.clear()

    def _compute_finger_control_u(
        self,
        finger: TactileSensorId,
        analysis: TactileAnalysis,
        force_reference: ForceReferenceDecision,
        finger_count: int,
        dt: float,
    ) -> float:
        fz = analysis.finger_fz.get(finger, 0.0)
        fz_ref = force_reference.force_refs.get(finger, 0.0)
        fz_limit = self._get_max_normal_force_per_finger(finger_count)
        return self._compute_pid_control_u(
            finger,
            fz=fz,
            fz_limit=fz_limit,
            F_n_ref=fz_ref,
            dt=dt,
        )

    def _compute_pid_control_u(
        self,
        finger: TactileSensorId,
        fz: float,
        fz_limit: float,
        F_n_ref: float,
        dt: float,
    ) -> float:
        error = F_n_ref - fz
        overlimit_u = self._compute_overlimit_control_u(fz, fz_limit)
        pid_u = self._get_or_create_pid(finger).compute(error=error, dt=dt)
        control_u = overlimit_u + pid_u
        if self.is_fragile_mode and fz >= fz_limit:
            control_u = min(control_u, 0.0)
        return control_u

    def _compute_overlimit_control_u(self, fz: float, fz_limit: float) -> float:
        normal_overlimit_error = max(0.0, (fz - fz_limit) / (fz_limit + self.config.epsilon))
        return -self.config.K_n * normal_overlimit_error

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

    def _get_max_normal_force_per_finger(self, finger_count: int) -> float:
        if self.profile is not None:
            return self.profile.safe_force_max / finger_count
        return self.config.max_normal_force_per_finger

    def _compute_next_torque(self) -> int:
        next_torque = (
            self.profile.position_hold_torque
            if self.profile is not None and self.profile.base_hold_torque is not None
            else self.config.position_torque_limit
        )
        if self.is_fragile_mode:
            next_torque = int(next_torque * self.config.fragile_torque_reduction)
        return next_torque

    def _get_or_create_pid(self, finger: TactileSensorId) -> PidController:
        if finger not in self._finger_pid:
            self._finger_pid[finger] = PidController(self._get_pid_params(finger))
        return self._finger_pid[finger]

    def _get_pid_param(self, finger: TactileSensorId, param_name: str) -> float:
        per_finger_cfg = self.config.per_finger_pid.get(finger)
        if per_finger_cfg is not None:
            value = getattr(per_finger_cfg, param_name, None)
            if value is not None:
                return value
        return getattr(self.config, f"position_hold_{param_name}")

    def _get_pid_params(self, finger: TactileSensorId) -> PidParams:
        return PidParams(
            K_p=self._get_pid_param(finger, "K_p"),
            K_i=self._get_pid_param(finger, "K_i"),
            K_d=self._get_pid_param(finger, "K_d"),
            I_min=self._get_pid_param(finger, "I_min"),
            I_max=self._get_pid_param(finger, "I_max"),
        )

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
