from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId

from .config import AdaptiveGraspConfig
from .force_reference_planner import ForceReferenceDecision
from .object_profile import ObjectProfile
from .pid_controller import LowPassFilter
from .tactility import TactileAnalysis
from .utils import JOINT_TO_FINGER, clip


JointAngles = dict[JointId, float]
FingerForces = dict[TactileSensorId, float]


@dataclass
class ForceDecision:
    control_u: float
    next_torque: int
    target_angles: JointAngles
    is_fragile_mode: bool
    near_limit: bool = False
    next_speed: Optional[int] = None


ForceDecisions = dict[TactileSensorId, ForceDecision]


class PositionHoldPlanner:
    """Plans position-mode joint corrections from shared force references.

    ``force_reference`` and ``dt`` are kept on ``compute`` so position and
    torque planners can share the same call shape, even though the direct
    position-control strategy does not currently use them.
    """

    def __init__(
        self,
        config: AdaptiveGraspConfig,
        profile: Optional[ObjectProfile] = None,
    ):
        self.config = config
        self.profile = profile
        self.is_fragile_mode = profile.is_fragile if profile else False
        self._slip_risk_filters: dict[TactileSensorId, LowPassFilter] = {
            finger: LowPassFilter(alpha=config.lowpass_alpha)
            for finger in config.active_fingers
        }

    def compute(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        force_reference: ForceReferenceDecision,
        dt: float,
    ) -> ForceDecisions:
        _ = (force_reference, dt)
        finger_count = self._get_effective_contact_count(analysis.finger_fz)
        near_limit = self._is_near_limit(analysis.finger_fz, finger_count)
        decisions: ForceDecisions = {}
        for finger in self.config.active_fingers:
            control_u = 0.0
            if self.config.enable_position_hold_force_control:
                control_u = self._compute_finger_direct_control_u(
                    finger,
                    analysis,
                    finger_count,
                )
            decisions[finger] = self._build_decision(
                finger,
                control_u,
                current_angles,
                near_limit,
            )
        return decisions

    def reset(self) -> None:
        for f in self._slip_risk_filters.values():
            f.reset()

    def _compute_finger_direct_control_u(
        self,
        finger: TactileSensorId,
        analysis: TactileAnalysis,
        finger_count: int,
    ) -> float:
        fz = analysis.finger_fz.get(finger, 0.0)
        fz_filtered = analysis.per_finger[finger].fz_filtered
        fz_limit = self._get_max_normal_force_per_finger(finger_count)
        finger_analysis = analysis.per_finger.get(finger)
        slip_risk = finger_analysis.s_total if finger_analysis is not None else 0.0
        slip_confirmed = finger_analysis.slip_confirmed if finger_analysis is not None else False

        slip_risk_filtered = self._slip_risk_filters[finger].compute(slip_risk)
        u_slip = self._compute_slip_control_u(slip_risk_filtered)
        u_boost = self._compute_confirmed_slip_boost_u(slip_confirmed)
        u_over = self._compute_overlimit_control_u(fz_filtered, fz_limit)
        u_ff = self._compute_feedforward_control_u(fz_filtered, finger_count)
        
        control_u = u_slip + u_boost + u_over + u_ff
        if self.is_fragile_mode and fz >= fz_limit:
            control_u = min(control_u, 0.0)
        return control_u

    def _compute_feedforward_control_u(
        self,
        fz: float,
        finger_count: int,
    ) -> float:
        if self.profile is None:
            raise ValueError("ObjectProfile is required for position hold mode")
        safe_force_min_per_finger = self.profile.safe_force_min / finger_count
        return max((safe_force_min_per_finger - fz) / safe_force_min_per_finger, 0)

    def _compute_slip_control_u(self, slip_risk: float) -> float:
        cfg = self.config
        denominator = cfg.direct_slip_risk_full - cfg.direct_slip_risk_deadband
        normalized_risk = clip(
            (slip_risk - cfg.direct_slip_risk_deadband) / denominator,
            0.0,
            1.0,
        )
        return cfg.delta_theta_limit * (normalized_risk ** cfg.direct_slip_risk_gamma)

    def _compute_confirmed_slip_boost_u(self, slip_confirmed: bool) -> float:
        if not slip_confirmed:
            return 0.0
        return self.config.delta_theta_limit * self.config.direct_slip_confirmed_boost_ratio

    def _compute_overlimit_control_u(self, fz: float, fz_limit: float) -> float:
        normal_overlimit_error = max(
            0.0,
            (fz - fz_limit) / (fz_limit + self.config.epsilon),
        )
        return -self.config.K_n * normal_overlimit_error

    def _build_decision(
        self,
        finger: TactileSensorId,
        control_u: float,
        current_angles: JointAngles,
        near_limit: bool,
    ) -> ForceDecision:
        total_delta = self._limited_total_delta(control_u, near_limit)
        mcp_delta, pip_delta = self._joint_deltas(finger, total_delta)

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
            next_speed=self._compute_next_speed(),
        )

    def _joint_deltas(
        self,
        finger: TactileSensorId,
        total_delta: float,
    ) -> tuple[float, float]:
        if finger == TactileSensorId.THUMB:
            return (
                total_delta * self.config.thumb_K_MCP,
                total_delta * self.config.thumb_K_PIP,
            )
        return (
            total_delta * self.config.finger_K_MCP,
            total_delta * self.config.finger_K_PIP,
        )

    def _limited_total_delta(self, control_u: float, near_limit: bool) -> float:
        delta_limit = self.config.delta_theta_limit
        if self.is_fragile_mode:
            delta_limit *= self.config.fragile_step_reduction
        if near_limit:
            delta_limit *= self.config.near_limit_step_scale
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
        threshold = self.config.near_force_limit_ratio * self._get_max_normal_force_per_finger(finger_count)
        return any(
            finger_fz.get(finger, 0.0) >= threshold
            for finger in self.config.active_fingers
        )

    def _get_max_normal_force_per_finger(self, finger_count: int) -> float:
        if self.profile is not None:
            return self.profile.safe_force_max / finger_count
        return self.config.max_normal_force_per_finger

    def _compute_next_torque(self) -> int:
        if self.profile is None or self.profile.position_hold_torque is None:
            raise ValueError("ObjectProfile.position_hold_torque is required for position hold mode")
        next_torque = self.profile.position_hold_torque
        if self.is_fragile_mode:
            next_torque = int(next_torque * self.config.fragile_torque_reduction)
        return next_torque

    def _compute_next_speed(self) -> int:
        if self.profile is None or self.profile.position_hold_speed is None:
            raise ValueError("ObjectProfile.position_hold_speed is required for position hold mode")
        next_speed = self.profile.position_hold_speed
        return int(clip(next_speed, 0, 100))

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
