import math
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.object_profile import ObjectProfile, ObjectProfileRegistry
from xiaoyao.adaptive_grasp.force_planner import ForcePlanner, ForceDecision
from xiaoyao.adaptive_grasp.tactility import TactileAnalysis, PerFingerAnalysis
from xiaoyao.dexhand import TactileSensorId, JointId


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
    # F_init = 0.5 * 9.8 * 1.5 + 1.0 = 8.35
    assert planner.F_init == pytest.approx(8.35, abs=0.01)


def test_force_planner_pid_around_normal_force():
    cfg = AdaptiveGraspConfig(
        K_p=1.0, K_i=0.0, K_d=0.0,
        max_normal_force_per_finger=5.0,
        control_period_s=0.01,
    )
    profile = ObjectProfile(
        name="test", weight_kg=0.1, material="plastic",
        safe_force_min=1.0, safe_force_max=10.0,
        friction_coeff=0.4, is_fragile=False,
    )
    planner = ForcePlanner(cfg, profile)

    analysis = TactileAnalysis(
        variance=0.0, slip_risk=0.0, direction_distance=0.0, friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 2.0},
        total_fz=2.0,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decisions = planner.compute(analysis, angles)
    decision = decisions[TactileSensorId.THUMB]

    # F_init = 0.1*9.8*1.5 + 0.5 = 1.97；单指 F_n,ref ≈ 1.97
    # e = 1.97 - 2.0 = -0.03；u_pid = -0.03；u_ff = 0
    # control_u 应为负（力略大，应卸力）
    assert decision.control_u < 0


def test_fragile_mode_limits_speed_and_step():
    cfg = AdaptiveGraspConfig(
        position_speed_limit=20,
        delta_theta_limit=math.radians(2.0),
        fragile_speed_reduction=0.7,
        fragile_step_reduction=0.5,
    )
    profile = ObjectProfile(
        name="tofu", weight_kg=0.05, material="tofu",
        safe_force_min=0.5, safe_force_max=3.0,
        friction_coeff=0.2, is_fragile=True,
    )
    planner = ForcePlanner(cfg, profile)
    assert planner.is_fragile_mode is True

    analysis = TactileAnalysis(
        variance=0.0, slip_risk=0.0, direction_distance=0.0, friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decisions = planner.compute(analysis, angles)
    decision = decisions[TactileSensorId.THUMB]

    assert decision.is_fragile_mode is True
    # speed 应被限制：20 * 0.7 = 14
    assert decision.next_torque <= int(20 * 0.7)


def test_per_finger_independent_control():
    cfg = AdaptiveGraspConfig(
        K_p=1.0, K_i=0.0, K_d=0.0,
        max_normal_force_per_finger=5.0,
        control_period_s=0.01,
    )
    profile = ObjectProfile(
        name="test", weight_kg=0.2, material="plastic",
        safe_force_min=1.0, safe_force_max=10.0,
        friction_coeff=0.4, is_fragile=False,
    )
    planner = ForcePlanner(cfg, profile)
    # F_init = 0.2*9.8*1.5 + 0.5 = 3.44；双指 => F_n,ref ≈ 1.72

    analysis = TactileAnalysis(
        variance=0.0, slip_risk=0.0, direction_distance=0.0, friction_utilization=0.0,
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
        JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0,
        JointId.FF_MCP: 0.0, JointId.FF_PIP: 0.0,
    }
    decisions = planner.compute(analysis, angles)

    thumb_mcp = decisions[TactileSensorId.THUMB].target_angles[JointId.THUMB_MCP]
    thumb_pip = decisions[TactileSensorId.THUMB].target_angles[JointId.THUMB_PIP]
    ff_mcp = decisions[TactileSensorId.FOREFINGER].target_angles[JointId.FF_MCP]
    ff_pip = decisions[TactileSensorId.FOREFINGER].target_angles[JointId.FF_PIP]

    # THUMB: F_n=2.0 > F_n,ref≈1.72 => 卸力（角度减小）
    assert thumb_mcp < 0.0
    assert thumb_pip < 0.0
    # FOREFINGER: F_n=0.5 < F_n,ref≈1.72 => 收紧（角度增大）
    assert ff_mcp > 0.0
    assert ff_pip > 0.0


def test_registry_lookup():
    profile = ObjectProfileRegistry.get("tofu")
    assert profile is not None
    assert profile.is_fragile is True
    assert "tofu" in ObjectProfileRegistry.list_names()
