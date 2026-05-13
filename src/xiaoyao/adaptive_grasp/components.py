from dataclasses import dataclass
from typing import Any, Optional

from .config import AdaptiveGraspConfig
from .hold_planner_factory import HoldPlannerFactory
from .joint_builder import JointCommandBuilder, TORQUE_CONTROL_JOINTS
from .safety import SafetyMonitor
from .sensor import SensorClient
from .tactility import TactileAnalyzer
from .utils import JOINT_TO_FINGER
from .visualization import TactileVisualizer


@dataclass
class AdaptiveGraspComponents:
    sensor: Any
    tactile: TactileAnalyzer
    safety: SafetyMonitor
    joint_builder: JointCommandBuilder
    hold_planner_factory: HoldPlannerFactory
    visualizer: Optional[TactileVisualizer]


def build_adaptive_grasp_components(
    *,
    hand: Any,
    config: AdaptiveGraspConfig,
    get_monotonic_time: Any,
    sensor: Optional[Any] = None,
) -> AdaptiveGraspComponents:
    active_fingers = set(config.active_fingers)
    sensor_client = sensor or SensorClient(
        hand,
        active_fingers=active_fingers,
        finger_touch_threshold_n=config.finger_touch_threshold_n,
        get_monotonic_time=get_monotonic_time,
    )
    torque_joints = tuple(
        joint
        for joint in TORQUE_CONTROL_JOINTS
        if JOINT_TO_FINGER[joint] in active_fingers
    )
    visualizer = (
        TactileVisualizer(
            active_fingers=active_fingers,
            backend=config.visualization_backend,
        )
        if config.enable_visualization
        else None
    )

    return AdaptiveGraspComponents(
        sensor=sensor_client,
        tactile=TactileAnalyzer(config),
        safety=SafetyMonitor(config),
        joint_builder=JointCommandBuilder(config, torque_joints),
        hold_planner_factory=HoldPlannerFactory(config),
        visualizer=visualizer,
    )
