from typing import Optional

from ghand import JointId, TactileSensorId

from .position_hold_planner import ForceDecision, ForceDecisions, JointAngles
from .tactility import TactileAnalysis
from .utils import normalize_joint_angles


class IncrementalPositionHoldPlanner:
    """Open-loop incremental position hold for very stiff objects.

    Instead of closing a per-finger force-error loop, this planner increases
    joint angles by a fixed step each cycle until the total normal force reaches
    the caller-supplied target. Contact loss (a sudden force drop) stops the
    increment and lets the safety monitor escalate to a fault release.
    """

    def __init__(
        self,
        *,
        step_deg: float,
        max_delta_deg: float,
        active_fingers: set[TactileSensorId],
        active_joint_ids: set[JointId],
        contact_joint_angles: Optional[JointAngles] = None,
        hold_speed: int,
        hold_torque: int,
        default_target_force_n: Optional[float] = None,
        stiff_position_force_drop_ratio: float,
    ):
        self._step = step_deg
        self._max_delta = max_delta_deg
        self._active_fingers = set(active_fingers)
        self._active_joint_ids = set(active_joint_ids)
        self.contact_joint_angles = normalize_joint_angles(
            contact_joint_angles or {})
        self._hold_speed = hold_speed
        self._hold_torque = hold_torque
        self._default_target_force_n = default_target_force_n
        self._stiff_position_force_drop_ratio = stiff_position_force_drop_ratio
        self._previous_total_fz: Optional[float] = None

    def compute(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        target_force_n: Optional[float] = None,
    ) -> ForceDecisions:
        total_fz = sum(analysis.finger_fz.values())
        target_force = target_force_n
        if target_force is None:
            target_force = self._default_target_force_n
        if target_force is None:
            raise ValueError(
                "target_force_n is required for stiff_position hold mode when no ObjectProfile is provided"
            )

        try:
            if self._is_contact_lost(total_fz):
                return self._hold_decisions(current_angles,
                                            speed=100,
                                            torque=self._hold_torque)

            if total_fz >= target_force:
                return self._hold_decisions(current_angles,
                                            speed=100,
                                            torque=self._hold_torque)

            next_angles = self._increment_angles(current_angles)
            return self._hold_decisions(next_angles,
                                        speed=self._hold_speed,
                                        torque=self._hold_torque)
        finally:
            self._previous_total_fz = total_fz

    def _is_contact_lost(self, total_fz: float) -> bool:
        if self._previous_total_fz is None:
            return False
        if self._previous_total_fz <= 0.0:
            return False
        threshold = self._previous_total_fz * (
            1.0 - self._stiff_position_force_drop_ratio)
        return total_fz < threshold

    def _increment_angles(self, current_angles: JointAngles) -> JointAngles:
        current_angles = normalize_joint_angles(current_angles)
        next_angles = dict(current_angles)

        for joint_id, angle in current_angles.items():
            if joint_id not in self._active_joint_ids:
                continue
            base = self.contact_joint_angles.get(joint_id, angle)
            current_delta = abs(angle - base)
            new_delta = min(current_delta + self._step, self._max_delta)
            next_angles[joint_id] = base + new_delta

        return next_angles

    def _hold_decisions(
        self,
        angles: JointAngles,
        *,
        speed: int,
        torque: int,
    ) -> ForceDecisions:
        angles = normalize_joint_angles(angles)
        target_angles = {
            joint_id: angles[joint_id]
            for joint_id in self._active_joint_ids if joint_id in angles
        }
        return {
            finger:
            ForceDecision(
                control_u=0.0,
                next_torque=torque,
                target_angles=target_angles,
                is_fragile_mode=False,
                near_limit=False,
                next_speed=speed,
            )
            for finger in self._active_fingers
        }

