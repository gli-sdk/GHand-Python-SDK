from dataclasses import dataclass

from .config import AdaptiveGraspConfig


# Demo users only need to edit these two values before pressing Run.
GRASP_OBJECT = "paper_cup" #default_object
HOLD_TIME_S = 60.0 #default_hold_time


@dataclass(frozen=True)
class DemoScene:
    default_object: str
    pre_grasp_preset: str


@dataclass(frozen=True)
class DemoRuntimeConfig:
    adaptive_config: AdaptiveGraspConfig
    enable_tactile_csv: bool = False
    interrupt_release_wait_s: float = 1.0


DEMO_SCENES: dict[str, DemoScene] = {
    "paper_cup": DemoScene(default_object="paper_cup", pre_grasp_preset="paper_cup_grasp"),
    "balloon": DemoScene(default_object="balloon", pre_grasp_preset="balloon_pinch"),
    "glass_cup": DemoScene(default_object="glass", pre_grasp_preset="three_finger_grasp"),
    "plastic_cup": DemoScene(default_object="plastic_cup", pre_grasp_preset="paper_cup_grasp"),
    "smooth_ball": DemoScene(default_object="plastic_cup", pre_grasp_preset="smooth_ball"),
    "mineral_water_bottle_500ml": DemoScene(
        default_object="mineral_water_bottle_500ml",
        pre_grasp_preset="minreal_water_grasp",
    ),
    "plastic_object": DemoScene(default_object="plastic", pre_grasp_preset="two_finger_pinch"),
    "orange": DemoScene(default_object="fruit", pre_grasp_preset="four_finger_grasp"),
    "pen": DemoScene(default_object="plastic", pre_grasp_preset="pen_pinch"),
}

_ENABLE_TACTILE_CSV = False
_ENABLE_VISUALIZATION = False
_HOLD_COMMAND_MODE = "position"
_INTERRUPT_RELEASE_WAIT_S = 1.0


def build_demo_runtime_config(
    grasp_object: str = GRASP_OBJECT,
    hold_time_s: float = HOLD_TIME_S,
) -> DemoRuntimeConfig:
    if grasp_object not in DEMO_SCENES:
        supported = ", ".join(sorted(DEMO_SCENES))
        raise ValueError(
            f'Unsupported GRASP_OBJECT="{grasp_object}". '
            "Edit GRASP_OBJECT in adaptive_grasp.demo_config. "
            f"Supported values: {supported}"
        )
    if hold_time_s <= 0:
        raise ValueError(
            "HOLD_TIME_S must be > 0. "
            "Edit HOLD_TIME_S in adaptive_grasp.demo_config."
        )

    scene = DEMO_SCENES[grasp_object]
    adaptive_config = AdaptiveGraspConfig(
        default_object=scene.default_object,
        pre_grasp_preset=scene.pre_grasp_preset,
        release_hold_time_s=hold_time_s,
        hold_command_mode=_HOLD_COMMAND_MODE,
        enable_visualization=_ENABLE_VISUALIZATION,
    )
    return DemoRuntimeConfig(
        adaptive_config=adaptive_config,
        enable_tactile_csv=_ENABLE_TACTILE_CSV,
        interrupt_release_wait_s=_INTERRUPT_RELEASE_WAIT_S,
    )
