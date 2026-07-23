from adaptive_grasp.config import AdaptiveGraspConfig
from adaptive_grasp.adaptive_grasp_manager import build_adaptive_grasp_components
from adaptive_grasp.hold_planner_factory import HoldPlannerFactory
from adaptive_grasp.joint_builder import JointCommandBuilder
from adaptive_grasp.safety import SafetyMonitor
from adaptive_grasp.sensor import SensorClient
from adaptive_grasp.tactility import TactileAnalyzer
from ghand import JointId, TactileSensorId


class FakeHand:
    pass


class FakeSensor:
    pass


class FalseyFakeSensor:
    def __bool__(self) -> bool:
        return False


def monotonic_time() -> float:
    return 0.0


def test_build_components_creates_default_dependencies_without_visualizer():
    config = AdaptiveGraspConfig(enable_visualization=False)

    components = build_adaptive_grasp_components(
        hand=FakeHand(),
        config=config,
        get_monotonic_time=monotonic_time,
    )

    assert isinstance(components.sensor, SensorClient)
    assert isinstance(components.tactile, TactileAnalyzer)
    assert isinstance(components.safety, SafetyMonitor)
    assert isinstance(components.joint_builder, JointCommandBuilder)
    assert isinstance(components.hold_planner_factory, HoldPlannerFactory)
    assert components.visualizer is None


def test_build_components_uses_injected_sensor():
    config = AdaptiveGraspConfig(enable_visualization=False)
    sensor = FakeSensor()

    components = build_adaptive_grasp_components(
        hand=FakeHand(),
        config=config,
        get_monotonic_time=monotonic_time,
        sensor=sensor,
    )

    assert components.sensor is sensor


def test_build_components_uses_injected_falsey_sensor():
    config = AdaptiveGraspConfig(enable_visualization=False)
    sensor = FalseyFakeSensor()

    components = build_adaptive_grasp_components(
        hand=FakeHand(),
        config=config,
        get_monotonic_time=monotonic_time,
        sensor=sensor,
    )

    assert components.sensor is sensor


def test_build_components_filters_torque_joints_to_active_fingers():
    config = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        enable_visualization=False,
    )

    components = build_adaptive_grasp_components(
        hand=FakeHand(),
        config=config,
        get_monotonic_time=monotonic_time,
        sensor=FakeSensor(),
    )

    assert components.joint_builder.torque_joints == (
        JointId.THUMB_MCP,
        JointId.THUMB_TMC_FE,
    )
    assert JointId.FF_PIP not in components.joint_builder.torque_joints
    assert JointId.MF_PIP not in components.joint_builder.torque_joints


def test_component_builder_lives_with_manager_entrypoint():
    import adaptive_grasp.adaptive_grasp_manager as manager_module

    assert manager_module.build_adaptive_grasp_components is build_adaptive_grasp_components
