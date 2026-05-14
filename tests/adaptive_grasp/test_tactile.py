import math
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.tactility import (
    OnlineWindowNormalizer,
    TactileAnalyzer,
    TactileAnalysis,
    get_tactile_layout_points,
)
from xiaoyao.dexhand import TactileSensorId


class FakeTactileInfo:
    def __init__(self, fx, fy, fz, distributed=None):
        self._fx = fx
        self._fy = fy
        self._fz = fz
        self._distributed = distributed if distributed is not None else []
    def get_force_x(self): return self._fx
    def get_force_y(self): return self._fy
    def get_force_z(self): return self._fz
    def get_distributed_force(self): return self._distributed


def test_tactile_layout_points_match_sensor_geometry():
    thumb_points = get_tactile_layout_points(TactileSensorId.THUMB)
    forefinger_points = get_tactile_layout_points(TactileSensorId.FOREFINGER)

    assert len(thumb_points) == 52
    assert thumb_points[0].index == 0
    assert thumb_points[0].x == pytest.approx(10.0)
    assert thumb_points[0].y == pytest.approx(385.0)
    assert thumb_points[-1].index == 51
    assert thumb_points[-1].x == pytest.approx(268.0)
    assert thumb_points[-1].y == pytest.approx(386.0)

    assert len(forefinger_points) == 31
    assert forefinger_points[0].index == 0
    assert forefinger_points[0].x == pytest.approx(22.0)
    assert forefinger_points[0].y == pytest.approx(365.0)
    assert forefinger_points[-1].index == 30
    assert forefinger_points[-1].x == pytest.approx(236.0)
    assert forefinger_points[-1].y == pytest.approx(235.0)


def test_tactile_analysis_variance_and_slip_risk():
    cfg = AdaptiveGraspConfig(slip_variance_baseline=0.0, slip_variance_threshold=1.0, numeric_epsilon=1e-6)
    analyzer = TactileAnalyzer(cfg)

    for i in range(cfg.tactile_slip_window_size):
        data = {
            TactileSensorId.THUMB: FakeTactileInfo(0.5 if i % 2 == 0 else 0.0, 0.0, 1.0),
            TactileSensorId.FOREFINGER: FakeTactileInfo(0.0, 0.0, 1.0),
        }
        result = analyzer.update(data)

    assert result.variance > 0.0
    assert 0.0 <= result.slip_risk <= 1.0
    assert result.total_fz == pytest.approx(2.0)


def test_online_window_normalizer_returns_positive_z_score_for_spike():
    normalizer = OnlineWindowNormalizer(window_size=4, eps=1e-6)

    for value in [0.0010, 0.0011, 0.0009]:
        normalizer.update(value)
    z_score = normalizer.update(0.0040)

    assert z_score > 1.0


def test_online_window_normalizer_returns_zero_for_constant_window():
    normalizer = OnlineWindowNormalizer(window_size=4, eps=1e-6)

    for _ in range(4):
        z_score = normalizer.update(0.0010)

    assert z_score == pytest.approx(0.0, abs=1e-9)


def test_slip_confirmed_after_debounce():
    cfg = AdaptiveGraspConfig(
        slip_variance_baseline=0.0,
        slip_variance_threshold=1.0,
        slip_detect_debounce_cycles=3,
        slip_variance_weight=0.5,
        slip_direction_weight=0.0,
        slip_friction_weight=0.5,
    )
    analyzer = TactileAnalyzer(cfg)

    # Warm up the window with constant force so variance stays near zero.
    for _ in range(3):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0)})

    # Drive three consecutive high-risk samples to satisfy the debounce count.
    for _ in range(3):
        data = {
            TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 1.0),
        }
        result = analyzer.update(data)

    assert result.slip_confirmed is True


def test_slip_confirmed_resets_on_clear():
    cfg = AdaptiveGraspConfig(
        slip_variance_baseline=0.0,
        slip_variance_threshold=1.0,
        slip_detect_debounce_cycles=3,
    )
    analyzer = TactileAnalyzer(cfg)


    for _ in range(2):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 1.0)})

    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0)})
    assert result.slip_confirmed is False


def test_direction_distance_zero_when_stable():
    cfg = AdaptiveGraspConfig(slip_variance_baseline=0.0, slip_variance_threshold=1.0)
    analyzer = TactileAnalyzer(cfg)


    stable = [1, 0, 0, 1, 0, 0, 1, 0, 0]
    analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(3.0, 0.0, 1.0, distributed=stable)})
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(3.0, 0.0, 1.0, distributed=stable)})

    assert result.direction_distance == pytest.approx(0.0, abs=1e-9)


def test_direction_distance_one_when_orthogonal():
    cfg = AdaptiveGraspConfig(slip_variance_baseline=0.0, slip_variance_threshold=1.0)
    analyzer = TactileAnalyzer(cfg)

    frame1 = [1, 0, 0, 1, 0, 0, 1, 0, 0]

    frame2 = [0, 1, 0, 0, 1, 0, 0, 1, 0]
    analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 3.0, 1.0, distributed=frame1)})
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 3.0, 1.0, distributed=frame2)})

    # cos_x=0, cos_y=0 => d = sqrt(2)/sqrt(2) = 1
    assert result.direction_distance == pytest.approx(1.0, abs=1e-6)


def test_direction_distance_zero_on_first_cycle():
    cfg = AdaptiveGraspConfig(slip_variance_baseline=0.0, slip_variance_threshold=1.0)
    analyzer = TactileAnalyzer(cfg)

    distributed = [1, 0, 0, 2, 0, 0, 3, 0, 0]
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(6.0, 0.0, 1.0, distributed=distributed)})

    assert result.direction_distance == pytest.approx(0.0, abs=1e-9)


def test_direction_distance_with_multiple_fingers():
    cfg = AdaptiveGraspConfig(slip_variance_baseline=0.0, slip_variance_threshold=1.0)
    analyzer = TactileAnalyzer(cfg)

    f1 = [1, 0, 0, 1, 0, 0]
    f2 = [1, 0, 0, 1, 0, 0]
    analyzer.update({
        TactileSensorId.THUMB: FakeTactileInfo(2.0, 0.0, 1.0, distributed=f1),
        TactileSensorId.FOREFINGER: FakeTactileInfo(2.0, 0.0, 1.0, distributed=f2),
    })


    f1_next = [0, 1, 0, 0, 1, 0]
    result = analyzer.update({
        TactileSensorId.THUMB: FakeTactileInfo(0.0, 2.0, 1.0, distributed=f1_next),
        TactileSensorId.FOREFINGER: FakeTactileInfo(2.0, 0.0, 1.0, distributed=f2),
    })


    assert result.direction_distance > 0.0
    assert result.direction_distance <= 1.0


def test_friction_utilization_zero_when_no_tangential_force():
    cfg = AdaptiveGraspConfig(default_friction_coeff=0.5)
    analyzer = TactileAnalyzer(cfg)

    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0)})
    # F_t = 0, F_n = 1 => mu_eff = 0 => r_k = 0
    assert result.friction_utilization == pytest.approx(0.0, abs=1e-9)


def test_friction_utilization_at_critical():
    cfg = AdaptiveGraspConfig(default_friction_coeff=0.5)
    analyzer = TactileAnalyzer(cfg)

    # F_t = 0.5, F_n = 1.0 => mu_eff = 0.5 / 1.0 = 0.5 => r_k = 0.5/0.5 = 1.0
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.5, 0.0, 1.0)})
    assert result.friction_utilization == pytest.approx(1.0, abs=1e-6)


def test_friction_utilization_clipped_to_one():
    cfg = AdaptiveGraspConfig(default_friction_coeff=0.3)
    analyzer = TactileAnalyzer(cfg)

    # F_t = 1.0, F_n = 0.2 => mu_eff = 5.0 => r_k = 5.0/0.3 > 1 => clip to 1
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(1.0, 0.0, 0.2)})
    assert result.friction_utilization == pytest.approx(1.0, abs=1e-9)


def test_friction_utilization_multiple_fingers_takes_max():
    cfg = AdaptiveGraspConfig(default_friction_coeff=0.5)
    analyzer = TactileAnalyzer(cfg)

    result = analyzer.update({
        TactileSensorId.THUMB: FakeTactileInfo(0.1, 0.0, 1.0),   # mu_eff=0.1 => r=0.2
        TactileSensorId.FOREFINGER: FakeTactileInfo(0.4, 0.0, 1.0),  # mu_eff=0.4 => r=0.8
    })
    assert result.friction_utilization == pytest.approx(0.8, abs=1e-6)


def test_slip_risk_fusion_with_all_indicators():
    cfg = AdaptiveGraspConfig(
        slip_variance_baseline=0.0,
        slip_variance_threshold=1.0,
        slip_variance_weight=0.5,
        slip_direction_weight=0.3,
        slip_friction_weight=0.2,
    )
    analyzer = TactileAnalyzer(cfg)

    frame1 = [1, 0, 0, 1, 0, 0]
    for _ in range(3):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 0.01, distributed=frame1)})


    dist = [0, 1, 0, 0, 1, 0]
    result = analyzer.update({
        TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 0.01, distributed=dist),
    })


    # s_total = 0.5*1 + 0.3*1 + 0.2*1 = 1.0
    assert result.slip_risk == pytest.approx(1.0, abs=1e-6)


def test_slip_confirmed_uses_fused_slip_risk():
    cfg = AdaptiveGraspConfig(
        slip_variance_baseline=0.0,
        slip_variance_threshold=1.0,
        slip_detect_debounce_cycles=2,
        slip_variance_weight=0.5,
        slip_direction_weight=0.3,
        slip_friction_weight=0.2,
    )
    analyzer = TactileAnalyzer(cfg)

    frame0 = [1, 0, 0, 1, 0, 0]
    for _ in range(3):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 0.01, distributed=frame0)})

    analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 0.01, distributed=frame0)})
    frame1 = [0, 1, 0, 0, 1, 0]
    result = analyzer.update({
        TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 0.01, distributed=frame1),
    })

    assert result.slip_confirmed is True


def test_slip_risk_fusion_formula():
    cfg = AdaptiveGraspConfig(
        slip_variance_baseline=0.0,
        slip_variance_threshold=1.0,
        slip_variance_weight=0.5,
        slip_direction_weight=0.3,
        slip_friction_weight=0.2,
    )
    analyzer = TactileAnalyzer(cfg)

    for _ in range(3):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0)})

    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 1.0)})

    # s_total = 0.5*1 + 0.3*0 + 0.2*1 = 0.7
    assert result.slip_risk == pytest.approx(0.7, abs=1e-6)


def test_per_finger_analysis_exposes_individual_slip_risk():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
        slip_variance_baseline=0.0,
        slip_variance_threshold=1.0,
        slip_variance_weight=0.5,
        slip_direction_weight=0.0,
        slip_friction_weight=0.5,
    )
    analyzer = TactileAnalyzer(cfg)

    for _ in range(3):
        analyzer.update(
            {
                TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0),
                TactileSensorId.FOREFINGER: FakeTactileInfo(0.0, 0.0, 1.0),
            }
        )
    result = analyzer.update(
        {
            TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 1.0),
            TactileSensorId.FOREFINGER: FakeTactileInfo(0.0, 0.0, 1.0),
        }
    )

    thumb_risk = result.per_finger[TactileSensorId.THUMB].slip_risk
    forefinger_risk = result.per_finger[TactileSensorId.FOREFINGER].slip_risk
    assert thumb_risk > forefinger_risk
    assert result.slip_risk == pytest.approx(max(thumb_risk, forefinger_risk))
