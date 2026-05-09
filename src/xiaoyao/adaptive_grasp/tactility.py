import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from xiaoyao.adaptive_grasp.utils import clip
from xiaoyao.dexhand import TactileSensorId
from .config import AdaptiveGraspConfig


@dataclass
class PerFingerAnalysis:
    variance: float #切向力合力方差
    s_k: float #基于方差的滑动风险
    d_k: float #方向余弦风险
    r_k: float #摩擦利用率
    s_total: float #融合风险
    slip_confirmed: bool #滑动确认
    fz: float #法向力


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
        # 只实例化活跃手指的滑动窗口，避免非参与手指产生噪声干扰
        self._windows: dict[TactileSensorId, deque[float]] = {
            finger: deque(maxlen=config.sliding_window_size)
            for finger in config.active_fingers
        }
        self._variance_normalizers: dict[TactileSensorId, OnlineWindowNormalizer] = {
            finger: OnlineWindowNormalizer(
                window_size=config.sliding_window_size,
                eps=config.epsilon,
            )
            for finger in config.active_fingers
        }
        self._slip_count: dict[TactileSensorId, int] = {}
        self._prev_fx: dict[TactileSensorId, list[float]] = {}
        self._prev_fy: dict[TactileSensorId, list[float]] = {}

    def set_friction_coeff(self, value: float) -> None:
        if value <= 0:
            raise ValueError("friction_coeff must be > 0")
        self._friction_coeff = value

    def update(self, tactile_data: dict[TactileSensorId, Any]) -> TactileAnalysis:
        cfg = self.config
        finger_fz: dict[TactileSensorId, float] = {}
        total_fz = 0.0
        per_finger: dict[TactileSensorId, PerFingerAnalysis] = {}

        for finger, info in tactile_data.items():
            if finger not in cfg.active_fingers:
                continue  # 跳过非活跃手指，避免不参与的手指产生误触发
            fx = info.get_force_x()
            fy = info.get_force_y()
            fz = abs(info.get_force_z())
            ft = math.sqrt(fx ** 2 + fy ** 2)
            self._windows[finger].append(ft)
            finger_fz[finger] = fz
            total_fz += fz

        for finger, info in tactile_data.items():
            if finger not in cfg.active_fingers:
                continue
            fz = finger_fz[finger]
            fx = info.get_force_x()
            fy = info.get_force_y()
            ft = math.sqrt(fx ** 2 + fy ** 2)

            # 逐指方差（基于该手指的滑动窗口）
            window = self._windows[finger]
            if len(window) >= 3:
                mean = sum(window) / len(window)
                var = sum((x - mean) ** 2 for x in window) / len(window)
            else:
                var = 0.0
            s_k = self._normalize_variance_with_window(finger, var)

            # 逐指方向一致性
            d_k = self._calculate_finger_direction_distance(finger, info)

            # 逐指摩擦利用率
            r_k = self._calculate_finger_friction_utilization(ft, fz)

            # 逐指融合
            s_total = min(1.0, max(0.0,
                cfg.variance_weight * s_k
                + cfg.direction_weight * d_k
                + cfg.friction_weight * r_k
            ))

            # 滑移次数统计
            count = self._slip_count.get(finger, 0)
            if s_total + cfg.epsilon >= 0.7:
                count += 1
            else:
                count = max(0, count - 1)
            self._slip_count[finger] = count
            finger_confirmed = count >= cfg.slip_detect_debounce_cycles

            per_finger[finger] = PerFingerAnalysis(
                variance=var,
                s_k=s_k,
                d_k=d_k,
                r_k=r_k,
                s_total=s_total,
                slip_confirmed=finger_confirmed,
                fz=fz,
            )

        # 全局汇总（取各指最大值/任一确认）
        variance = max((f.variance for f in per_finger.values()), default=0.0)
        slip_risk = max((f.s_total for f in per_finger.values()), default=0.0)
        direction_distance = max((f.d_k for f in per_finger.values()), default=0.0)
        friction_utilization = max((f.r_k for f in per_finger.values()), default=0.0)
        slip_confirmed = any(f.slip_confirmed for f in per_finger.values())

        return TactileAnalysis(
            variance=variance,
            slip_risk=slip_risk,
            direction_distance=direction_distance,
            friction_utilization=friction_utilization,
            slip_confirmed=slip_confirmed,
            finger_fz=finger_fz,
            total_fz=total_fz,
            per_finger=per_finger,
        )

    def reset(self) -> None:
        for window in self._windows.values():
            window.clear()
        for normalizer in self._variance_normalizers.values():
            normalizer.reset()
        # 只清理活跃手指的历史状态，避免残留数据影响下一轮控制
        self._slip_count = {f: 0 for f in self.config.active_fingers}
        self._prev_fx.clear()
        self._prev_fy.clear()

    def _normalize_variance_with_window(
        self,
        finger: TactileSensorId,
        variance: float,
    ) -> float:
        z_score = self._variance_normalizers[finger].update(variance)
        return clip(z_score, 0.0, 1.0)

    def _normalize_slip_risk(self, variance: float) -> float:
        cfg = self.config
        if variance <= cfg.variance_baseline:
            return 0.0
        if variance >= cfg.variance_threshold:
            return 1.0
        denom = (cfg.variance_threshold - cfg.variance_baseline) + cfg.epsilon
        return clip((variance - cfg.variance_baseline) / denom, 0, 1)

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
        mu_eff = ft / (fz + cfg.epsilon)
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
