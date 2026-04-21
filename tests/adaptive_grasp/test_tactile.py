import math
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.tactile import TactileAnalyzer, TactileAnalysis
from xiaoyao.dexhand import TactileSensorId


class FakeTactileInfo:
    def __init__(self, fx, fy, fz):
        self._fx = fx
        self._fy = fy
        self._fz = fz
    def get_force_x(self): return self._fx
    def get_force_y(self): return self._fy
    def get_force_z(self): return self._fz


def test_tactile_analysis_variance_and_slip_risk():
    cfg = AdaptiveGraspConfig(variance_baseline=0.0, variance_threshold=1.0, epsilon=1e-6)
    analyzer = TactileAnalyzer(cfg)

    # 填充滑动窗口使方差非零（交替切向力产生变化）
    for i in range(cfg.sliding_window_size):
        data = {
            TactileSensorId.THUMB: FakeTactileInfo(0.5 if i % 2 == 0 else 0.0, 0.0, 1.0),
            TactileSensorId.FOREFINGER: FakeTactileInfo(0.0, 0.0, 1.0),
        }
        result = analyzer.update(data)

    assert result.variance > 0.0
    assert 0.0 <= result.slip_risk <= 1.0
    assert result.total_fz == pytest.approx(2.0)


def test_slip_confirmed_after_debounce():
    cfg = AdaptiveGraspConfig(
        variance_baseline=0.0,
        variance_threshold=1.0,
        slip_detect_debounce_cycles=3,
    )
    analyzer = TactileAnalyzer(cfg)

    # 预填充窗口到长度 >= 3（恒定力，方差为 0，不影响 debounce）
    for _ in range(3):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0)})

    # 连续 3 个周期高方差
    for i in range(3):
        data = {
            TactileSensorId.THUMB: FakeTactileInfo(10.0 if i % 2 == 0 else 0.0, 0.0, 1.0),
        }
        result = analyzer.update(data)

    assert result.slip_confirmed is True


def test_slip_confirmed_resets_on_clear():
    cfg = AdaptiveGraspConfig(
        variance_baseline=0.0,
        variance_threshold=1.0,
        slip_detect_debounce_cycles=3,
    )
    analyzer = TactileAnalyzer(cfg)

    # 2 个周期高方差（未触发）
    for _ in range(2):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 1.0)})
    # 1 个周期低方差（衰减）
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0)})
    assert result.slip_confirmed is False
