from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import TactileSensorId

from .config import AdaptiveGraspConfig
from .grasp_sequence import ContactSnapshot
from .object_profile import ObjectProfile
from .pid_controller import PidController, PidParams
from .tactility import TactileAnalysis
from .utils import clip


@dataclass(frozen=True)
class TorqueHoldDecision:
    finger_torques: dict[TactileSensorId, float]
    force_refs: dict[TactileSensorId, float]
    contact_ratios: dict[TactileSensorId, float]
    F_ref_total: float


class TorqueHoldPlanner:
    """Plans per-finger torque commands for torque-mode adaptive hold."""

    def __init__(
        self,
        config: AdaptiveGraspConfig,
        profile: Optional[ObjectProfile],
        contact_snapshot: ContactSnapshot,
    ):
        self.config = config
        self.profile = profile
        self.contact_snapshot = contact_snapshot
        self.contact_ratios = self._compute_contact_ratios(contact_snapshot)
        self.F_ref_total = self._initial_force_ref(contact_snapshot)
        self._pid_by_finger = {
            finger: PidController(
                PidParams(
                    K_p=config.torque_hold_K_p,
                    K_i=config.torque_hold_K_i,
                    K_d=config.torque_hold_K_d,
                    I_min=config.torque_hold_I_min,
                    I_max=config.torque_hold_I_max,
                )
            )
            for finger in config.active_fingers
        }
        self._last_slip_confirmed = False
        self._stable_time_s = 0.0

    def compute(self, analysis: TactileAnalysis, dt: float) -> TorqueHoldDecision:
        self._update_total_force_ref(analysis, dt)
        force_refs = self._compute_finger_force_refs()
        finger_torques = {
            finger: self._compute_finger_torque(
                finger,
                force_refs[finger],
                analysis.finger_fz.get(finger, 0.0),
                dt,
            )
            for finger in self.config.active_fingers
        }
        return TorqueHoldDecision(
            finger_torques=finger_torques,
            force_refs=force_refs,
            contact_ratios=dict(self.contact_ratios),
            F_ref_total=self.F_ref_total,
        )

    def _update_total_force_ref(self, analysis: TactileAnalysis, dt: float) -> None:
        warning_threshold = self.config.torque_hold_slip_warning_threshold
        stable_threshold = self.config.torque_hold_stable_threshold
        slip_gain = self.config.torque_hold_slip_gain_n_per_s
        max_rise_step = self.config.torque_hold_max_rise_step_n
        boost = self.config.torque_hold_confirmed_boost_n
        decay_rate = self.config.torque_hold_decay_rate_n_per_s
        decay_delay = self.config.torque_hold_stable_decay_delay_s

        confirmed_rising_edge = (
            analysis.slip_confirmed and not self._last_slip_confirmed
        )
        if confirmed_rising_edge:
            self.F_ref_total += boost
            self._stable_time_s = 0.0

        if analysis.slip_risk >= warning_threshold:
            slip_excess = analysis.slip_risk - warning_threshold
            rise_step = slip_gain * slip_excess * dt
            self.F_ref_total += min(rise_step, max_rise_step)
            self._stable_time_s = 0.0
        elif analysis.slip_risk <= stable_threshold:
            self._stable_time_s += dt
            if self._stable_time_s >= decay_delay:
                self.F_ref_total -= decay_rate * dt
        else:
            self._stable_time_s = 0.0

        self.F_ref_total = self._clamp_force_ref(self.F_ref_total)
        self._last_slip_confirmed = analysis.slip_confirmed

    def _compute_contact_ratios(
        self,
        contact_snapshot: ContactSnapshot,
    ) -> dict[TactileSensorId, float]:
        raw = {
            finger: max(0.0, contact_snapshot.finger_fz.get(finger, 0.0))
            for finger in self.config.active_fingers
        }
        total = sum(raw.values())
        if total <= 0.0:
            return self._uniform_contact_ratios()

        ratios = {
            finger: max(force / total, self.config.torque_hold_min_contact_ratio)
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

    def _initial_force_ref(self, contact_snapshot: ContactSnapshot) -> float:
        contact_force = max(0.0, contact_snapshot.total_fz)
        target = contact_force + self.config.torque_hold_force_margin_n
        if self.profile is not None:
            target = max(target, self.profile.safe_force_min)
        return self._clamp_force_ref(target)

    def _minimum_force_ref(self) -> float:
        if self.profile is None:
            return 0.0
        return self.profile.safe_force_min

    def _maximum_force_ref(self) -> float:
        if self.profile is None:
            return float(
                self.config.max_normal_force_per_finger
                * len(self.config.active_fingers)
            )
        return self.profile.safe_force_max

    def _clamp_force_ref(self, value: float) -> float:
        lower = self._minimum_force_ref()
        upper = self._maximum_force_ref()
        if upper < lower:
            return upper
        return clip(value, lower, upper)

    def _compute_finger_force_refs(self) -> dict[TactileSensorId, float]:
        return {
            finger: self.F_ref_total * self.contact_ratios.get(finger, 0.0)
            for finger in self.config.active_fingers
        }

    def _initial_hold_torque(self) -> int:
        return self.config.adaptive_hold_torque

    def _compute_finger_torque(
        self,
        finger: TactileSensorId,
        force_ref: float,
        force_actual: float,
        dt: float,
    ) -> float:
        error = force_ref - force_actual
        pid_u = self._pid_by_finger[finger].compute(error=error, dt=dt)
        torque = self._initial_hold_torque() + pid_u
        return clip(torque, 0.0, self.config.max_torque)
