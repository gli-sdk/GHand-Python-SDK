import math

import pytest

from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig, PerFingerPidConfig
from xiaoyao.adaptive_grasp.force_planner import ForcePlanner
from xiaoyao.adaptive_grasp.object_profile import ObjectProfile, ObjectProfileRegistry
from xiaoyao.adaptive_grasp.tactility import PerFingerAnalysis, TactileAnalysis
from xiaoyao.dexhand import JointId, TactileSensorId


def test_object_profile_f_init_calculation():
    profile = ObjectProfile(
        name="metal_block",
        weight_kg=0.5,
        material="metal",
        safe_force_min=2.0,
        safe_force_max=15.0,
        friction_coeff=0.3,
        is_fragile=False,
    )
    cfg = AdaptiveGraspConfig(safety_factor=1.5, base_holding_force=1.0)
    planner = ForcePlanner(cfg, profile)

    assert planner.F_init == pytest.approx(15.0, abs=0.01)


def test_force_planner_pid_around_normal_force():
    cfg = AdaptiveGraspConfig(
        K_p=1.0,
        K_i=0.0,
        K_d=0.0,
        max_normal_force_per_finger=5.0,
        control_period_s=0.01,
    )
    profile = ObjectProfile(
        name="test",
        weight_kg=0.1,
        material="plastic",
        safe_force_min=1.0,
        safe_force_max=10.0,
        friction_coeff=0.4,
        is_fragile=False,
        hold_strategy="adaptive",
    )
    planner = ForcePlanner(cfg, profile)

    analysis = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 2.0},
        total_fz=2.0,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decisions = planner.compute(analysis, angles)

    assert decisions[TactileSensorId.THUMB].control_u > 0


def test_force_planner_uses_slip_risk_feedforward_from_design():
    cfg = AdaptiveGraspConfig(
        K_s=0.2,
        K_n=0.0,
        K_p=0.0,
        K_i=0.0,
        K_d=0.0,
        control_period_s=0.01,
    )
    planner = ForcePlanner(cfg, None)

    control_u = planner._compute_pid_control_u(
        TactileSensorId.THUMB,
        s_k=0.75,
        fz=0.5,
        fz_limit=5.0,
        F_n_ref=1.0,
        dt=0.01,
    )

    assert control_u == pytest.approx(0.15)


def test_force_planner_uses_normal_force_overlimit_feedforward():
    cfg = AdaptiveGraspConfig(
        K_s=0.0,
        K_n=1.0,
        K_p=0.0,
        K_i=0.0,
        K_d=0.0,
        control_period_s=0.01,
    )
    planner = ForcePlanner(cfg, None)

    control_u = planner._compute_pid_control_u(
        TactileSensorId.THUMB,
        s_k=0.0,
        fz=3.0,
        fz_limit=2.0,
        F_n_ref=3.0,
        dt=0.01,
    )

    assert control_u == pytest.approx(-0.5)


def test_per_finger_pid_overrides_only_configured_finger():
    cfg = AdaptiveGraspConfig(
        K_p=2.0,
        K_i=0.0,
        K_d=0.0,
        control_period_s=0.01,
        per_finger_pid={
            TactileSensorId.THUMB: PerFingerPidConfig(K_p=0.1),
        },
    )
    planner = ForcePlanner(cfg, None)

    thumb_u = planner._compute_pid_control_u(
        TactileSensorId.THUMB,
        s_k=0.0,
        fz=0.5,
        fz_limit=5.0,
        F_n_ref=1.0,
        dt=0.01,
    )
    forefinger_u = planner._compute_pid_control_u(
        TactileSensorId.FOREFINGER,
        s_k=0.0,
        fz=0.5,
        fz_limit=5.0,
        F_n_ref=1.0,
        dt=0.01,
    )

    assert thumb_u == pytest.approx(0.05)
    assert forefinger_u == pytest.approx(1.0)


def test_fragile_mode_limits_torque_and_step():
    cfg = AdaptiveGraspConfig(
        position_torque_limit=20,
        delta_theta_limit=math.radians(2.0),
        fragile_torque_reduction=0.7,
        fragile_step_reduction=0.5,
    )
    profile = ObjectProfile(
        name="tofu",
        weight_kg=0.05,
        material="tofu",
        safe_force_min=0.5,
        safe_force_max=3.0,
        friction_coeff=0.2,
        is_fragile=True,
    )
    planner = ForcePlanner(cfg, profile)
    assert planner.is_fragile_mode is True

    analysis = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decision = planner.compute(analysis, angles)[TactileSensorId.THUMB]

    assert decision.is_fragile_mode is True
    assert decision.next_torque <= int(20 * 0.7)


def test_hold_strategy_none_defaults_to_fixed():
    profile = ObjectProfile(
        name="unknown",
        weight_kg=0.1,
        material="unknown",
        safe_force_min=0.5,
        safe_force_max=5.0,
        friction_coeff=0.8,
        is_fragile=False,
        hold_strategy=None,
    )
    planner = ForcePlanner(AdaptiveGraspConfig(), profile)

    assert planner._apply_hold_strategy(control_u=0.1, slip_confirmed=True) == pytest.approx(0.0)


def test_per_finger_independent_control():
    cfg = AdaptiveGraspConfig(
        K_p=1.0,
        K_i=0.0,
        K_d=0.0,
        max_normal_force_per_finger=5.0,
        control_period_s=0.01,
    )
    profile = ObjectProfile(
        name="test",
        weight_kg=0.2,
        material="plastic",
        safe_force_min=1.0,
        safe_force_max=10.0,
        friction_coeff=0.4,
        is_fragile=False,
        hold_strategy="adaptive",
    )
    planner = ForcePlanner(cfg, profile)

    analysis = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 2.0, TactileSensorId.FOREFINGER: 0.5},
        total_fz=2.5,
        per_finger={
            TactileSensorId.THUMB: PerFingerAnalysis(
                variance=0.0, s_k=0.0, d_k=0.0, r_k=0.0, s_total=0.0,
                slip_confirmed=False, fz=2.0,
            ),
            TactileSensorId.FOREFINGER: PerFingerAnalysis(
                variance=0.0, s_k=0.0, d_k=0.0, r_k=0.0, s_total=0.0,
                slip_confirmed=False, fz=0.5,
            ),
        },
    )
    angles = {
        JointId.THUMB_MCP: 0.0,
        JointId.THUMB_PIP: 0.0,
        JointId.FF_MCP: 0.0,
        JointId.FF_PIP: 0.0,
    }
    decisions = planner.compute(analysis, angles)

    assert decisions[TactileSensorId.THUMB].target_angles[JointId.THUMB_MCP] > 0.0
    assert decisions[TactileSensorId.THUMB].target_angles[JointId.THUMB_PIP] > 0.0
    assert decisions[TactileSensorId.FOREFINGER].target_angles[JointId.FF_MCP] > 0.0
    assert decisions[TactileSensorId.FOREFINGER].target_angles[JointId.FF_PIP] > 0.0


def test_registry_lookup():
    profile = ObjectProfileRegistry.get("tofu")
    assert profile is not None
    assert profile.is_fragile is True
    assert "tofu" in ObjectProfileRegistry.list_names()


def test_force_planner_uses_only_contacting_active_fingers_for_force_split():
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="five_finger_grasp",
        K_p=1.0,
        K_i=0.0,
        K_d=0.0,
        control_period_s=0.01,
    )
    profile = ObjectProfile(
        name="test",
        weight_kg=0.2,
        material="plastic",
        safe_force_min=1.0,
        safe_force_max=10.0,
        friction_coeff=0.4,
        is_fragile=False,
        hold_strategy="adaptive",
    )
    planner = ForcePlanner(cfg, profile)

    analysis = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={
            TactileSensorId.THUMB: 1.0,
            TactileSensorId.FOREFINGER: 1.0,
            TactileSensorId.MIDDLE_FINGER: 0.0,
            TactileSensorId.RING_FINGER: 0.0,
            TactileSensorId.LITTLE_FINGER: 0.0,
        },
        total_fz=2.0,
        per_finger={
            TactileSensorId.THUMB: PerFingerAnalysis(
                variance=0.0, s_k=0.0, d_k=0.0, r_k=0.0, s_total=0.0,
                slip_confirmed=False, fz=1.0,
            ),
            TactileSensorId.FOREFINGER: PerFingerAnalysis(
                variance=0.0, s_k=0.0, d_k=0.0, r_k=0.0, s_total=0.0,
                slip_confirmed=False, fz=1.0,
            ),
            TactileSensorId.MIDDLE_FINGER: PerFingerAnalysis(
                variance=0.0, s_k=0.0, d_k=0.0, r_k=0.0, s_total=0.0,
                slip_confirmed=False, fz=0.0,
            ),
            TactileSensorId.RING_FINGER: PerFingerAnalysis(
                variance=0.0, s_k=0.0, d_k=0.0, r_k=0.0, s_total=0.0,
                slip_confirmed=False, fz=0.0,
            ),
            TactileSensorId.LITTLE_FINGER: PerFingerAnalysis(
                variance=0.0, s_k=0.0, d_k=0.0, r_k=0.0, s_total=0.0,
                slip_confirmed=False, fz=0.0,
            ),
        },
    )
    angles = {
        JointId.THUMB_MCP: 0.0,
        JointId.THUMB_PIP: 0.0,
        JointId.FF_MCP: 0.0,
        JointId.FF_PIP: 0.0,
        JointId.MF_MCP: 0.0,
        JointId.MF_PIP: 0.0,
        JointId.RF_MCP: 0.0,
        JointId.RF_PIP: 0.0,
        JointId.LF_MCP: 0.0,
        JointId.LF_PIP: 0.0,
    }

    decisions = planner.compute(analysis, angles)

    assert decisions[TactileSensorId.THUMB].target_angles[JointId.THUMB_MCP] > 0.0
    assert decisions[TactileSensorId.FOREFINGER].target_angles[JointId.FF_MCP] > 0.0


def test_force_planner_uses_monotonic_time(monkeypatch):
    cfg = AdaptiveGraspConfig(control_period_s=0.01)
    planner = ForcePlanner(cfg, None)

    monkeypatch.setattr("xiaoyao.adaptive_grasp.force_planner.time.time", lambda: 999.0)

    analysis = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 1.0},
        total_fz=1.0,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decisions = planner.compute(analysis, angles)
    assert math.isfinite(decisions[TactileSensorId.THUMB].control_u)
