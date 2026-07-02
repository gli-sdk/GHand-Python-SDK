import math
from dataclasses import MISSING

import pytest

import adaptive_grasp.config as config_module
import adaptive_grasp.grasp_presets as preset_module
from adaptive_grasp import AdaptiveGraspConfig
from ghand import JointId, TactileSensorId


def _config_default(name: str):
    field = AdaptiveGraspConfig.__dataclass_fields__[name]
    if field.default is not MISSING:
        return field.default
    return field.default_factory()


def _preset_degrees(preset: str, joint_id: JointId) -> float:
    return preset_module.PRE_GRASP_PRESET_DEGREE[preset][joint_id]


def test_position_hold_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.enable_position_hold_force_control is _config_default("enable_position_hold_force_control")
    assert cfg.position_hold_max_step_rad == pytest.approx(_config_default("position_hold_max_step_rad"))
    assert cfg.thumb_mcp_step_ratio == pytest.approx(_config_default("thumb_mcp_step_ratio"))
    assert cfg.thumb_pip_step_ratio == pytest.approx(_config_default("thumb_pip_step_ratio"))
    assert cfg.finger_mcp_step_ratio == pytest.approx(_config_default("finger_mcp_step_ratio"))
    assert cfg.finger_pip_step_ratio == pytest.approx(_config_default("finger_pip_step_ratio"))


def test_position_hold_max_step_rad_must_be_positive():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(position_hold_max_step_rad=0.0)


def test_position_hold_force_control_flag_must_be_bool():
    cfg = AdaptiveGraspConfig(enable_position_hold_force_control=False)
    assert cfg.enable_position_hold_force_control is False

    with pytest.raises(ValueError):
        AdaptiveGraspConfig(enable_position_hold_force_control=1)


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
    for param_name in (
        "thumb_mcp_step_ratio",
        "thumb_pip_step_ratio",
        "finger_mcp_step_ratio",
        "finger_pip_step_ratio",
    ):
        with pytest.raises(ValueError):
            AdaptiveGraspConfig(**{param_name: -0.1})

    cfg = AdaptiveGraspConfig(
        thumb_mcp_step_ratio=0.0,
        thumb_pip_step_ratio=0.0,
        finger_mcp_step_ratio=0.0,
        finger_pip_step_ratio=0.0,
    )
    assert cfg.thumb_mcp_step_ratio == pytest.approx(0.0)
    assert cfg.thumb_pip_step_ratio == pytest.approx(0.0)
    assert cfg.finger_mcp_step_ratio == pytest.approx(0.0)
    assert cfg.finger_pip_step_ratio == pytest.approx(0.0)


def test_thumb_and_finger_joint_allocation_can_be_configured_independently():
    cfg = AdaptiveGraspConfig(
        thumb_mcp_step_ratio=0.2,
        thumb_pip_step_ratio=0.8,
        finger_mcp_step_ratio=0.7,
        finger_pip_step_ratio=0.3,
    )

    assert cfg.thumb_mcp_step_ratio == pytest.approx(0.2)
    assert cfg.thumb_pip_step_ratio == pytest.approx(0.8)
    assert cfg.finger_mcp_step_ratio == pytest.approx(0.7)
    assert cfg.finger_pip_step_ratio == pytest.approx(0.3)


def test_release_and_pid_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.release_hold_time_s == pytest.approx(_config_default("release_hold_time_s"))
    assert cfg.release_open_speed == _config_default("release_open_speed")
    assert cfg.release_open_torque == _config_default("release_open_torque")
    assert cfg.release_timeout_s == pytest.approx(_config_default("release_timeout_s"))


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
    assert cfg.slip_detect_debounce_cycles == _config_default("slip_detect_debounce_cycles")
    assert cfg.fragile_step_reduction == pytest.approx(_config_default("fragile_step_reduction"))


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

    assert cfg.drop_detect_force_per_finger_n == pytest.approx(_config_default("drop_detect_force_per_finger_n"))
    assert cfg.drop_detect_debounce_cycles == _config_default("drop_detect_debounce_cycles")


def test_adaptive_hold_guard_defaults_are_configurable():
    cfg = AdaptiveGraspConfig()

    assert cfg.adaptive_hold_move_failure_limit == _config_default("adaptive_hold_move_failure_limit")
    assert cfg.contact_angle_guard_margin_rad == pytest.approx(_config_default("contact_angle_guard_margin_rad"))
    assert cfg.force_limit_slowdown_ratio == pytest.approx(_config_default("force_limit_slowdown_ratio"))
    assert cfg.force_limit_slowdown_step_scale == pytest.approx(_config_default("force_limit_slowdown_step_scale"))
    assert cfg.closing_total_contact_threshold_n == pytest.approx(
        _config_default("closing_total_contact_threshold_n")
    )
    assert cfg.finger_touch_threshold_n == pytest.approx(_config_default("finger_touch_threshold_n"))
    assert cfg.thumb_aux_torque == _config_default("thumb_aux_torque")
    assert cfg.tactile_sensor_update_period_s == pytest.approx(
        _config_default("tactile_sensor_update_period_s")
    )
    assert cfg.tactile_dispatch_period_s == pytest.approx(_config_default("tactile_dispatch_period_s"))


def test_adaptive_hold_guard_constraints():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(adaptive_hold_move_failure_limit=0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(contact_angle_guard_margin_rad=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(force_limit_slowdown_ratio=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(force_limit_slowdown_ratio=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(force_limit_slowdown_step_scale=0.0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(force_limit_slowdown_step_scale=1.1)
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
    expected_preset = preset_module.OBJECT_PRE_GRASP_PRESET.get(
        _config_default("default_object"),
        "balloon_pinch",
    )

    assert cfg.pre_grasp_preset == expected_preset
    assert cfg.pre_grasp_pose[JointId.FF_MCP] == pytest.approx(
        math.radians(_preset_degrees(expected_preset, JointId.FF_MCP))
    )
    assert cfg.pre_grasp_pose[JointId.FF_PIP] == pytest.approx(
        math.radians(_preset_degrees(expected_preset, JointId.FF_PIP))
    )
    assert cfg.pre_grasp_pose[JointId.THUMB_SWING] == pytest.approx(
        math.radians(_preset_degrees(expected_preset, JointId.THUMB_SWING))
    )
    assert cfg.pre_grasp_pose[JointId.THUMB_PIP] == pytest.approx(
        math.radians(_preset_degrees(expected_preset, JointId.THUMB_PIP))
    )


def test_config_has_no_import_time_object_pose_selector():
    assert not hasattr(config_module, "_legacy_object_pose_selector")


def test_object_specific_pre_grasp_preset_is_config_driven():
    preset = "paper_cup_pinch"
    cfg = AdaptiveGraspConfig(pre_grasp_preset=preset)

    assert cfg.active_fingers == preset_module.PRESET_ACTIVE_FINGERS[preset]
    assert cfg.pre_grasp_pose[JointId.FF_MCP] == pytest.approx(
        math.radians(_preset_degrees(preset, JointId.FF_MCP))
    )
    assert cfg.pre_grasp_pose[JointId.MF_MCP] == pytest.approx(
        math.radians(_preset_degrees(preset, JointId.MF_MCP))
    )
    assert cfg.pre_grasp_pose[JointId.THUMB_SWING] == pytest.approx(
        math.radians(_preset_degrees(preset, JointId.THUMB_SWING))
    )


def test_pre_grasp_preset_requires_explicit_active_finger_mapping(monkeypatch):
    preset = "unmapped_test_preset"
    monkeypatch.setitem(
        preset_module.PRE_GRASP_PRESET_DEGREE,
        preset,
        preset_module.pose_degrees(ff_mcp=20.0),
    )

    with pytest.raises(ValueError) as exc_info:
        AdaptiveGraspConfig(pre_grasp_preset=preset)
    message = str(exc_info.value)
    assert preset in message
    assert "PRESET_ACTIVE_FINGERS" in message
    assert "active_fingers explicitly" in message


def test_default_object_can_drive_default_pre_grasp_preset():
    default_object = "paper_cup"
    expected_preset = preset_module.OBJECT_PRE_GRASP_PRESET[default_object]
    cfg = AdaptiveGraspConfig(default_object=default_object)

    assert cfg.pre_grasp_preset == expected_preset
    assert cfg.active_fingers == preset_module.PRESET_ACTIVE_FINGERS[expected_preset]
    assert cfg.pre_grasp_pose[JointId.FF_MCP] == pytest.approx(
        math.radians(_preset_degrees(expected_preset, JointId.FF_MCP))
    )


def test_explicit_pre_grasp_preset_overrides_default_object_preset():
    cfg = AdaptiveGraspConfig(
        default_object="paper_cup",
        pre_grasp_preset="balloon_pinch",
    )

    assert cfg.pre_grasp_preset == "balloon_pinch"
    assert cfg.active_fingers == {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
    }


def test_phase_motion_defaults_are_configurable():
    cfg = AdaptiveGraspConfig()

    assert cfg.open_speed == _config_default("open_speed")
    assert cfg.open_torque == _config_default("open_torque")
    assert cfg.pre_grasp_speed == _config_default("pre_grasp_speed")
    assert cfg.pre_grasp_torque == _config_default("pre_grasp_torque")


def test_phase_motion_wait_fields_are_not_public_config():
    assert "open_wait_s" not in AdaptiveGraspConfig.__dataclass_fields__
    assert "pre_grasp_wait_s" not in AdaptiveGraspConfig.__dataclass_fields__

    with pytest.raises(TypeError):
        AdaptiveGraspConfig(open_wait_s=1.0)
    with pytest.raises(TypeError):
        AdaptiveGraspConfig(pre_grasp_wait_s=1.0)


def test_phase_motion_constraints():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(open_speed=-1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(open_torque=101)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(pre_grasp_speed=101)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(pre_grasp_torque=-1)


def test_safety_threshold_defaults_are_configurable():
    cfg = AdaptiveGraspConfig()

    assert cfg.sensor_missing_fault_cycles == _config_default("sensor_missing_fault_cycles")
    assert cfg.empty_grasp_angle_threshold == pytest.approx(_config_default("empty_grasp_angle_threshold"))


def test_safety_threshold_constraints():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(sensor_missing_fault_cycles=0)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(empty_grasp_angle_threshold=0.0)


def test_variance_direction_friction_weights_sum_to_one():
    cfg = AdaptiveGraspConfig()
    assert cfg.slip_variance_weight == pytest.approx(_config_default("slip_variance_weight"))
    assert cfg.slip_direction_weight == pytest.approx(_config_default("slip_direction_weight"))
    assert cfg.slip_friction_weight == pytest.approx(_config_default("slip_friction_weight"))
    total = cfg.slip_variance_weight + cfg.slip_direction_weight + cfg.slip_friction_weight
    assert total == pytest.approx(1.0)


def test_weight_bounds_and_normalization():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(slip_variance_weight=-0.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(slip_direction_weight=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(slip_friction_weight=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(
            slip_variance_weight=0.5,
            slip_direction_weight=0.5,
            slip_friction_weight=0.5,
        )


def test_default_friction_coeff():
    cfg = AdaptiveGraspConfig()
    assert cfg.default_friction_coeff == pytest.approx(_config_default("default_friction_coeff"))
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(default_friction_coeff=0.0)


def test_force_reference_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.force_ref_margin_n == pytest.approx(_config_default("force_ref_margin_n"))
    assert cfg.force_ref_slip_warning_threshold == pytest.approx(
        _config_default("force_ref_slip_warning_threshold")
    )
    assert cfg.force_ref_stable_threshold == pytest.approx(_config_default("force_ref_stable_threshold"))
    assert cfg.force_ref_slip_gain_n_per_s == pytest.approx(_config_default("force_ref_slip_gain_n_per_s"))
    assert cfg.force_ref_max_rise_step_n == pytest.approx(_config_default("force_ref_max_rise_step_n"))
    assert cfg.force_ref_confirmed_boost_n == pytest.approx(_config_default("force_ref_confirmed_boost_n"))
    assert cfg.force_ref_decay_rate_n_per_s == pytest.approx(_config_default("force_ref_decay_rate_n_per_s"))
    assert cfg.force_ref_stable_decay_delay_s == pytest.approx(
        _config_default("force_ref_stable_decay_delay_s")
    )
    assert cfg.force_ref_min_contact_ratio == pytest.approx(_config_default("force_ref_min_contact_ratio"))


def test_torque_hold_closed_loop_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.torque_hold_base_torque == _config_default("torque_hold_base_torque")
    assert cfg.torque_hold_K_p == pytest.approx(_config_default("torque_hold_K_p"))
    assert cfg.torque_hold_K_i == pytest.approx(_config_default("torque_hold_K_i"))
    assert cfg.torque_hold_K_d == pytest.approx(_config_default("torque_hold_K_d"))
    assert cfg.torque_hold_I_min == pytest.approx(_config_default("torque_hold_I_min"))
    assert cfg.torque_hold_I_max == pytest.approx(_config_default("torque_hold_I_max"))


def test_force_ref_min_contact_ratio_must_fit_active_fingers():
    with pytest.raises(ValueError, match="force_ref_min_contact_ratio"):
        AdaptiveGraspConfig(
            active_fingers={
                TactileSensorId.THUMB,
                TactileSensorId.FF,
                TactileSensorId.MF,
            },
            force_ref_min_contact_ratio=0.40,
        )
