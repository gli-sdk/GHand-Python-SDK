import math

import pytest

from xiaoyao.adaptive_grasp import AdaptiveGraspConfig


def test_position_hold_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.position_speed_limit == 20
    assert cfg.position_torque_limit == 35
    assert cfg.delta_theta_limit == pytest.approx(math.radians(2.0))
    assert cfg.K_MCP == pytest.approx(0.5)
    assert cfg.K_PIP == pytest.approx(0.5)


def test_delta_theta_limit_must_be_positive():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(delta_theta_limit=0.0)


def test_position_speed_limit_bounds():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(position_speed_limit=-1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(position_speed_limit=101)


def test_position_torque_limit_bounds():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(position_torque_limit=-1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(position_torque_limit=101)


def test_k_allocation_must_be_normalized():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(K_MCP=-0.1, K_PIP=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(K_MCP=0.4, K_PIP=0.4)


def test_release_and_pid_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.release_hold_time_s == 20.0
    assert cfg.release_open_speed == 30
    assert cfg.release_open_torque == 30
    assert cfg.release_timeout_s == 5.0
    assert cfg.release_check_cycles == 3
    assert cfg.s_ref == pytest.approx(0.25)


def test_release_and_pid_constraints():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(release_hold_time_s=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(release_open_speed=101)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(release_open_torque=-1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(release_timeout_s=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(release_check_cycles=0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(s_ref=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(I_min=1.0, I_max=0.0)


def test_extended_torque_strategy_params_removed():
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(enable_phase4_ext=True)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(load_gain=1.2)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(ext_smoothing_alpha=0.5)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(ext_safety_margin_ratio=0.8)


def test_v2_params_defaults():
    cfg = AdaptiveGraspConfig()
    assert cfg.safety_factor == pytest.approx(1.5)
    assert cfg.base_holding_force == pytest.approx(0.5)
    assert cfg.slip_detect_debounce_cycles == 3
    assert cfg.fragile_speed_reduction == pytest.approx(0.7)
    assert cfg.fragile_step_reduction == pytest.approx(0.5)


def test_safety_factor_bounds():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(safety_factor=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(safety_factor=2.1)


def test_slip_detect_debounce_positive():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(slip_detect_debounce_cycles=0)


def test_variance_direction_friction_weights_sum_to_one():
    cfg = AdaptiveGraspConfig()
    assert cfg.variance_weight == pytest.approx(0.5)
    assert cfg.direction_weight == pytest.approx(0.3)
    assert cfg.friction_weight == pytest.approx(0.2)
    total = cfg.variance_weight + cfg.direction_weight + cfg.friction_weight
    assert total == pytest.approx(1.0)


def test_weight_bounds_and_normalization():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(variance_weight=-0.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(direction_weight=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(friction_weight=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(variance_weight=0.5, direction_weight=0.5, friction_weight=0.5)


def test_default_friction_coeff():
    cfg = AdaptiveGraspConfig()
    assert cfg.default_friction_coeff == pytest.approx(0.7)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(default_friction_coeff=0.0)
