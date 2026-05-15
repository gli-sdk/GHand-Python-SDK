import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

from xiaoyao.adaptive_grasp.demo_config import DemoRuntimeConfig
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig

_DEMO_PATH = Path(__file__).resolve().parents[2] / "examples" / "2x.adaptive_grasp_demo.py"
spec = importlib.util.spec_from_file_location("adaptive_grasp_demo_2x", _DEMO_PATH)
assert spec is not None and spec.loader is not None
demo = importlib.util.module_from_spec(spec)
sys.modules["adaptive_grasp_demo_2x"] = demo
spec.loader.exec_module(demo)


class _MockHand:
    last_instance = None

    def __init__(self):
        type(self).last_instance = self
        self.events: list[str] = []

    def open(self, *args, **kwargs):
        self.events.append("open")
        return True

    def tactile_open(self):
        self.events.append("tactile_open")
        return True

    def tactile_zero(self):
        self.events.append("tactile_zero")
        return True

    def tactile_close(self):
        self.events.append("tactile_close")
        return True

    def close(self):
        self.events.append("close")
        return True

    def get_tactile_data(self):
        return {}


class _InterruptingGrasper:
    last_instance = None

    def __init__(self, hand, config):
        type(self).last_instance = self
        self.config = config
        self.release_calls = 0
        self.emergency_release_waits: list[float] = []
        self.wait_calls = 0

    def grasp_core(self):
        raise KeyboardInterrupt

    def release(self):
        self.release_calls += 1
        return True

    def emergency_release(self, wait_s=0.2):
        self.emergency_release_waits.append(wait_s)
        return True

    def wait_for_visualizer_close(self):
        self.wait_calls += 1

    def get_state(self):
        return demo.GraspState.ERROR


def _fake_config():
    return AdaptiveGraspConfig(
        default_object="paper_cup",
        release_hold_time_s=0.01,
        pre_grasp_preset="two_finger_pinch",
        enable_visualization=False,
    )


def test_demo_no_longer_exposes_command_line_parser():
    assert not hasattr(demo, "build_parser")
    assert not hasattr(demo, "build_config")


def test_demo_no_longer_exposes_internal_diagnostics():
    assert not hasattr(demo, "TactileLogger")
    assert not hasattr(demo, "format_hold_status")
    assert not hasattr(demo, "print_hold_status")


def test_main_zeroes_tactile_after_open(monkeypatch):
    monkeypatch.setattr(demo, "DexHand", _MockHand)
    monkeypatch.setattr(demo, "AdaptiveGrasper", _InterruptingGrasper)
    monkeypatch.setattr(
        demo,
        "build_demo_runtime_config",
        lambda: DemoRuntimeConfig(adaptive_config=_fake_config()),
    )
    monkeypatch.setattr(demo.time, "sleep", lambda _x: None)

    with patch.object(sys, "argv", ["2x.adaptive_grasp_demo.py", "--ignored-cli-arg"]):
        demo.main()

    assert _MockHand.last_instance is not None
    assert _MockHand.last_instance.events[:2] == ["open", "tactile_open"]
    assert "tactile_zero" not in _MockHand.last_instance.events


def test_main_fast_releases_on_keyboard_interrupt_by_default(monkeypatch):
    monkeypatch.setattr(demo, "DexHand", _MockHand)
    monkeypatch.setattr(demo, "AdaptiveGrasper", _InterruptingGrasper)
    monkeypatch.setattr(
        demo,
        "build_demo_runtime_config",
        lambda: DemoRuntimeConfig(adaptive_config=_fake_config()),
    )
    monkeypatch.setattr(demo.time, "sleep", lambda _x: None)

    with patch.object(sys, "argv", ["2x.adaptive_grasp_demo.py"]):
        demo.main()

    assert _InterruptingGrasper.last_instance is not None
    assert _InterruptingGrasper.last_instance.release_calls == 0
    assert _InterruptingGrasper.last_instance.emergency_release_waits == [1.0]


def test_main_uses_internal_fast_release_wait_on_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(demo, "DexHand", _MockHand)
    monkeypatch.setattr(demo, "AdaptiveGrasper", _InterruptingGrasper)
    monkeypatch.setattr(
        demo,
        "build_demo_runtime_config",
        lambda: DemoRuntimeConfig(
            adaptive_config=_fake_config(),
            interrupt_release_wait_s=0.05,
        ),
    )
    monkeypatch.setattr(demo.time, "sleep", lambda _x: None)

    with patch.object(sys, "argv", ["2x.adaptive_grasp_demo.py"]):
        demo.main()

    assert _InterruptingGrasper.last_instance is not None
    assert _InterruptingGrasper.last_instance.emergency_release_waits == [0.05]

