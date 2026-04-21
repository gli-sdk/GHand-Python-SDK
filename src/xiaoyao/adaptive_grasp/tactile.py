import math
from collections import deque
from dataclasses import dataclass
from typing import Any

from xiaoyao.dexhand import TactileSensorId
from .config import AdaptiveGraspConfig


@dataclass
class TactileAnalysis:
    variance: float
    slip_risk: float
    slip_confirmed: bool
    finger_fz: dict[TactileSensorId, float]
    total_fz: float


class TactileAnalyzer:
    def __init__(self, config: AdaptiveGraspConfig):
        self.config = config
        self._windows: dict[TactileSensorId, deque[float]] = {
            finger: deque(maxlen=config.sliding_window_size)
            for finger in TactileSensorId
        }
        self._slip_count: int = 0

    def update(self, tactile_data: dict[TactileSensorId, Any]) -> TactileAnalysis:
        cfg = self.config
        finger_fz: dict[TactileSensorId, float] = {}
        total_fz = 0.0

        for finger, info in tactile_data.items():
            fx = info.get_force_x()
            fy = info.get_force_y()
            fz = abs(info.get_force_z())
            ft = math.sqrt(fx ** 2 + fy ** 2)
            self._windows[finger].append(ft)
            finger_fz[finger] = fz
            total_fz += fz

        variance = self._calculate_variance()
        slip_risk = self._normalize_slip_risk(variance)

        if slip_risk >= 0.5:
            self._slip_count += 1
        else:
            self._slip_count = max(0, self._slip_count - 1)

        slip_confirmed = self._slip_count >= cfg.slip_detect_debounce_cycles

        return TactileAnalysis(
            variance=variance,
            slip_risk=slip_risk,
            slip_confirmed=slip_confirmed,
            finger_fz=finger_fz,
            total_fz=total_fz,
        )

    def reset(self) -> None:
        for window in self._windows.values():
            window.clear()
        self._slip_count = 0

    def _calculate_variance(self) -> float:
        values = []
        for window in self._windows.values():
            if len(window) < 3:
                continue
            mean = sum(window) / len(window)
            var = sum((x - mean) ** 2 for x in window) / len(window)
            values.append(var)
        return max(values) if values else 0.0

    def _normalize_slip_risk(self, variance: float) -> float:
        cfg = self.config
        if variance <= cfg.variance_baseline:
            return 0.0
        if variance >= cfg.variance_threshold:
            return 1.0
        denom = (cfg.variance_threshold - cfg.variance_baseline) + cfg.epsilon
        return min(1.0, max(0.0, (variance - cfg.variance_baseline) / denom))
