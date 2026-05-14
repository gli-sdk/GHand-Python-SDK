import math

import pytest

from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.force_reference_planner import ForceReferenceDecision
from xiaoyao.adaptive_grasp.object_profile import ObjectProfile
from xiaoyao.adaptive_grasp.position_hold_planner import PositionHoldPlanner
from xiaoyao.adaptive_grasp.tactility import PerFingerAnalysis, TactileAnalysis
from xiaoyao.dexhand import JointId, TactileSensorId


def _analysis(
    *,
    finger_fz: dict[TactileSensorId, float] | None = None,
    slip_risk: float = 0.0,
    per_finger_slip_risk: dict[TactileSensorId, float] | None = None,
    slip_confirmed: bool = False,
) -> TactileAnalysis:
    forces = finger_fz or {
        TactileSensorId.THUMB: 0.5,
        TactileSensorId.FOREFINGER: 0.5,
    }
    return TactileAnalysis(
        variance=0.0,
        slip_risk=slip_risk,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=slip_confirmed,
        finger_fz=forces,
        total_fz=sum(forces.values()),
        per_finger={
            finger: PerFingerAnalysis(
                variance=0.0,
                s_k=0.0,
                d_k=0.0,
                r_k=(per_finger_slip_risk or {}).get(finger, slip_risk),
                s_total=(per_finger_slip_risk or {}).get(finger, slip_risk),
                slip_confirmed=slip_confirmed,
                fz=fz,
                fz_filtered=fz,
            )
            for finger, fz in forces.items()
        },
    )


def _reference(
    *,
    force_refs: dict[TactileSensorId, float],
) -> ForceReferenceDecision:
    return ForceReferenceDecision(
        force_refs=force_refs,
        contact_ratios={finger: 1.0 / len(force_refs) for finger in force_refs},
        F_ref_total=sum(force_refs.values()),
    )


def _profile(*, is_fragile: bool = True) -> ObjectProfile:
    return ObjectProfile(
        name="paper_cup_test",
        weight_kg=0.01,
        safe_force_min=0.5,
        safe_force_max=3.5,
        friction_coeff=0.8,
        is_fragile=is_fragile,
        material="paper",
        hold_strategy="adaptive",
        position_hold_torque=12,
        position_hold_speed=7,
    )


def test_position_hold_planner_uses_slip_risk_per_finger():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
        K_n=0.0,
        thumb_K_MCP=0.5,
        thumb_K_PIP=0.5,
        finger_K_MCP=0.5,
        finger_K_PIP=0.5,
        delta_theta_limit=math.radians(2.0),
    )
    planner = PositionHoldPlanner(cfg, _profile(is_fragile=False))
    angles = {
        JointId.THUMB_MCP: 0.0,
        JointId.THUMB_PIP: 0.0,
        JointId.FF_MCP: 0.0,
        JointId.FF_PIP: 0.0,
    }

    decisions = planner.compute(
        _analysis(
            finger_fz={
                TactileSensorId.THUMB: 0.5,
                TactileSensorId.FOREFINGER: 0.5,
            },
            per_finger_slip_risk={
                TactileSensorId.THUMB: 1.0,
                TactileSensorId.FOREFINGER: 0.0,
            },
        ),
        angles,
        _reference(
            force_refs={
                TactileSensorId.THUMB: 0.8,
                TactileSensorId.FOREFINGER: 0.2,
            },
        ),
        dt=0.02,
    )

    assert decisions[TactileSensorId.THUMB].control_u > 0.0
    assert decisions[TactileSensorId.FOREFINGER].control_u == pytest.approx(0.0)
    assert decisions[TactileSensorId.THUMB].target_angles[JointId.THUMB_MCP] > 0.0
    assert decisions[TactileSensorId.FOREFINGER].target_angles[JointId.FF_MCP] == pytest.approx(0.0)


def test_position_hold_planner_limits_angle_step():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        K_n=0.0,
        thumb_K_MCP=0.5,
        thumb_K_PIP=0.5,
        delta_theta_limit=math.radians(2.0),
    )
    planner = PositionHoldPlanner(cfg, _profile(is_fragile=False))

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 0.0}, slip_risk=1.0),
        {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0},
        _reference(force_refs={TactileSensorId.THUMB: 1.0}),
        dt=0.02,
    )[TactileSensorId.THUMB]

    assert decision.target_angles[JointId.THUMB_MCP] == pytest.approx(math.radians(1.0))
    assert decision.target_angles[JointId.THUMB_PIP] == pytest.approx(math.radians(1.0))


def test_position_hold_planner_uses_thumb_and_finger_joint_allocation():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
        K_n=0.0,
        thumb_K_MCP=0.2,
        thumb_K_PIP=0.8,
        finger_K_MCP=0.7,
        finger_K_PIP=0.3,
        delta_theta_limit=10.0,
    )
    planner = PositionHoldPlanner(cfg, _profile(is_fragile=False))

    decisions = planner.compute(
        _analysis(
            finger_fz={
                TactileSensorId.THUMB: 0.0,
                TactileSensorId.FOREFINGER: 0.0,
            },
            slip_risk=1.0,
        ),
        {
            JointId.THUMB_MCP: 0.0,
            JointId.THUMB_PIP: 0.0,
            JointId.FF_MCP: 0.0,
            JointId.FF_PIP: 0.0,
        },
        _reference(
            force_refs={
                TactileSensorId.THUMB: 1.0,
                TactileSensorId.FOREFINGER: 1.0,
            },
        ),
        dt=0.02,
    )

    thumb = decisions[TactileSensorId.THUMB].target_angles
    forefinger = decisions[TactileSensorId.FOREFINGER].target_angles
    assert thumb[JointId.THUMB_MCP] == pytest.approx(2.0)
    assert thumb[JointId.THUMB_PIP] == pytest.approx(8.0)
    assert forefinger[JointId.FF_MCP] == pytest.approx(7.0)
    assert forefinger[JointId.FF_PIP] == pytest.approx(3.0)


def test_position_hold_planner_uses_configured_near_limit_step_scale():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        K_n=0.0,
        thumb_K_MCP=0.5,
        thumb_K_PIP=0.5,
        delta_theta_limit=math.radians(2.0),
        near_force_limit_ratio=0.5,
        near_limit_step_scale=0.25,
    )
    planner = PositionHoldPlanner(cfg, _profile(is_fragile=False))

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 2.0}, slip_risk=1.0),
        {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0},
        _reference(force_refs={TactileSensorId.THUMB: 3.0}),
        dt=0.02,
    )[TactileSensorId.THUMB]

    assert decision.near_limit is True
    assert decision.target_angles[JointId.THUMB_MCP] == pytest.approx(math.radians(0.25))
    assert decision.target_angles[JointId.THUMB_PIP] == pytest.approx(math.radians(0.25))


def test_position_hold_planner_applies_direct_slip_control():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        K_n=0.0,
        thumb_K_MCP=0.5,
        thumb_K_PIP=0.5,
    )
    planner = PositionHoldPlanner(cfg, _profile(is_fragile=False))

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 0.5}, slip_risk=1.0),
        {JointId.THUMB_MCP: 0.1, JointId.THUMB_PIP: 0.2},
        _reference(force_refs={TactileSensorId.THUMB: 0.5}),
        dt=0.02,
    )[TactileSensorId.THUMB]

    assert decision.control_u > 0.0
    assert decision.target_angles[JointId.THUMB_MCP] > 0.1
    assert decision.target_angles[JointId.THUMB_PIP] > 0.2


def test_position_hold_planner_disables_force_control_when_configured():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        enable_position_hold_force_control=False,
        thumb_K_MCP=0.5,
        thumb_K_PIP=0.5,
    )
    planner = PositionHoldPlanner(cfg, _profile(is_fragile=False))

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 0.0}, slip_risk=1.0, slip_confirmed=True),
        {JointId.THUMB_MCP: 0.1, JointId.THUMB_PIP: 0.2},
        _reference(force_refs={TactileSensorId.THUMB: 1.0}),
        dt=0.02,
    )[TactileSensorId.THUMB]

    assert decision.control_u == pytest.approx(0.0)
    assert decision.target_angles[JointId.THUMB_MCP] == pytest.approx(0.1)
    assert decision.target_angles[JointId.THUMB_PIP] == pytest.approx(0.2)


def test_direct_control_uses_slip_risk_deadband_boost_and_overlimit():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        delta_theta_limit=1.0,
        direct_slip_risk_deadband=0.2,
        direct_slip_risk_full=0.8,
        direct_slip_risk_gamma=1.0,
        direct_slip_confirmed_boost_ratio=0.5,
        K_n=1.0,
    )
    planner = PositionHoldPlanner(cfg, _profile(is_fragile=False))

    assert planner._compute_finger_direct_control_u(
        TactileSensorId.THUMB,
        _analysis(finger_fz={TactileSensorId.THUMB: 0.5}, slip_risk=0.1),
        finger_count=1,
    ) == pytest.approx(0.0)

    assert planner._compute_finger_direct_control_u(
        TactileSensorId.THUMB,
        _analysis(
            finger_fz={TactileSensorId.THUMB: 0.5},
            slip_risk=0.8,
            slip_confirmed=True,
        ),
        finger_count=1,
    ) == pytest.approx(0.6833333333333333)

    assert planner._compute_finger_direct_control_u(
        TactileSensorId.THUMB,
        _analysis(finger_fz={TactileSensorId.THUMB: 7.0}, slip_risk=0.1),
        finger_count=1,
    ) < 0.0


def test_direct_control_does_not_fall_back_to_global_slip_risk():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
        K_n=0.0,
        delta_theta_limit=1.0,
    )
    planner = PositionHoldPlanner(cfg, _profile(is_fragile=False))
    analysis = _analysis(
        finger_fz={
            TactileSensorId.THUMB: 0.5,
            TactileSensorId.FOREFINGER: 0.5,
        },
        slip_risk=1.0,
        per_finger_slip_risk={
            TactileSensorId.THUMB: 1.0,
            TactileSensorId.FOREFINGER: 0.0,
        },
    )
    assert planner._compute_finger_direct_control_u(
        TactileSensorId.FOREFINGER,
        analysis,
        finger_count=2,
    ) == pytest.approx(0.0)


def test_position_hold_planner_uses_direct_slip_curve_params():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        K_n=0.0,
        direct_slip_risk_deadband=0.2,
        direct_slip_risk_full=0.8,
        direct_slip_risk_gamma=1.0,
        thumb_K_MCP=0.5,
        thumb_K_PIP=0.5,
        delta_theta_limit=10.0,
    )
    planner = PositionHoldPlanner(cfg, _profile(is_fragile=False))

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 0.5}, slip_risk=0.5),
        {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0},
        _reference(force_refs={TactileSensorId.THUMB: 1.0}),
        dt=0.02,
    )[TactileSensorId.THUMB]

    assert decision.control_u == pytest.approx(5.0)


def test_position_hold_planner_uses_position_hold_torque_when_configured():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
    )
    profile = _profile(is_fragile=False)
    profile.position_hold_torque = 12
    planner = PositionHoldPlanner(cfg, profile)

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 0.5}),
        {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0},
        _reference(force_refs={TactileSensorId.THUMB: 0.5}),
        dt=0.02,
    )[TactileSensorId.THUMB]

    assert decision.next_torque == 12


def test_position_hold_planner_uses_position_hold_speed_when_configured():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
    )
    profile = _profile(is_fragile=False)
    profile.position_hold_speed = 7
    planner = PositionHoldPlanner(cfg, profile)

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 0.5}),
        {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0},
        _reference(force_refs={TactileSensorId.THUMB: 0.5}),
        dt=0.02,
    )[TactileSensorId.THUMB]

    assert decision.next_speed == 7


def test_position_hold_planner_requires_profile_for_position_hold_mode():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
    )
    planner = PositionHoldPlanner(cfg, profile=None)

    with pytest.raises(ValueError, match="ObjectProfile"):
        planner.compute(
            _analysis(finger_fz={TactileSensorId.THUMB: 0.5}),
            {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0},
            _reference(force_refs={TactileSensorId.THUMB: 0.5}),
            dt=0.02,
        )


def test_position_hold_planner_does_not_expose_removed_pid_path():
    planner = PositionHoldPlanner(
        AdaptiveGraspConfig(active_fingers={TactileSensorId.THUMB}),
        _profile(is_fragile=False),
    )

    removed_names = (
        "_compute_finger_control_u",
        "_compute_pid_control_u",
        "_get_or_create_pid",
        "_get_pid_param",
        "_get_pid_params",
    )

    for name in removed_names:
        assert not hasattr(planner, name)
