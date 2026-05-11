import csv
import io
import importlib.util
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

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


def test_build_parser_defaults():
    parser = demo.build_parser()
    args = parser.parse_args([])
    assert args.max_torque == 80
    assert args.pre_grasp_preset == "small_pinch"
    assert args.hold_time == 100
    assert args.object == "metal"
    assert args.hold_command_mode == "position"
    assert args.torque_hold_base_torque == 4
    assert args.interrupt_release_wait == 1
    assert args.verbose is False


def test_build_config_from_args():
    parser = demo.build_parser()
    args = parser.parse_args([
        "--max-torque", "70",
        "--pre-grasp-preset", "two_finger_pinch",
        "--hold-command-mode", "torque",
        "--torque-hold-base-torque", "6",
    ])
    cfg = demo.build_config(args)
    assert cfg.max_torque == 70
    assert cfg.pre_grasp_preset == "two_finger_pinch"
    assert cfg.adaptive_hold_command_mode == "torque"
    assert cfg.torque_hold_base_torque == 6
    assert TactileSensorId.THUMB in cfg.active_fingers
    assert TactileSensorId.FOREFINGER in cfg.active_fingers


def test_build_config_with_object():
    parser = demo.build_parser()
    args = parser.parse_args(["--default_object", "egg"])
    cfg = demo.build_config(args)
    assert cfg.default_object == "egg"
    assert cfg.pre_grasp_preset == "small_pinch"


class _NonClosingStringIO(io.StringIO):
    def close(self):
        self.flush()


def test_tactile_logger_writes_csv(monkeypatch):
    stream = _NonClosingStringIO()
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: stream)

    hand = _MockDexHand()
    logger = demo.TactileLogger(hand, Path("."))
    assert logger.csv_path.name.startswith("tactile_")

    logger.write_row("CLOSING_TO_CONTACT", 30)
    logger.write_row("ADAPTIVE_HOLD", 45)
    logger.close()

    reader = csv.DictReader(io.StringIO(stream.getvalue()))
    rows = list(reader)

    assert len(rows) == 2
    assert rows[0]["state"] == "CLOSING_TO_CONTACT"
    assert rows[0]["torque"] == "30"
    assert rows[1]["state"] == "ADAPTIVE_HOLD"
    assert rows[1]["torque"] == "45"
    # Verify tactile columns exist
    assert "thumb_x" in rows[0]
    assert "thumb_y" in rows[0]
    assert "thumb_z" in rows[0]


def test_main_smoke(monkeypatch):
    """End-to-end smoke test: main() completes without crashing."""
    tmp_dir = _workspace_tmp_root()
    try:
        # Redirect dist output so we don't pollute the real dist/ folder
        monkeypatch.setattr(demo, "ROOT", tmp_dir)

        # Inject mock hand and grasper
        monkeypatch.setattr(demo, "DexHand", _MockDexHand)

        class _MockGrasper:
            def __init__(self, hand, config):
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

        loggers = []

        class _FakeLogger:
            def __init__(self, hand, output_dir):
                self.csv_path = output_dir / "tactile_fake.csv"
                self.rows = []
                self.closed = False
                loggers.append(self)

            def write_row(self, state, torque):
                self.rows.append((state, torque))

            def close(self):
                self.closed = True

        monkeypatch.setattr(demo, "TactileLogger", _FakeLogger)

        # Accelerate sleeps so the test finishes quickly
        monkeypatch.setattr(demo.time, "sleep", lambda _x: None)

        # Use very short hold time and a preset that matches our mock data (3 fingers)
        test_argv = [
            "2x.adaptive_grasp_demo.py",
            "--hold-time", "0.01",
            "--pre-grasp-preset", "small_pinch",
        ]

        with patch.object(sys, "argv", test_argv):
            demo.main()

        assert len(loggers) == 1
        assert len(loggers[0].rows) >= 1
        assert loggers[0].closed is True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_main_connection_failure(monkeypatch):
    """main() should exit early when hand.open() returns False."""
    tmp_dir = _workspace_tmp_root()
    try:
        monkeypatch.setattr(demo, "ROOT", tmp_dir)

        class FailingHand(_MockDexHand):
            def open(self, *args, **kwargs):
                return False

        monkeypatch.setattr(demo, "DexHand", FailingHand)

        with patch.object(sys, "argv", ["demo.py"]):
            demo.main()  # Should not raise

        dist_dir = tmp_dir / "dist"
        assert not list(dist_dir.glob("tactile_*.csv"))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_main_tactile_open_failure(monkeypatch):
    """main() should exit early when tactile_open() returns False."""
    tmp_dir = _workspace_tmp_root()
    try:
        monkeypatch.setattr(demo, "ROOT", tmp_dir)

        class FailingHand(_MockDexHand):
            def tactile_open(self):
                return False

        monkeypatch.setattr(demo, "DexHand", FailingHand)

        with patch.object(sys, "argv", ["demo.py"]):
            demo.main()

        dist_dir = tmp_dir / "dist"
        assert not list(dist_dir.glob("tactile_*.csv"))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
