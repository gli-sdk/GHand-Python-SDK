import importlib.util
from types import SimpleNamespace
import sys
from pathlib import Path
from unittest.mock import patch

from xiaoyao.adaptive_grasp.torque_hold_planner import TorqueHoldDecision
from xiaoyao.dexhand import TactileSensorId

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
        self.wait_calls = 0

    def grasp_core(self):
        raise KeyboardInterrupt

    def release(self):
        self.release_calls += 1
        return True

    def wait_for_visualizer_close(self):
        self.wait_calls += 1

    def get_state(self):
        return demo.GraspState.ERROR


class _FakeTactileLogger:
    last_instance = None

    def __init__(self, hand, output_dir):
        type(self).last_instance = self
        self.hand = hand
        self.output_dir = output_dir
        self.csv_path = output_dir / "fake_tactile.csv"
        self.closed = False
        self.rows: list[tuple[str, int]] = []

    def write_row(self, state: str, torque: int) -> None:
        self.rows.append((state, torque))

    def close(self) -> None:
        self.closed = True


def _fake_config():
    return SimpleNamespace(
        release_hold_time_s=0.01,
        release_open_speed=50,
        release_open_torque=50,
        adaptive_hold_command_mode="position",
        adaptive_hold_torque=20,
        pre_grasp_preset="two_finger_pinch",
    )


def test_build_config_accepts_adaptive_hold_command_options():
    captured_kwargs = {}

    class _ConfigSpy:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    parser = demo.build_parser()
    args = parser.parse_args([
        "--hold-command-mode", "torque",
        "--adaptive-hold-torque", "20",
        "--phase-closing-torque", "4",
        "--default_object", "balloon",
    ])

    original_config = demo.AdaptiveGraspConfig
    demo.AdaptiveGraspConfig = _ConfigSpy
    try:
        cfg = demo.build_config(args)
    finally:
        demo.AdaptiveGraspConfig = original_config

    assert isinstance(cfg, _ConfigSpy)
    assert captured_kwargs["adaptive_hold_command_mode"] == "torque"
    assert captured_kwargs["adaptive_hold_torque"] == 20
    assert captured_kwargs["phase_closing_torque"] == 4
    assert captured_kwargs["default_object"] == "balloon"


def test_build_config_does_not_override_config_defaults_when_args_omitted():
    captured_kwargs = {}

    class _ConfigSpy:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    parser = demo.build_parser()
    args = parser.parse_args([])

    original_config = demo.AdaptiveGraspConfig
    demo.AdaptiveGraspConfig = _ConfigSpy
    try:
        cfg = demo.build_config(args)
    finally:
        demo.AdaptiveGraspConfig = original_config

    assert isinstance(cfg, _ConfigSpy)
    assert captured_kwargs == {}


def test_print_hold_status_uses_newline(capsys):
    demo.print_hold_status("adaptive_hold", 4)

    captured = capsys.readouterr()
    assert captured.out == "state=adaptive_hold     ; torque=  4\n"


def test_format_hold_status_includes_torque_decision():
    decision = TorqueHoldDecision(
        finger_torques={
            TactileSensorId.THUMB: 5.4,
            TactileSensorId.FOREFINGER: 6.2,
        },
        force_refs={},
        contact_ratios={},
        F_ref_total=0.8,
    )

    line = demo.format_hold_status(
        state="adaptive_hold",
        torque=6,
        mode="torque",
        total_fz=0.7,
        slip_risk=0.4,
        slip_confirmed=False,
        torque_decision=decision,
    )

    assert "state=adaptive_hold" in line
    assert "mode=torque" in line
    assert "total_fz=0.70" in line
    assert "slip_risk=0.40" in line
    assert "F_ref_total=0.80" in line
    assert "THUMB=5.40" in line
    assert "FOREFINGER=6.20" in line


def test_main_zeroes_tactile_after_open(monkeypatch):
    monkeypatch.setattr(demo, "DexHand", _MockHand)
    monkeypatch.setattr(demo, "AdaptiveGrasper", _InterruptingGrasper)
    monkeypatch.setattr(demo, "TactileLogger", _FakeTactileLogger)
    monkeypatch.setattr(demo, "build_config", lambda _args: _fake_config())
    monkeypatch.setattr(demo.time, "sleep", lambda _x: None)

    with patch.object(sys, "argv", [
        "2x.adaptive_grasp_demo.py",
        "--no-release-on-interrupt",
    ]):
        demo.main()

    assert _MockHand.last_instance is not None
    assert _MockHand.last_instance.events[:3] == ["open", "tactile_open", "tactile_zero"]


def test_main_releases_on_keyboard_interrupt_by_default(monkeypatch):
    monkeypatch.setattr(demo, "DexHand", _MockHand)
    monkeypatch.setattr(demo, "AdaptiveGrasper", _InterruptingGrasper)
    monkeypatch.setattr(demo, "TactileLogger", _FakeTactileLogger)
    monkeypatch.setattr(demo, "build_config", lambda _args: _fake_config())
    monkeypatch.setattr(demo.time, "sleep", lambda _x: None)

    with patch.object(sys, "argv", ["2x.adaptive_grasp_demo.py"]):
        demo.main()

    assert _InterruptingGrasper.last_instance is not None
    assert _InterruptingGrasper.last_instance.release_calls == 1


def test_main_can_skip_release_on_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(demo, "DexHand", _MockHand)
    monkeypatch.setattr(demo, "AdaptiveGrasper", _InterruptingGrasper)
    monkeypatch.setattr(demo, "TactileLogger", _FakeTactileLogger)
    monkeypatch.setattr(demo, "build_config", lambda _args: _fake_config())
    monkeypatch.setattr(demo.time, "sleep", lambda _x: None)

    with patch.object(sys, "argv", ["2x.adaptive_grasp_demo.py", "--no-release-on-interrupt"]):
        demo.main()

    assert _InterruptingGrasper.last_instance is not None
    assert _InterruptingGrasper.last_instance.release_calls == 0
