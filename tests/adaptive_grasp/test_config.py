import math

import pytest

import xiaoyao.adaptive_grasp.config as config_module
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig
from xiaoyao.dexhand import JointId, TactileSensorId


def test_position_hold_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.delta_theta_limit == pytest.approx(math.radians(2.0))
    assert cfg.thumb_K_MCP == pytest.approx(0.7)
    assert cfg.thumb_K_PIP == pytest.approx(0.3)
    assert cfg.finger_K_MCP == pytest.approx(0.2)
    assert cfg.finger_K_PIP == pytest.approx(0.8)


def test_delta_theta_limit_must_be_positive():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(delta_theta_limit=0.0)


def test_position_hold_speed_and_torque_limits_removed_from_config():
    cfg = AdaptiveGraspConfig()

    assert not hasattr(cfg, "position_speed_limit")
    assert not hasattr(cfg, "position_torque_limit")
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(position_speed_limit=15)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(position_torque_limit=15)


def test_global_joint_allocation_params_removed():
    cfg = AdaptiveGraspConfig()

    assert not hasattr(cfg, "K_MCP")
    assert not hasattr(cfg, "K_PIP")
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(K_MCP=0.3)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(K_PIP=0.7)


def test_thumb_and_finger_joint_allocation_must_be_non_negative():
    for param_name in ("thumb_K_MCP", "thumb_K_PIP", "finger_K_MCP", "finger_K_PIP"):
        with pytest.raises(ValueError):
            AdaptiveGraspConfig(**{param_name: -0.1})

    cfg = AdaptiveGraspConfig(
        thumb_K_MCP=0.0,
        thumb_K_PIP=0.0,
        finger_K_MCP=0.0,
        finger_K_PIP=0.0,
    )
    assert cfg.thumb_K_MCP == pytest.approx(0.0)
    assert cfg.thumb_K_PIP == pytest.approx(0.0)
    assert cfg.finger_K_MCP == pytest.approx(0.0)
    assert cfg.finger_K_PIP == pytest.approx(0.0)


def test_thumb_and_finger_joint_allocation_can_be_configured_independently():
    cfg = AdaptiveGraspConfig(
        thumb_K_MCP=0.2,
        thumb_K_PIP=0.8,
        finger_K_MCP=0.7,
        finger_K_PIP=0.3,
    )

    assert cfg.thumb_K_MCP == pytest.approx(0.2)
    assert cfg.thumb_K_PIP == pytest.approx(0.8)
    assert cfg.finger_K_MCP == pytest.approx(0.7)
    assert cfg.finger_K_PIP == pytest.approx(0.3)


def test_release_and_pid_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.release_hold_time_s == 20.0
    assert cfg.release_open_speed == 50
    assert cfg.release_open_torque == 50
    assert cfg.release_timeout_s == 5.0


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
        AdaptiveGraspConfig(position_hold_I_min=1.0, position_hold_I_max=0.0)


def test_extended_torque_strategy_params_removed():
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(enable_phase4_ext=True)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(load_gain=1.2)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(ext_smoothing_alpha=0.5)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(ext_safety_margin_ratio=0.8)


def test_unused_params_removed():
    for param_name, value in {
        "theta_err_th": math.radians(2.0),
        "release_check_cycles": 3,
        "s_ref": 0.25,
        "fragile_speed_reduction": 0.8,
        "K_s": 1.0,
        "force_calibrate_tolerance": 0.5,
        "safety_factor": 1.5,
        "base_holding_force": 0.5,
        "K_p": 0.2,
        "K_i": 0.2,
        "K_d": 0.0,
        "I_min": -1.0,
        "I_max": 1.0,
    }.items():
        with pytest.raises(TypeError):
            AdaptiveGraspConfig(**{param_name: value})


def test_v2_params_defaults():
    cfg = AdaptiveGraspConfig()
    assert cfg.slip_detect_debounce_cycles == 3
    assert cfg.fragile_step_reduction == pytest.approx(0.5)


def test_phase_closing_torque_removed_from_config():
    cfg = AdaptiveGraspConfig()

    assert not hasattr(cfg, "phase_closing_torque")
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(phase_closing_torque=30)


def test_base_torque_and_torque_adjust_step_removed_from_config():
    cfg = AdaptiveGraspConfig()

    assert not hasattr(cfg, "base_torque")
    assert not hasattr(cfg, "torque_adjust_step")
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(base_torque=30)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(torque_adjust_step=5)


def test_slip_detect_debounce_positive():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(slip_detect_debounce_cycles=0)


def test_drop_detect_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.drop_detect_force_per_finger_n == pytest.approx(0.1)
    assert cfg.drop_detect_debounce_cycles == 6


def test_adaptive_hold_guard_defaults_are_configurable():
    cfg = AdaptiveGraspConfig()

    assert cfg.adaptive_hold_move_failure_limit == 3
    assert cfg.contact_snapshot_angle_limit == pytest.approx(math.radians(10.0))
    assert cfg.near_force_limit_ratio == pytest.approx(0.9)
    assert cfg.near_limit_step_scale == pytest.approx(0.8)
    assert cfg.closing_total_contact_threshold_n == pytest.approx(0.2)
    assert cfg.finger_touch_threshold_n == pytest.approx(0.1)
    assert cfg.thumb_aux_torque == 5
    assert cfg.tactile_sensor_update_period_s == pytest.approx(0.02)
    assert cfg.tactile_dispatch_period_s == pytest.approx(0.02)


def test_adaptive_hold_guard_constraints():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(adaptive_hold_move_failure_limit=0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(contact_snapshot_angle_limit=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(near_force_limit_ratio=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(near_force_limit_ratio=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(near_limit_step_scale=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(near_limit_step_scale=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(closing_total_contact_threshold_n=-0.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(finger_touch_threshold_n=-0.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(tactile_sensor_update_period_s=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(tactile_dispatch_period_s=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(thumb_aux_torque=-101)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(thumb_aux_torque=101)


def test_ambiguous_contact_and_torque_hold_params_removed_from_config():
    cfg = AdaptiveGraspConfig()

    assert not hasattr(cfg, "contact_threshold_z")
    assert not hasattr(cfg, "touch_detect_force_threshold_n")
    assert not hasattr(cfg, "adaptive_hold_torque")
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(contact_threshold_z=0.2)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(touch_detect_force_threshold_n=0.1)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(adaptive_hold_torque=5)


def test_drop_detect_constraints():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(drop_detect_force_per_finger_n=-0.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(drop_detect_debounce_cycles=0)


def test_default_pre_grasp_preset_is_explicit_balloon_pinch():
    cfg = AdaptiveGraspConfig()

    assert cfg.pre_grasp_preset == "balloon_pinch"
    assert cfg.pre_grasp_pose[JointId.FF_MCP] == pytest.approx(math.radians(25.0))
    assert cfg.pre_grasp_pose[JointId.FF_PIP] == pytest.approx(math.radians(25.0))
    assert cfg.pre_grasp_pose[JointId.THUMB_SWING] == pytest.approx(math.radians(80.0))
    assert cfg.pre_grasp_pose[JointId.THUMB_PIP] == pytest.approx(math.radians(5.0))


def test_config_has_no_import_time_object_pose_selector():
    assert not hasattr(config_module, "_legacy_object_pose_selector")


def test_object_specific_pre_grasp_preset_is_config_driven():
    cfg = AdaptiveGraspConfig(pre_grasp_preset="paper_cup_pinch")

    assert cfg.active_fingers == {
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
    }
    assert cfg.pre_grasp_pose[JointId.FF_MCP] == pytest.approx(math.radians(41.0))
    assert cfg.pre_grasp_pose[JointId.MF_MCP] == pytest.approx(math.radians(49.0))
    assert cfg.pre_grasp_pose[JointId.THUMB_SWING] == pytest.approx(math.radians(85.0))


def test_default_object_can_drive_default_pre_grasp_preset():
    cfg = AdaptiveGraspConfig(default_object="paper_cup")

    assert cfg.pre_grasp_preset == "paper_cup_pinch"
    assert cfg.active_fingers == {
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
    }
    assert cfg.pre_grasp_pose[JointId.FF_MCP] == pytest.approx(math.radians(41.0))


def test_explicit_pre_grasp_preset_overrides_default_object_preset():
    cfg = AdaptiveGraspConfig(
        default_object="paper_cup",
        pre_grasp_preset="balloon_pinch",
    )

    assert cfg.pre_grasp_preset == "balloon_pinch"
    assert cfg.active_fingers == {
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
    }


def test_phase_motion_defaults_are_configurable():
    cfg = AdaptiveGraspConfig()

    assert cfg.open_speed == 50
    assert cfg.open_torque == 50
    assert cfg.open_wait_s == pytest.approx(3.0)
    assert cfg.pre_grasp_speed == 50
    assert cfg.pre_grasp_torque == 50
    assert cfg.pre_grasp_wait_s == pytest.approx(5.0)


def test_phase_motion_constraints():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(open_speed=-1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(open_torque=101)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(open_wait_s=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(pre_grasp_speed=101)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(pre_grasp_torque=-1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(pre_grasp_wait_s=0.0)


def test_safety_threshold_defaults_are_configurable():
    cfg = AdaptiveGraspConfig()

    assert cfg.sensor_missing_fault_cycles == 3
    assert cfg.empty_grasp_angle_threshold == pytest.approx(math.radians(30.0))


def test_safety_threshold_constraints():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(sensor_missing_fault_cycles=0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(empty_grasp_angle_threshold=0.0)


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


def test_force_reference_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.force_ref_margin_n == pytest.approx(0.10)
    assert cfg.force_ref_slip_warning_threshold == pytest.approx(0.40)
    assert cfg.force_ref_stable_threshold == pytest.approx(0.20)
    assert cfg.force_ref_slip_gain_n_per_s == pytest.approx(0.20)
    assert cfg.force_ref_max_rise_step_n == pytest.approx(0.02)
    assert cfg.force_ref_confirmed_boost_n == pytest.approx(0.05)
    assert cfg.force_ref_decay_rate_n_per_s == pytest.approx(0.02)
    assert cfg.force_ref_stable_decay_delay_s == pytest.approx(1.0)
    assert cfg.force_ref_min_contact_ratio == pytest.approx(0.15)


def test_torque_hold_closed_loop_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.torque_hold_base_torque == 5
    assert cfg.torque_hold_K_p == pytest.approx(5.0)
    assert cfg.torque_hold_K_i == pytest.approx(0.0)
    assert cfg.torque_hold_K_d == pytest.approx(0.0)
    assert cfg.torque_hold_I_min == pytest.approx(-1.0)
    assert cfg.torque_hold_I_max == pytest.approx(1.0)


def test_force_ref_min_contact_ratio_must_fit_active_fingers():
    with pytest.raises(ValueError, match="force_ref_min_contact_ratio"):
        AdaptiveGraspConfig(
            active_fingers={
                TactileSensorId.THUMB,
                TactileSensorId.FOREFINGER,
                TactileSensorId.MIDDLE_FINGER,
            },
            force_ref_min_contact_ratio=0.40,
        )
