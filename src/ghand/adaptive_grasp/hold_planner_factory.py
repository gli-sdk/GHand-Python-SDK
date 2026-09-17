# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

from typing import Optional

from .config import AdaptiveGraspConfig, HoldCommandMode
from .force_reference_planner import ForceReferencePlanner
from .grasp_sequence import ContactSnapshot
from .object_profile import ObjectProfile
from .incremental_position_hold_planner import IncrementalPositionHoldPlanner
from .position_hold_planner import PositionHoldPlanner
from .utils import JOINT_TO_FINGER


def create_hold_planners(
    config: AdaptiveGraspConfig,
    profile: Optional[ObjectProfile],
    contact_snapshot: Optional[ContactSnapshot],
) -> tuple[
    Optional[ForceReferencePlanner],
    Optional[PositionHoldPlanner],
    Optional[IncrementalPositionHoldPlanner],
]:
    if contact_snapshot is None:
        return None, None, None

    force_reference_planner = ForceReferencePlanner(
        config,
        profile,
        contact_snapshot,
    )
    if config.hold_command_mode is HoldCommandMode.POSITION:
        return force_reference_planner, PositionHoldPlanner(config, profile), None

    if config.hold_command_mode is HoldCommandMode.STIFF_POSITION:
        active_joint_ids = {
            joint_id
            for joint_id, finger in JOINT_TO_FINGER.items()
            if finger in config.active_fingers
        }
        return (
            force_reference_planner,
            None,
            IncrementalPositionHoldPlanner(
                step_deg=config.stiff_position_step_deg,
                max_delta_deg=config.stiff_position_max_delta_deg,
                active_fingers=set(config.active_fingers),
                active_joint_ids=active_joint_ids,
                contact_joint_angles=contact_snapshot.joint_angles,
                hold_speed=(
                    profile.stiff_position_hold_speed
                    if profile is not None and profile.stiff_position_hold_speed is not None
                    else config.stiff_position_hold_speed
                ),
                hold_current=(
                    profile.stiff_position_hold_current
                    if profile is not None and profile.stiff_position_hold_current is not None
                    else config.stiff_position_hold_current
                ),
                default_target_force_n=(
                    None
                    if profile is None
                    else profile.stiff_position_hold_target_force or profile.safe_force_min
                ),
                stiff_position_force_drop_ratio=config.stiff_position_force_drop_ratio,
            ),
        )

    raise ValueError(
        "hold_command_mode must be HoldCommandMode.POSITION "
        "or HoldCommandMode.STIFF_POSITION")
