from dataclasses import dataclass

from xiaoyao.dexhand import TactileSensorId

from .config import AdaptiveGraspConfig
from .force_reference_planner import ForceReferenceDecision
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
    ):
        self.config = config
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

    def compute(
        self,
        analysis: TactileAnalysis,
        force_reference: ForceReferenceDecision,
        dt: float,
    ) -> TorqueHoldDecision:
        force_refs = force_reference.force_refs
        finger_torques = {
            finger: self._compute_finger_torque(
                finger,
                force_refs.get(finger, 0.0),
                analysis.finger_fz.get(finger, 0.0),
                dt,
            )
            for finger in self.config.active_fingers
        }
        return TorqueHoldDecision(
            finger_torques=finger_torques,
            force_refs=force_refs,
            contact_ratios=force_reference.contact_ratios,
            F_ref_total=force_reference.F_ref_total,
        )

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
        return clip(torque, -100.0, self.config.max_torque)
