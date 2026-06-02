from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

import adaptive_grasp.utils as utils
from ghand import TactileSensorId


SRC_ROOT = Path(__file__).parents[2] / "src" / "adaptive_grasp"


def test_normal_force_z_returns_absolute_z_component():
    assert hasattr(utils, "normal_force_z")

    info = SimpleNamespace(resultant_force=[1.0, -2.0, -3.5])

    assert utils.normal_force_z(info) == pytest.approx(3.5)


def test_active_finger_normal_forces_filters_to_active_present_fingers():
    assert hasattr(utils, "active_finger_normal_forces")

    tactile_data = {
        TactileSensorId.THUMB: SimpleNamespace(resultant_force=[0.0, 0.0, -1.0]),
        TactileSensorId.FF: SimpleNamespace(resultant_force=[0.0, 0.0, 2.0]),
        TactileSensorId.MF: SimpleNamespace(resultant_force=[0.0, 0.0, 3.0]),
    }

    forces = utils.active_finger_normal_forces(
        tactile_data,
        (TactileSensorId.FF, TactileSensorId.THUMB, TactileSensorId.RF),
    )

    assert list(forces) == [TactileSensorId.FF, TactileSensorId.THUMB]
    assert forces == {
        TactileSensorId.FF: pytest.approx(2.0),
        TactileSensorId.THUMB: pytest.approx(1.0),
    }


def test_normal_force_helpers_are_the_only_force_z_abs_call_sites():
    repeated_modules = ("sensor.py", "safety.py", "grasp_sequence.py")

    for module_name in repeated_modules:
        source = (SRC_ROOT / module_name).read_text(encoding="utf-8")
        assert "abs(tactile_force_xyz(" not in source


class _ThreadStub:
    def __init__(self, alive=True):
        self.alive = alive
        self.join_calls = []

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_calls.append(timeout)


def test_join_thread_if_alive_joins_live_non_current_thread():
    thread = _ThreadStub(alive=True)

    joined = utils.join_thread_if_alive(thread, timeout=1.25)

    assert joined is True
    assert thread.join_calls == [1.25]


def test_join_thread_if_alive_skips_missing_dead_and_current_threads():
    missing_api = object()
    dead_thread = _ThreadStub(alive=False)
    current_thread = threading.current_thread()

    assert utils.join_thread_if_alive(None, timeout=1.0) is False
    assert utils.join_thread_if_alive(missing_api, timeout=1.0) is False
    assert utils.join_thread_if_alive(dead_thread, timeout=1.0) is False
    assert utils.join_thread_if_alive(current_thread, timeout=1.0) is False
    assert dead_thread.join_calls == []


def test_join_thread_if_alive_is_the_only_thread_join_guard():
    repeated_modules = (
        "release_controller.py",
        "adaptive_hold_runner.py",
        "adaptive_grasp_manager.py",
    )

    for module_name in repeated_modules:
        source = (SRC_ROOT / module_name).read_text(encoding="utf-8")
        assert "threading.current_thread()" not in source
        assert ".join(timeout=" not in source
