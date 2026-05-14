from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .adaptive_hold_loop import HoldStepResult


class GraspState(Enum):
    IDLE = "idle"
    OPEN = "open"
    PRE_GRASP = "pre_grasp"
    CLOSING_TO_CONTACT = "closing_to_contact"
    ADAPTIVE_HOLD = "adaptive_hold"
    RELEASE = "release"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"


class _HoldStepSensor(Protocol):
    @property
    def tactile_data(self) -> Optional[Any]:
        ...

    def data_age_s(self, current_time: float) -> Optional[float]:
        ...


@dataclass
class AdaptiveGraspRuntime:
    state: GraspState = GraspState.IDLE
    running: bool = False
    current_torque: int = 0
    object_profile: Optional[Any] = None
    adaptive_hold_started_at: Optional[float] = None
    last_contact_snapshot: Optional[Any] = None
    last_tactile_analysis: Optional[Any] = None
    last_safety_report: Optional[Any] = None
    last_force_decisions: Optional[Any] = None
    last_torque_hold_decision: Optional[Any] = None
    last_tactile_data_age_s: Optional[float] = None
    last_control_step_start_s: Optional[float] = None
    last_control_cycle_s: Optional[float] = None
    last_control_cycle_jitter_s: Optional[float] = None

    def reset_for_grasp(self) -> None:
        self.running = True
        self.state = GraspState.IDLE
        self.current_torque = 0
        self.object_profile = None
        self.adaptive_hold_started_at = None
        self.last_contact_snapshot = None
        self.last_tactile_analysis = None
        self.last_safety_report = None
        self.last_force_decisions = None
        self.last_torque_hold_decision = None
        self.last_tactile_data_age_s = None
        self.last_control_step_start_s = None
        self.last_control_cycle_s = None
        self.last_control_cycle_jitter_s = None

    def update_control_cycle_timing(
        self,
        step_start: float,
        *,
        control_period_s: float,
    ) -> None:
        if self.last_control_step_start_s is not None:
            control_cycle_s = step_start - self.last_control_step_start_s
            self.last_control_cycle_s = control_cycle_s
            self.last_control_cycle_jitter_s = control_cycle_s - control_period_s
        self.last_control_step_start_s = step_start

    def record_hold_step(
        self,
        step: "HoldStepResult",
        sensor: _HoldStepSensor,
        step_start: float,
    ) -> None:
        self.last_tactile_analysis = step.tactile_analysis
        self.last_safety_report = step.safety_report
        self.last_force_decisions = step.force_decisions
        self.last_torque_hold_decision = step.torque_hold_decision
        if step.current_torque is not None:
            self.current_torque = step.current_torque

        self.last_tactile_data_age_s = (
            sensor.data_age_s(step_start)
            if sensor.tactile_data is not None
            else None
        )
