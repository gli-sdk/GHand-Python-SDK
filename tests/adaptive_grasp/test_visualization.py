import math
import time
from pathlib import Path

import pytest

from adaptive_grasp.config import AdaptiveGraspConfig
from adaptive_grasp.tactility import TactileAnalyzer, TactileAnalysis
from adaptive_grasp.visualization import TactileVisualizer
from ghand import TactileSensorId


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


class _GHandTactileInfo:
    def __init__(self, fx: float, fy: float, fz: float):
        self.resultant_force = [fx, fy, fz]
        self.distributed_force = []


def test_visualizer_init_with_active_fingers():
    viz = TactileVisualizer(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FF},
        max_points=50,
    )
    assert set(viz._active_fingers) == {TactileSensorId.THUMB, TactileSensorId.FF}
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

    viz.update(
        tactile_data,
        analysis,
        force_refs={TactileSensorId.THUMB: 0.8},
        timestamp=0.0,
    )

    assert len(viz._timestamps) == 1
    assert len(viz._data[TactileSensorId.THUMB]["fz"]) == 1
    assert len(viz._data[TactileSensorId.THUMB]["fz_ref"]) == 1
    assert viz._data[TactileSensorId.THUMB]["fz_ref"][0] == pytest.approx(0.8)
    assert len(viz._data[TactileSensorId.THUMB]["ft"]) == 1
    # ft = hypot(0.3, 0.4) = 0.5
    assert viz._data[TactileSensorId.THUMB]["ft"][0] == pytest.approx(0.5)


def test_visualizer_update_accepts_ghand_tactile_fields():
    viz = TactileVisualizer(
        active_fingers={TactileSensorId.THUMB},
        max_points=10,
    )
    cfg = AdaptiveGraspConfig()
    analyzer = TactileAnalyzer(cfg)

    tactile_data = {
        TactileSensorId.THUMB: _GHandTactileInfo(0.6, 0.8, 1.0),
    }
    analysis = analyzer.update(tactile_data)

    viz.update(tactile_data, analysis, timestamp=0.0)

    assert viz._data[TactileSensorId.THUMB]["ft"][0] == pytest.approx(1.0)


def test_visualizer_plots_slip_indicator_components():
    viz = TactileVisualizer(
        active_fingers={TactileSensorId.THUMB},
        max_points=10,
    )
    cfg = AdaptiveGraspConfig()
    analyzer = TactileAnalyzer(cfg)

    for _ in range(3):
        analyzer.update({TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 1.0)})
    tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.3, 0.4, 1.0),
    }
    analysis = analyzer.update(tactile_data)
    per = analysis.per_finger[TactileSensorId.THUMB]

    viz.update(tactile_data, analysis, timestamp=0.0)

    assert viz._data[TactileSensorId.THUMB]["s_k"][0] == pytest.approx(per.s_k)
    assert viz._data[TactileSensorId.THUMB]["d_k"][0] == pytest.approx(per.d_k)
    assert viz._data[TactileSensorId.THUMB]["r_k"][0] == pytest.approx(per.r_k)


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


def test_visualizer_start_disables_itself_when_backend_fails(monkeypatch):
    viz = TactileVisualizer(
        active_fingers={TactileSensorId.THUMB},
        update_interval=0.001,
    )

    def fail_subplots(*_args, **_kwargs):
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr("adaptive_grasp.visualization.plt.subplots", fail_subplots)

    viz.start()

    assert viz._running is False
    assert viz._thread is None


def test_visualizer_start_does_not_create_background_gui_thread(monkeypatch):
    viz = TactileVisualizer(active_fingers={TactileSensorId.THUMB})

    def fail_subplots(*_args, **_kwargs):
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr("adaptive_grasp.visualization.plt.subplots", fail_subplots)

    viz.start()

    assert viz._thread is None


def test_visualizer_stop_does_not_write_stdout(monkeypatch, capsys):
    viz = TactileVisualizer(active_fingers={TactileSensorId.THUMB})
    viz._fig = object()
    monkeypatch.setattr("adaptive_grasp.visualization.plt.close", lambda _fig: None)

    viz.stop()

    captured = capsys.readouterr()
    assert captured.out == ""


def test_visualizer_stop_keeps_figure_open_by_default(monkeypatch):
    viz = TactileVisualizer(active_fingers={TactileSensorId.THUMB})
    fig = object()
    viz._fig = fig
    closed = []
    monkeypatch.setattr(
        "adaptive_grasp.visualization.plt.close",
        lambda _fig: closed.append(_fig),
    )

    viz.stop()

    assert closed == []
    assert viz._fig is fig


def test_visualizer_detach_window_spawns_snapshot_viewer(monkeypatch):
    viz = TactileVisualizer(active_fingers={TactileSensorId.THUMB})
    viz._timestamps.extend([1.0, 2.0])
    viz._data[TactileSensorId.THUMB]["fz"].extend([0.5, 0.8])
    launched = []
    snapshot_path = Path("snapshot.json")

    monkeypatch.setattr(viz, "_write_snapshot_file", lambda: snapshot_path)
    monkeypatch.setattr(
        viz,
        "_launch_snapshot_viewer",
        lambda path: launched.append(path),
    )

    viz.detach_window()

    assert launched == [snapshot_path]
