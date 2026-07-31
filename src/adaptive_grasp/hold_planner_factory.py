from dataclasses import dataclass
from typing import Optional

from .config import AdaptiveGraspConfig, HoldCommandMode
from .force_reference_planner import ForceReferencePlanner
from .grasp_sequence import ContactSnapshot
from .object_profile import ObjectProfile
from .incremental_position_hold_planner import IncrementalPositionHoldPlanner
from .position_hold_planner import PositionHoldPlanner
from .utils import JOINT_TO_FINGER


@dataclass(frozen=True)
class HoldPlannerBundle:
    force_reference_planner: Optional[ForceReferencePlanner] = None
    position_hold_planner: Optional[PositionHoldPlanner] = None
    stiff_position_hold_planner: Optional[
        IncrementalPositionHoldPlanner] = None


class HoldPlannerFactory:

    def __init__(self, config: AdaptiveGraspConfig):
        self.config = config

    def create(
        self,
        profile: Optional[ObjectProfile],
        contact_snapshot: Optional[ContactSnapshot],
    ) -> HoldPlannerBundle:
        if contact_snapshot is None:
            return HoldPlannerBundle()

        force_reference_planner = ForceReferencePlanner(
            self.config,
            profile,
            contact_snapshot,
        )
        if self.config.hold_command_mode is HoldCommandMode.POSITION:
            return HoldPlannerBundle(
                force_reference_planner=force_reference_planner,
                position_hold_planner=self._create_position_hold_planner(
                    profile),
            )

        if self.config.hold_command_mode is HoldCommandMode.STIFF_POSITION:
            return HoldPlannerBundle(
                force_reference_planner=force_reference_planner,
                stiff_position_hold_planner=self.
                _create_stiff_position_hold_planner(
                    profile,
                    contact_snapshot,
                ),
            )

        raise ValueError(
            "hold_command_mode must be HoldCommandMode.POSITION "
            "or HoldCommandMode.STIFF_POSITION")

    def _create_stiff_position_hold_planner(
        self,
        profile: Optional[ObjectProfile],
        contact_snapshot: ContactSnapshot,
    ) -> Optional[IncrementalPositionHoldPlanner]:
        active_joint_ids = {
            joint_id
            for joint_id, finger in JOINT_TO_FINGER.items()
            if finger in self.config.active_fingers
        }
        return IncrementalPositionHoldPlanner(
            step_deg=self.config.stiff_position_step_deg,
            max_delta_deg=self.config.stiff_position_max_delta_deg,
            active_fingers=set(self.config.active_fingers),
            active_joint_ids=active_joint_ids,
            contact_joint_angles=contact_snapshot.joint_angles,
            hold_speed=self._resolve_stiff_position_hold_speed(profile),
            hold_torque=self._resolve_stiff_position_hold_torque(profile),
            default_target_force_n=self._resolve_stiff_position_target_force(
                profile),
            stiff_position_force_drop_ratio=(
                self.config.stiff_position_force_drop_ratio),
        )

    def _resolve_stiff_position_hold_speed(
        self,
        profile: Optional[ObjectProfile],
    ) -> int:
        if (profile is not None
                and profile.stiff_position_hold_speed is not None):
            return profile.stiff_position_hold_speed
        return self.config.stiff_position_hold_speed

    def _resolve_stiff_position_hold_torque(
        self,
        profile: Optional[ObjectProfile],
    ) -> int:
        if (profile is not None
                and profile.stiff_position_hold_torque is not None):
            return profile.stiff_position_hold_torque
        return self.config.stiff_position_hold_torque

    def _resolve_stiff_position_target_force(
        self,
        profile: Optional[ObjectProfile],
    ) -> Optional[float]:
        if profile is None:
            return None
        if profile.stiff_position_hold_target_force is not None:
            return profile.stiff_position_hold_target_force
        return profile.safe_force_min

    def _create_position_hold_planner(
        self,
        profile: Optional[ObjectProfile],
    ) -> Optional[PositionHoldPlanner]:
        return PositionHoldPlanner(self.config, profile)
