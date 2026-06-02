import pytest

from adaptive_grasp.config import AdaptiveGraspConfig
from adaptive_grasp.grasp_presets import PRESET_ACTIVE_FINGERS
from adaptive_grasp.demo_config import (
    DEMO_SCENES,
    DemoRuntimeConfig,
    HOLD_TIME_S,
    GRASP_OBJECT,
    build_demo_runtime_config,
)
import adaptive_grasp.demo_config as demo_config


def test_demo_runtime_config_uses_user_facing_object_and_hold_time_only():
    runtime = build_demo_runtime_config("paper_cup", 3.5)

    scene = DEMO_SCENES["paper_cup"]
    config = runtime.adaptive_config

    assert config.default_object == scene.default_object
    assert config.pre_grasp_preset == scene.pre_grasp_preset
    assert config.release_hold_time_s == 3.5
    assert config.hold_command_mode == "position"
    assert config.enable_visualization is False
    assert runtime.enable_tactile_csv is False


def test_demo_runtime_config_defaults_use_top_level_demo_choices():
    runtime = build_demo_runtime_config()

    assert runtime.adaptive_config.release_hold_time_s == HOLD_TIME_S
    assert runtime.adaptive_config.default_object == DEMO_SCENES[GRASP_OBJECT].default_object


def test_demo_runtime_config_interrupt_default_comes_from_module_constant():
    runtime = DemoRuntimeConfig(
        adaptive_config=AdaptiveGraspConfig(
            default_object="paper_cup",
            pre_grasp_preset="paper_cup_grasp",
        )
    )

    assert runtime.interrupt_release_wait_s == demo_config._INTERRUPT_RELEASE_WAIT_S


def test_mineral_water_bottle_demo_name_has_no_hidden_whitespace():
    runtime = build_demo_runtime_config("mineral_water_bottle_500ml", HOLD_TIME_S)

    assert runtime.adaptive_config.default_object == "mineral_water_bottle_500ml"


@pytest.mark.parametrize("grasp_object, scene", DEMO_SCENES.items())
def test_all_demo_scenes_build_valid_adaptive_configs(grasp_object, scene):
    runtime = build_demo_runtime_config(grasp_object, HOLD_TIME_S)

    assert runtime.adaptive_config.pre_grasp_preset == scene.pre_grasp_preset
    assert runtime.adaptive_config.active_fingers == PRESET_ACTIVE_FINGERS[scene.pre_grasp_preset]


def test_hidden_demo_defaults_follow_adaptive_config_defaults_where_possible():
    runtime = build_demo_runtime_config("balloon", 1.1)
    default_config = AdaptiveGraspConfig(
        default_object=runtime.adaptive_config.default_object,
        pre_grasp_preset=runtime.adaptive_config.pre_grasp_preset,
    )

    assert runtime.adaptive_config.max_torque == default_config.max_torque
    assert runtime.adaptive_config.torque_hold_base_torque == default_config.torque_hold_base_torque


def test_unknown_demo_object_tells_user_which_setting_to_edit():
    with pytest.raises(ValueError, match="GRASP_OBJECT"):
        build_demo_runtime_config("unknown_object", HOLD_TIME_S)


def test_invalid_demo_hold_time_tells_user_which_setting_to_edit():
    with pytest.raises(ValueError, match="HOLD_TIME_S"):
        build_demo_runtime_config(GRASP_OBJECT, 0)


def test_short_demo_hold_time_warns_but_still_builds():
    with pytest.warns(UserWarning, match="HOLD_TIME_S.*> 1"):
        runtime = build_demo_runtime_config(GRASP_OBJECT, 1.0)

    assert runtime.adaptive_config.release_hold_time_s == 1.0


def test_short_interrupt_release_wait_warns_but_still_builds():
    with pytest.warns(UserWarning, match="_INTERRUPT_RELEASE_WAIT_S.*> 3"):
        runtime = build_demo_runtime_config(
            GRASP_OBJECT,
            HOLD_TIME_S,
            interrupt_release_wait_s=3.0,
        )

    assert runtime.interrupt_release_wait_s == 3.0


def test_invalid_interrupt_release_wait_tells_user_which_setting_to_edit():
    with pytest.raises(ValueError, match="_INTERRUPT_RELEASE_WAIT_S"):
        build_demo_runtime_config(
            GRASP_OBJECT,
            HOLD_TIME_S,
            interrupt_release_wait_s=0,
        )


def test_demo_config_is_code_defined_without_toml_loader():
    assert not hasattr(demo_config, "build_demo_runtime_config_from_toml")
