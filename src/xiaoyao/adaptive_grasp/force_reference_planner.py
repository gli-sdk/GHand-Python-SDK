from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from xiaoyao.dexhand import TactileSensorId

from .config import AdaptiveGraspConfig
from .object_profile import ObjectProfile
from .tactility import TactileAnalysis
from .utils import clip

if TYPE_CHECKING:
    from .grasp_sequence import ContactSnapshot


@dataclass(frozen=True)
class ForceReferenceDecision:
    force_refs: dict[TactileSensorId, float]
    contact_ratios: dict[TactileSensorId, float]
    F_ref_total: float


class ForceReferencePlanner:
    """Plans shared normal-force references for adaptive hold."""

    def __init__(
        self,
        config: AdaptiveGraspConfig,
        profile: Optional[ObjectProfile],
        contact_snapshot: "ContactSnapshot",
    ):
        self.config = config
        self.profile = profile
        self.contact_snapshot = contact_snapshot
        self.contact_ratios = self._compute_contact_ratios(contact_snapshot)
        self.F_ref_total = self._initial_force_ref(contact_snapshot)
        self._last_slip_confirmed = False
        self._stable_time_s = 0.0

    def compute(self, analysis: TactileAnalysis, dt: float) -> ForceReferenceDecision:
        self._update_total_force_ref(analysis, dt)
        return ForceReferenceDecision(
            force_refs=self._compute_finger_force_refs(),
            contact_ratios=dict(self.contact_ratios),
            F_ref_total=self.F_ref_total,
        )

    def minimum_force_ref(self) -> float:
        if self.profile is None:
            return 0.0
        return self.profile.safe_force_min

    def maximum_force_ref(self) -> float:
        if self.profile is None:
            return float(
                self.config.max_normal_force_per_finger
                * len(self.config.active_fingers)
            )
        return self.profile.safe_force_max

    def _update_total_force_ref(self, analysis: TactileAnalysis, dt: float) -> None:
        confirmed_rising_edge = (
            analysis.slip_confirmed and not self._last_slip_confirmed
        )
        if confirmed_rising_edge:
            self.F_ref_total += self.config.force_ref_confirmed_boost_n
            self._stable_time_s = 0.0

        if analysis.slip_risk >= self.config.force_ref_slip_warning_threshold:
            slip_excess = analysis.slip_risk - self.config.force_ref_slip_warning_threshold
            rise_step = self.config.force_ref_slip_gain_n_per_s * slip_excess * dt
            self.F_ref_total += min(rise_step, self.config.force_ref_max_rise_step_n)
            self._stable_time_s = 0.0
        elif analysis.slip_risk <= self.config.force_ref_stable_threshold:
            self._stable_time_s += dt
            if self._stable_time_s >= self.config.force_ref_stable_decay_delay_s:
                self.F_ref_total -= self.config.force_ref_decay_rate_n_per_s * dt
        else:
            self._stable_time_s = 0.0

        self.F_ref_total = self._clamp_force_ref(self.F_ref_total)
        self._last_slip_confirmed = analysis.slip_confirmed

    def _compute_contact_ratios(
        self,
        contact_snapshot: "ContactSnapshot",
    ) -> dict[TactileSensorId, float]:
        raw = {
            finger: max(0.0, contact_snapshot.finger_fz.get(finger, 0.0))
            for finger in self.config.active_fingers
        }
        total = sum(raw.values())
        if total <= 0.0:
            return self._uniform_contact_ratios()

        ratios = {
            finger: max(force / total, self.config.force_ref_min_contact_ratio)
            for finger, force in raw.items()
        }
        ratio_sum = sum(ratios.values())
        if ratio_sum <= 0.0:
            return self._uniform_contact_ratios()
        return {finger: ratio / ratio_sum for finger, ratio in ratios.items()}

    def _uniform_contact_ratios(self) -> dict[TactileSensorId, float]:
        active = set(self.config.active_fingers)
        if not active:
            return {}
        ratio = 1.0 / len(active)
        return {finger: ratio for finger in active}

    def _initial_force_ref(self, contact_snapshot: "ContactSnapshot") -> float:
        contact_force = max(0.0, contact_snapshot.total_fz)
        target = contact_force + self.config.force_ref_margin_n
        if self.profile is not None:
            target = max(target, self.profile.safe_force_min)
        return self._clamp_force_ref(target)

    def _clamp_force_ref(self, value: float) -> float:
        lower = self.minimum_force_ref()
        upper = self.maximum_force_ref()
        if upper < lower:
            return upper
        return clip(value, lower, upper)

    def _compute_finger_force_refs(self) -> dict[TactileSensorId, float]:
        return {
            finger: self.F_ref_total * self.contact_ratios.get(finger, 0.0)
            for finger in self.config.active_fingers
        }
