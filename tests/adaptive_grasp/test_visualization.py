import math
import time

import pytest

from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.tactility import TactileAnalyzer, TactileAnalysis
from xiaoyao.adaptive_grasp.visualization import TactileVisualizer
from xiaoyao.dexhand import TactileSensorId


class _FakeTactileInfo:
    def __init__(self, fx: float, fy: float, fz: float):
        self._fx = fx
        self._fy = fy
        self._fz = fz

    def get_force_x(self) -> float:
        return self._fx

    def get_force_y(self) -> float:
        return self._fy

    def get_force_z(self) -> float:
        return self._fz


def test_visualizer_init_with_active_fingers():
    viz = TactileVisualizer(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
        max_points=50,
    )
    assert set(viz._active_fingers) == {TactileSensorId.THUMB, TactileSensorId.FOREFINGER}
    assert viz._max_points == 50


def test_visualizer_update_populates_data():
    viz = TactileVisualizer(
        active_fingers={TactileSensorId.THUMB},
        max_points=10,
    )
    cfg = AdaptiveGraspConfig()
    analyzer = TactileAnalyzer(cfg)

    tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.3, 0.4, 1.0),
    }
    analysis = analyzer.update(tactile_data)

    viz.update(tactile_data, analysis, timestamp=0.0)

    assert len(viz._timestamps) == 1
    assert len(viz._data[TactileSensorId.THUMB]["fz"]) == 1
    assert len(viz._data[TactileSensorId.THUMB]["ft"]) == 1
    # ft = hypot(0.3, 0.4) = 0.5
    assert viz._data[TactileSensorId.THUMB]["ft"][0] == pytest.approx(0.5)


def test_visualizer_respects_max_points():
    viz = TactileVisualizer(
        active_fingers={TactileSensorId.THUMB},
        max_points=3,
    )
    cfg = AdaptiveGraspConfig()
    analyzer = TactileAnalyzer(cfg)

    tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 1.0),
    }

    for i in range(5):
        analysis = analyzer.update(tactile_data)
        viz.update(tactile_data, analysis, timestamp=float(i))

    assert len(viz._timestamps) == 3
    assert list(viz._timestamps) == [2.0, 3.0, 4.0]


def test_visualizer_thread_disables_itself_when_backend_fails(monkeypatch):
    viz = TactileVisualizer(
        active_fingers={TactileSensorId.THUMB},
        update_interval=0.001,
    )

    def fail_subplots(*_args, **_kwargs):
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr("xiaoyao.adaptive_grasp.visualization.plt.subplots", fail_subplots)

    viz.start()
    deadline = time.monotonic() + 1.0
    while viz._thread is not None and viz._thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert viz._running is False
    assert viz._thread is not None
    assert not viz._thread.is_alive()


def test_visualizer_stop_does_not_write_stdout(monkeypatch, capsys):
    viz = TactileVisualizer(active_fingers={TactileSensorId.THUMB})
    viz._fig = object()
    monkeypatch.setattr("xiaoyao.adaptive_grasp.visualization.plt.close", lambda _fig: None)

    viz.stop()

    captured = capsys.readouterr()
    assert captured.out == ""
