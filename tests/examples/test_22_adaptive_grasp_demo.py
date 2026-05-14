import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.demo_config import DemoRuntimeConfig, build_demo_runtime_config
from xiaoyao.dexhand import Joint, JointId, TactileSensorId


# Load the demo module (filename starts with a digit, cannot import directly)
_DEMO_PATH = Path(__file__).resolve().parents[2] / "examples" / "2x.adaptive_grasp_demo.py"
spec = importlib.util.spec_from_file_location("adaptive_grasp_demo", _DEMO_PATH)
assert spec is not None and spec.loader is not None
demo = importlib.util.module_from_spec(spec)
sys.modules["adaptive_grasp_demo"] = demo
spec.loader.exec_module(demo)


def _workspace_tmp_root() -> Path:
    return Path(__file__).resolve().parents[2] / "tmp_test_adaptive_grasp_demo"


class _MockTactileInfo:
    def __init__(self, fx: float = 0.0, fy: float = 0.0, fz: float = 0.0):
        self._fx = fx
        self._fy = fy
        self._fz = fz

    def get_force_x(self) -> float:
        return self._fx

    def get_force_y(self) -> float:
        return self._fy

    def get_force_z(self) -> float:
        return self._fz


class _MockDexHand:
    """Minimal mock hand that makes grasp_core happy."""

    def __init__(self):
        self._tactile = {
            TactileSensorId.THUMB: _MockTactileInfo(0.1, 0.1, 2.0),
            TactileSensorId.FOREFINGER: _MockTactileInfo(0.1, 0.1, 2.0),
            TactileSensorId.MIDDLE_FINGER: _MockTactileInfo(0.1, 0.1, 2.0),
        }
        self._joints = [
            Joint(id=JointId.THUMB_MCP, angle=0.0),
            Joint(id=JointId.THUMB_PIP, angle=0.0),
            Joint(id=JointId.FF_MCP, angle=0.0),
            Joint(id=JointId.FF_PIP, angle=0.0),
            Joint(id=JointId.MF_MCP, angle=0.0),
            Joint(id=JointId.MF_PIP, angle=0.0),
        ]

    def open(self, *args, **kwargs):
        return True

    def tactile_open(self):
        return True

    def tactile_close(self):
        pass

    def close(self):
        pass

    def stop(self):
        pass

    def move_joints(self, joints, mode=None):
        return True

    def get_tactile_data(self):
        return self._tactile

    def get_joints(self):
        return self._joints


def test_demo_uses_code_config_instead_of_command_line_parser():
    assert not hasattr(demo, "build_parser")
    assert not hasattr(demo, "build_config")
    runtime = build_demo_runtime_config("paper_cup", 0.01)
    assert runtime.adaptive_config.default_object == "paper_cup"
    assert runtime.adaptive_config.release_hold_time_s == 0.01


def test_demo_does_not_expose_tactile_csv_logger():
    assert not hasattr(demo, "TactileLogger")


def test_main_smoke(monkeypatch):
    """End-to-end smoke test: main() completes without crashing."""
    # Inject mock hand and grasper
    monkeypatch.setattr(demo, "DexHand", _MockDexHand)

    class _MockGrasper:
        last_config = None

        def __init__(self, hand, config):
            type(self).last_config = config
            self.current_torque = 30
            self.last_tactile_analysis = None
            self.last_torque_hold_decision = None
            self._states = iter([
                demo.GraspState.ADAPTIVE_HOLD,
                demo.GraspState.COMPLETED,
            ])
            self._state = demo.GraspState.ADAPTIVE_HOLD

        def grasp_core(self):
            return True

        def get_state(self):
            self._state = next(self._states, demo.GraspState.COMPLETED)
            return self._state

        def poll_visualizer(self):
            return None

        def release(self):
            self._state = demo.GraspState.COMPLETED
            return True

        def wait_for_visualizer_close(self):
            return None

    monkeypatch.setattr(demo, "AdaptiveGrasper", _MockGrasper)

    monkeypatch.setattr(demo.time, "sleep", lambda _x: None)
    monkeypatch.setattr(
        demo,
        "build_demo_runtime_config",
        lambda: DemoRuntimeConfig(
            adaptive_config=AdaptiveGraspConfig(
                default_object="paper_cup",
                pre_grasp_preset="paper_cup_grasp",
                release_hold_time_s=0.01,
                enable_visualization=False,
            )
        ),
    )

    with patch.object(sys, "argv", ["2x.adaptive_grasp_demo.py", "--unused"]):
        demo.main()

    assert _MockGrasper.last_config.default_object == "paper_cup"


def test_main_connection_failure(monkeypatch):
    """main() should exit early when hand.open() returns False."""
    class FailingHand(_MockDexHand):
        def open(self, *args, **kwargs):
            return False

    monkeypatch.setattr(demo, "DexHand", FailingHand)

    with patch.object(sys, "argv", ["demo.py"]):
        demo.main()  # Should not raise


def test_main_tactile_open_failure(monkeypatch):
    """main() should exit early when tactile_open() returns False."""
    class FailingHand(_MockDexHand):
        def tactile_open(self):
            return False

    monkeypatch.setattr(demo, "DexHand", FailingHand)

    with patch.object(sys, "argv", ["demo.py"]):
        demo.main()
