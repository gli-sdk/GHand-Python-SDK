import csv
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from xiaoyao.dexhand import Joint, JointId, TactileSensorId


# Load the demo module (filename starts with a digit, cannot import directly)
_DEMO_PATH = Path(__file__).resolve().parents[2] / "examples" / "22.adaptive_grasp_demo.py"
spec = importlib.util.spec_from_file_location("adaptive_grasp_demo", _DEMO_PATH)
assert spec is not None and spec.loader is not None
demo = importlib.util.module_from_spec(spec)
sys.modules["adaptive_grasp_demo"] = demo
spec.loader.exec_module(demo)


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
    assert args.base_torque == 30
    assert args.max_torque == 80
    assert args.pre_grasp_preset == "three_finger_pinch"
    assert args.contact_threshold_z == 0.8
    assert args.hold_time == 20.0
    assert args.object is None
    assert args.verbose is False


def test_build_config_from_args():
    parser = demo.build_parser()
    args = parser.parse_args([
        "--base_torque", "25",
        "--max-torque", "70",
        "--contact_threshold_z", "1.2",
        "--pre-grasp-preset", "two_finger_pinch",
    ])
    cfg = demo.build_config(args)
    assert cfg.base_torque == 25
    assert cfg.max_torque == 70
    assert cfg.contact_threshold_z == pytest.approx(1.2)
    assert cfg.pre_grasp_preset == "two_finger_pinch"
    assert TactileSensorId.THUMB in cfg.active_fingers
    assert TactileSensorId.FOREFINGER in cfg.active_fingers


def test_build_config_with_object():
    parser = demo.build_parser()
    args = parser.parse_args(["--object", "egg"])
    cfg = demo.build_config(args)
    assert cfg.pre_grasp_preset == "three_finger_pinch"


def test_tactile_logger_writes_csv():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        hand = _MockDexHand()
        logger = demo.TactileLogger(hand, tmp_dir)
        assert logger.csv_path.exists()

        logger.write_row("CLOSING_TO_CONTACT", 30)
        logger.write_row("ADAPTIVE_HOLD", 45)
        logger.close()

        with open(logger.csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
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
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_main_smoke(monkeypatch):
    """End-to-end smoke test: main() completes without crashing."""
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        # Redirect dist output so we don't pollute the real dist/ folder
        monkeypatch.setattr(demo, "ROOT", tmp_dir)

        # Inject mock hand
        monkeypatch.setattr(demo, "DexHand", _MockDexHand)

        # Accelerate sleeps so the test finishes quickly
        monkeypatch.setattr(demo.time, "sleep", lambda _x: None)

        # Use very short hold time and a preset that matches our mock data (3 fingers)
        test_argv = [
            "22.adaptive_grasp_demo.py",
            "--hold-time", "0.01",
            "--pre-grasp-preset", "three_finger_pinch",
            "--contact_threshold_z", "0.5",
        ]

        with patch.object(sys, "argv", test_argv):
            demo.main()

        # CSV should have been written
        dist_dir = tmp_dir / "dist"
        csv_files = list(dist_dir.glob("tactile_*.csv"))
        assert len(csv_files) == 1

        with open(csv_files[0], "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) >= 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_main_connection_failure(monkeypatch):
    """main() should exit early when hand.open() returns False."""
    tmp_dir = Path(tempfile.mkdtemp())
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
    tmp_dir = Path(tempfile.mkdtemp())
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
