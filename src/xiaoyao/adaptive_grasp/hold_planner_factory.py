from dataclasses import dataclass
from typing import Optional

from .config import AdaptiveGraspConfig
from .force_reference_planner import ForceReferencePlanner
from .grasp_sequence import ContactSnapshot
from .object_profile import ObjectProfile
from .position_hold_planner import PositionHoldPlanner
from .torque_hold_planner import TorqueHoldPlanner


@dataclass(frozen=True)
class HoldPlannerBundle:
    force_reference_planner: Optional[ForceReferencePlanner] = None
    position_hold_planner: Optional[PositionHoldPlanner] = None
    torque_hold_planner: Optional[TorqueHoldPlanner] = None


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
        return HoldPlannerBundle(
            force_reference_planner=force_reference_planner,
            position_hold_planner=self._create_position_hold_planner(profile),
            torque_hold_planner=self._create_torque_hold_planner(),
        )

    def _create_position_hold_planner(
        self,
        profile: Optional[ObjectProfile],
    ) -> Optional[PositionHoldPlanner]:
        if self.config.adaptive_hold_command_mode != "position":
            return None
        return PositionHoldPlanner(self.config, profile)

    def _create_torque_hold_planner(self) -> Optional[TorqueHoldPlanner]:
        if self.config.adaptive_hold_command_mode != "torque":
            return None
        return TorqueHoldPlanner(self.config)
