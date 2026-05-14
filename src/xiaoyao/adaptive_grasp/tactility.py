import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from xiaoyao.adaptive_grasp.utils import clip
from xiaoyao.dexhand import TactileSensorId
from .config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.pid_controller import LowPassFilter

@dataclass(frozen=True)
class TactileLayoutPoint:
    index: int
    x: float
    y: float


_THUMB_TACTILE_COORDS: tuple[tuple[float, float], ...] = (
    (10, 385), (8, 338), (10, 286), (10, 238), (17, 191),
    (51, 402), (51, 347), (53, 292), (53, 239),
    (22, 139),
    (58, 184), (59, 130),
    (37, 66),
    (70, 88),
    (93, 408), (93, 354), (96, 296), (92, 238), (100, 178),
    (100, 118), (102, 66),
    (73, 27),
    (141, 411), (141, 358), (141, 300), (140, 238), (140, 176),
    (139, 113), (138, 58), (139, 13),
    (189, 355),
    (183, 179), (180, 116), (177, 67),
    (191, 409),
    (186, 297), (183, 239),
    (200, 27), (210, 89), (217, 130),
    (238, 67),
    (232, 403), (230, 347), (227, 292), (234, 238), (224, 185),
    (261, 190), (253, 138),
    (267, 338),
    (266, 285), (264, 240),
    (268, 386),
)


_FOUR_FINGER_TACTILE_COORDS: tuple[tuple[float, float], ...] = (
    (22, 365), (26, 297), (29, 235), (30, 172), (36, 107),
    (78, 285), (79, 227), (80, 172),
    (76, 348),
    (83, 116),
    (55, 38),
    (90, 70),
    (136, 339), (136, 275), (136, 223), (135, 171), (135, 122),
    (135, 75), (135, 20),
    (179, 70),
    (188, 347), (188, 285),
    (186, 116),
    (214, 38),
    (188, 226), (187, 171),
    (240, 364), (239, 298),
    (234, 172), (227, 107),
    (236, 235),
)


def _build_layout_points(coords: tuple[tuple[float, float], ...]) -> tuple[TactileLayoutPoint, ...]:
    return tuple(
        TactileLayoutPoint(index=index, x=float(x), y=float(y))
        for index, (x, y) in enumerate(coords)
    )


THUMB_TACTILE_LAYOUT_POINTS = _build_layout_points(_THUMB_TACTILE_COORDS)
FOUR_FINGER_TACTILE_LAYOUT_POINTS = _build_layout_points(_FOUR_FINGER_TACTILE_COORDS)


def get_tactile_layout_points(finger: TactileSensorId) -> tuple[TactileLayoutPoint, ...]:
    if finger == TactileSensorId.THUMB:
        return THUMB_TACTILE_LAYOUT_POINTS
    return FOUR_FINGER_TACTILE_LAYOUT_POINTS


@dataclass
class PerFingerAnalysis:
    variance: float
    s_k: float
    d_k: float
    r_k: float
    s_total: float
    slip_confirmed: bool
    fz: float
    fz_filtered: float

    @property
    def slip_risk(self) -> float:
        return self.s_total


@dataclass
class TactileAnalysis:
    variance: float
    slip_risk: float
    direction_distance: float
    friction_utilization: float
    slip_confirmed: bool
    finger_fz: dict[TactileSensorId, float]
    total_fz: float
    per_finger: dict[TactileSensorId, PerFingerAnalysis] = field(default_factory=dict)
    

@dataclass(frozen=True)
class FingerTactileSample:
    finger: TactileSensorId
    info: Any
    fx: float #x杞存柟鍚戝垏鍚戝姏
    fy: float #y杞存柟鍚戝垏鍚戝姏
    fz: float #娉曞悜鍔?
    ft: float #鍚堟垚鍒囧悜鍔?


class OnlineWindowNormalizer:
    def __init__(self, window_size: int, eps: float = 1e-6):
        self.window: deque[float] = deque(maxlen=window_size)
        self.eps = eps

    def update(self, x: float) -> float:
        self.window.append(float(x))
        mean = sum(self.window) / len(self.window)
        variance = sum((value - mean) ** 2 for value in self.window) / len(self.window)
        std = max(math.sqrt(variance), self.eps)
        return (x - mean) / std

    def reset(self) -> None:
        self.window.clear()


class TactileAnalyzer:
    def __init__(self, config: AdaptiveGraspConfig):
        self.config = config
        self._friction_coeff = config.default_friction_coeff
        self._windows: dict[TactileSensorId, deque[float]] = {
            finger: deque(maxlen=config.tactile_slip_window_size)
            for finger in config.active_fingers
        }
        self._variance_normalizers: dict[TactileSensorId, OnlineWindowNormalizer] = {
            finger: OnlineWindowNormalizer(
                window_size=config.tactile_slip_window_size,
                eps=config.numeric_epsilon,
            )
            for finger in config.active_fingers
        }
        self._slip_count: dict[TactileSensorId, int] = {}
        self._prev_fx: dict[TactileSensorId, list[float]] = {}
        self._prev_fy: dict[TactileSensorId, list[float]] = {}
        self._fz_filters: dict[TactileSensorId, LowPassFilter] = {
            finger: LowPassFilter(alpha=config.tactile_lowpass_alpha)
            for finger in config.active_fingers
        }
    def set_friction_coeff(self, value: float) -> None:
        if value <= 0:
            raise ValueError("friction_coeff must be > 0")
        self._friction_coeff = value

    def update(self, tactile_data: dict[TactileSensorId, Any]) -> TactileAnalysis:
        samples = self._collect_active_samples(tactile_data)
        per_finger = {
            sample.finger: self._analyze_finger(sample)
            for sample in samples
        }
        return self._build_analysis(samples, per_finger)

    def reset(self) -> None:
        for window in self._windows.values():
            window.clear()
        for normalizer in self._variance_normalizers.values():
            normalizer.reset()
        self._slip_count = {f: 0 for f in self.config.active_fingers}
        self._prev_fx.clear()
        self._prev_fy.clear()
        for fz_filter in self._fz_filters.values():
            fz_filter.reset()

    def _collect_active_samples(
        self,
        tactile_data: dict[TactileSensorId, Any],
    ) -> list[FingerTactileSample]:
        samples: list[FingerTactileSample] = []
        for finger, info in tactile_data.items():
            if finger not in self.config.active_fingers:
                continue
            fx = info.get_force_x()
            fy = info.get_force_y()
            fz = abs(info.get_force_z())
            ft = math.sqrt(fx ** 2 + fy ** 2)
            self._windows[finger].append(ft)
            samples.append(FingerTactileSample(finger, info, fx, fy, fz, ft))
        return samples

    def _analyze_finger(self, sample: FingerTactileSample) -> PerFingerAnalysis:
        variance = self._calculate_tangential_variance(sample.finger)
        s_k = self._normalize_variance_with_window(sample.finger, variance)
        d_k = self._calculate_finger_direction_distance(sample.finger, sample.info)
        r_k = self._calculate_finger_friction_utilization(sample.ft, sample.fz)
        s_total = self._fuse_slip_risk(s_k, d_k, r_k)
        slip_confirmed = self._update_slip_debounce(sample.finger, s_total)
        fz_filtered = self._fz_filters[sample.finger].compute(sample.fz)
        return PerFingerAnalysis(
            variance=variance,
            s_k=s_k,
            d_k=d_k,
            r_k=r_k,
            s_total=s_total,
            slip_confirmed=slip_confirmed,
            fz=sample.fz,
            fz_filtered=fz_filtered,
        )

    def _build_analysis(
        self,
        samples: list[FingerTactileSample],
        per_finger: dict[TactileSensorId, PerFingerAnalysis],
    ) -> TactileAnalysis:
        finger_fz = {sample.finger: sample.fz for sample in samples}
        return TactileAnalysis(
            variance=max((f.variance for f in per_finger.values()), default=0.0),
            slip_risk=max((f.s_total for f in per_finger.values()), default=0.0),
            direction_distance=max((f.d_k for f in per_finger.values()), default=0.0),
            friction_utilization=max((f.r_k for f in per_finger.values()), default=0.0),
            slip_confirmed=any(f.slip_confirmed for f in per_finger.values()),
            finger_fz=finger_fz,
            total_fz=sum(finger_fz.values()),
            per_finger=per_finger,
        )

    def _calculate_tangential_variance(self, finger: TactileSensorId) -> float:
        window = self._windows[finger]
        if len(window) < 3:
            return 0.0
        mean = sum(window) / len(window)
        return sum((x - mean) ** 2 for x in window) / len(window)

    def _normalize_variance_with_window(
        self,
        finger: TactileSensorId,
        variance: float,
    ) -> float:
        z_score = self._variance_normalizers[finger].update(variance)
        return clip(z_score, 0.0, 1.0)

    def _normalize_slip_risk(self, variance: float) -> float:
        cfg = self.config
        if variance <= cfg.slip_variance_baseline:
            return 0.0
        if variance >= cfg.slip_variance_threshold:
            return 1.0
        denom = (cfg.slip_variance_threshold - cfg.slip_variance_baseline) + cfg.numeric_epsilon
        return clip((variance - cfg.slip_variance_baseline) / denom, 0, 1)

    def _fuse_slip_risk(self, s_k: float, d_k: float, r_k: float) -> float:
        cfg = self.config
        return clip(
            cfg.slip_variance_weight * s_k
            + cfg.slip_direction_weight * d_k
            + cfg.slip_friction_weight * r_k,
            0.0,
            1.0,
        )

    def _update_slip_debounce(self, finger: TactileSensorId, slip_risk: float) -> bool:
        count = self._slip_count.get(finger, 0)
        if slip_risk + self.config.numeric_epsilon >= 0.7:
            count += 1
        else:
            count = max(0, count - 1)
        self._slip_count[finger] = count
        return count >= self.config.slip_detect_debounce_cycles

    def _calculate_finger_direction_distance(
        self, finger: TactileSensorId, info: Any
    ) -> float:
        distributed = (
            info.get_distributed_force()
            if hasattr(info, "get_distributed_force")
            else []
        )
        if len(distributed) < 3:
            return 0.0
        fx_vec = [float(distributed[i]) for i in range(0, len(distributed), 3)]
        fy_vec = [float(distributed[i]) for i in range(1, len(distributed), 3)]

        prev_fx = self._prev_fx.get(finger)
        prev_fy = self._prev_fy.get(finger)
        if prev_fx is None or prev_fy is None:
            self._prev_fx[finger] = fx_vec
            self._prev_fy[finger] = fy_vec
            return 0.0

        cos_x = self._cosine_similarity(fx_vec, prev_fx)
        cos_y = self._cosine_similarity(fy_vec, prev_fy)
        d = math.sqrt((1.0 - cos_x) ** 2 + (1.0 - cos_y) ** 2) / math.sqrt(2.0)
        d = min(1.0, max(0.0, d))

        self._prev_fx[finger] = fx_vec
        self._prev_fy[finger] = fy_vec
        return d

    def _calculate_finger_friction_utilization(self, ft: float, fz: float) -> float:
        cfg = self.config
        mu_ref = self._friction_coeff
        mu_eff = ft / (fz + cfg.numeric_epsilon)
        return min(1.0, max(0.0, mu_eff / mu_ref))

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 and norm_b == 0.0:
            return 1.0
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return min(1.0, max(-1.0, dot / (norm_a * norm_b)))
