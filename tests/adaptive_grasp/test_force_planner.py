import math
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.force_planner import ObjectProfile, ForcePlanner, ForceDecision
from xiaoyao.adaptive_grasp.tactile import TactileAnalysis
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
        variance=0.0, slip_risk=0.0, slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 2.0},
        total_fz=2.0,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decision = planner.compute(analysis, angles)

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
        variance=0.0, slip_risk=0.0, slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decision = planner.compute(analysis, angles)

    assert decision.is_fragile_mode is True
    # speed 应被限制：20 * 0.7 = 14
    assert decision.next_torque <= int(20 * 0.7)
