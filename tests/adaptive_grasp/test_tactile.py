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
        variance_baseline=0.0,
        variance_threshold=1.0,
        slip_detect_debounce_cycles=3,
        variance_weight=0.5,
        direction_weight=0.0,
        friction_weight=0.5,
    )
    analyzer = TactileAnalyzer(cfg)

    # 预填充窗口到长度 >= 3（恒定力，方差为 0，不影响 debounce）
    for _ in range(3):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0)})

    # 连续 3 个周期高风险：方差突增且摩擦利用率保持高位。
    for _ in range(3):
        data = {
            TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 1.0),
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


def test_direction_distance_zero_when_stable():
    cfg = AdaptiveGraspConfig(variance_baseline=0.0, variance_threshold=1.0)
    analyzer = TactileAnalyzer(cfg)

    # 稳定的力场分布：3 个点，Fx=1, Fy=0
    stable = [1, 0, 0, 1, 0, 0, 1, 0, 0]
    analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(3.0, 0.0, 1.0, distributed=stable)})
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(3.0, 0.0, 1.0, distributed=stable)})

    assert result.direction_distance == pytest.approx(0.0, abs=1e-9)


def test_direction_distance_one_when_orthogonal():
    cfg = AdaptiveGraspConfig(variance_baseline=0.0, variance_threshold=1.0)
    analyzer = TactileAnalyzer(cfg)

    frame1 = [1, 0, 0, 1, 0, 0, 1, 0, 0]
    # 力场完全转向：Fx=0, Fy=1
    frame2 = [0, 1, 0, 0, 1, 0, 0, 1, 0]
    analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 3.0, 1.0, distributed=frame1)})
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 3.0, 1.0, distributed=frame2)})

    # cos_x=0, cos_y=0 => d = sqrt(2)/sqrt(2) = 1
    assert result.direction_distance == pytest.approx(1.0, abs=1e-6)


def test_direction_distance_zero_on_first_cycle():
    cfg = AdaptiveGraspConfig(variance_baseline=0.0, variance_threshold=1.0)
    analyzer = TactileAnalyzer(cfg)

    distributed = [1, 0, 0, 2, 0, 0, 3, 0, 0]
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(6.0, 0.0, 1.0, distributed=distributed)})

    assert result.direction_distance == pytest.approx(0.0, abs=1e-9)


def test_direction_distance_with_multiple_fingers():
    cfg = AdaptiveGraspConfig(variance_baseline=0.0, variance_threshold=1.0)
    analyzer = TactileAnalyzer(cfg)

    f1 = [1, 0, 0, 1, 0, 0]
    f2 = [1, 0, 0, 1, 0, 0]
    analyzer.update({
        TactileSensorId.THUMB: FakeTactileInfo(2.0, 0.0, 1.0, distributed=f1),
        TactileSensorId.FOREFINGER: FakeTactileInfo(2.0, 0.0, 1.0, distributed=f2),
    })

    # 只有拇指方向变化
    f1_next = [0, 1, 0, 0, 1, 0]
    result = analyzer.update({
        TactileSensorId.THUMB: FakeTactileInfo(0.0, 2.0, 1.0, distributed=f1_next),
        TactileSensorId.FOREFINGER: FakeTactileInfo(2.0, 0.0, 1.0, distributed=f2),
    })

    # 有一只手指方向变了，d_k 应该 > 0
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
        variance_baseline=0.0,
        variance_threshold=1.0,
        variance_weight=0.5,
        direction_weight=0.3,
        friction_weight=0.2,
    )
    analyzer = TactileAnalyzer(cfg)

    frame1 = [1, 0, 0, 1, 0, 0]
    for _ in range(3):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 0.01, distributed=frame1)})

    # 方差突增 + 方向变化 + 高摩擦利用率。
    dist = [0, 1, 0, 0, 1, 0]
    result = analyzer.update({
        TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 0.01, distributed=dist),
    })

    # s_k=1.0, d_k=1.0, r_k≈1.0 (mu_eff=10/0.01=1000, mu_ref=0.5 => clip 1)
    # s_total = 0.5*1 + 0.3*1 + 0.2*1 = 1.0
    assert result.slip_risk == pytest.approx(1.0, abs=1e-6)


def test_slip_confirmed_uses_fused_slip_risk():
    cfg = AdaptiveGraspConfig(
        variance_baseline=0.0,
        variance_threshold=1.0,
        slip_detect_debounce_cycles=2,
        variance_weight=0.5,
        direction_weight=0.3,
        friction_weight=0.2,
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
    # 连续两周期 s_total >= 0.7，debounce=2 => confirmed
    assert result.slip_confirmed is True


def test_slip_risk_fusion_formula():
    cfg = AdaptiveGraspConfig(
        variance_baseline=0.0,
        variance_threshold=1.0,
        variance_weight=0.5,
        direction_weight=0.3,
        friction_weight=0.2,
    )
    analyzer = TactileAnalyzer(cfg)

    for _ in range(3):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0)})

    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 1.0)})
    # s_k=1.0, d_k=0（无distributed）, r_k=clip(10/0.5,0,1)=1.0
    # s_total = 0.5*1 + 0.3*0 + 0.2*1 = 0.7
    assert result.slip_risk == pytest.approx(0.7, abs=1e-6)


def test_per_finger_analysis_exposes_individual_slip_risk():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
        variance_baseline=0.0,
        variance_threshold=1.0,
        variance_weight=0.5,
        direction_weight=0.0,
        friction_weight=0.5,
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
