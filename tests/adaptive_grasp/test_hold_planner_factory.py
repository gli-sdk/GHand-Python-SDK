from adaptive_grasp.config import AdaptiveGraspConfig
from adaptive_grasp.grasp_sequence import ContactSnapshot
from adaptive_grasp.hold_planner_factory import HoldPlannerFactory
from adaptive_grasp.object_profile import ObjectProfile
from adaptive_grasp.position_hold_planner import PositionHoldPlanner
from adaptive_grasp.torque_hold_planner import TorqueHoldPlanner
from adaptive_grasp.force_reference_planner import ForceReferencePlanner
from xiaoyao.dexhand import JointId, TactileSensorId


def _profile() -> ObjectProfile:
    return ObjectProfile(
        name="paper_cup_test",
        weight_kg=0.01,
        safe_force_min=0.5,
        safe_force_max=3.5,
        friction_coeff=0.8,
        is_fragile=True,
        material="paper",
        position_hold_torque=5,
        position_hold_speed=5,
    )


def _snapshot() -> ContactSnapshot:
    return ContactSnapshot(
        joint_angles={JointId.THUMB_PIP: 0.12},
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
        torque=5,
        reason="force_threshold",
        timestamp_s=1.0,
    )


def test_hold_planner_factory_creates_torque_mode_planners_from_contact_snapshot():
    cfg = AdaptiveGraspConfig(
        hold_command_mode="torque",
        active_fingers={TactileSensorId.THUMB},
    )

    planners = HoldPlannerFactory(cfg).create(_profile(), _snapshot())

    assert isinstance(planners.force_reference_planner, ForceReferencePlanner)
    assert isinstance(planners.torque_hold_planner, TorqueHoldPlanner)
    assert planners.position_hold_planner is None


def test_hold_planner_factory_creates_position_mode_planners_from_contact_snapshot():
    cfg = AdaptiveGraspConfig(
        hold_command_mode="position",
        active_fingers={TactileSensorId.THUMB},
    )

    planners = HoldPlannerFactory(cfg).create(_profile(), _snapshot())

    assert isinstance(planners.force_reference_planner, ForceReferencePlanner)
    assert isinstance(planners.position_hold_planner, PositionHoldPlanner)
    assert planners.torque_hold_planner is None


def test_hold_planner_factory_returns_empty_bundle_without_contact_snapshot():
    cfg = AdaptiveGraspConfig(active_fingers={TactileSensorId.THUMB})

    planners = HoldPlannerFactory(cfg).create(_profile(), contact_snapshot=None)

    assert planners.force_reference_planner is None
    assert planners.position_hold_planner is None
    assert planners.torque_hold_planner is None
