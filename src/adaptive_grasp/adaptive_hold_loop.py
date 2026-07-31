import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional, Protocol

from ghand import CtrlMode, JointCommand, JointId, TactileSensorId
from .config import AdaptiveGraspConfig, HoldCommandMode
from .force_reference_planner import ForceReferencePlanner
from .incremental_position_hold_planner import IncrementalPositionHoldPlanner
from .joint_builder import JointCommandBuilder
from .position_hold_planner import ForceDecision, PositionHoldPlanner
from .ports import HandCommandPort, SensorFrameSource
from .safety import SafetyMonitor, SafetyReport, SafetyStatus
from .runtime import GraspState
from .tactility import TactileAnalyzer, TactileAnalysis
from .utils import normalize_joint_angles, normalize_joint_id
from .visualization import TactileVisualizer

_logger = logging.getLogger("adaptive_grasp.adaptive_hold_loop")
_MAX_CONTROL_DT_S = 1.0
_POSITION_HOLD_THUMB_AUX_JOINTS = (
    JointId.THUMB_TMC_AA,
    JointId.THUMB_TMC_PS,
)
_POSITION_HOLD_MODES_WITH_THUMB_AUX = {
    HoldCommandMode.POSITION,
    HoldCommandMode.STIFF_POSITION,
}

ForceDecisions = dict[TactileSensorId, ForceDecision]
JointAngles = dict[JointId, float]
TactileData = dict[TactileSensorId, Any]


class HoldResult(Enum):
    CONTINUE = auto()
    AUTO_RELEASE = auto()
    FAULT_RELEASE = auto()
    ERROR = auto()


@dataclass
class HoldStepResult:
    result: HoldResult
    tactile_analysis: Optional[TactileAnalysis] = None
    safety_report: Optional[SafetyReport] = None
    force_decisions: Optional[ForceDecisions] = None
    current_torque: Optional[int] = None


@dataclass
class PositionHoldCommand:
    angles: JointAngles
    torque: int
    speed: int
    decisions: ForceDecisions
    force_refs: Optional[dict[TactileSensorId, float]] = None


HoldCommand = PositionHoldCommand


@dataclass(frozen=True)
class _HoldSensorFrame:
    tactile_data: Optional[TactileData]
    joint_feedback: Optional[list[JointCommand]]
    sample_time_s: Optional[float]
    current_angles: JointAngles


class HoldObserver(Protocol):

    def on_hold_step(
        self,
        *,
        tactile_data: TactileData,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        current_time: float,
        force_refs: Optional[dict[TactileSensorId, float]] = None,
    ) -> None:
        ...


class _VisualizerHoldObserver:

    def __init__(self, visualizer: TactileVisualizer):
        self._visualizer = visualizer

    def on_hold_step(
        self,
        *,
        tactile_data: TactileData,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        current_time: float,
        force_refs: Optional[dict[TactileSensorId, float]] = None,
    ) -> None:
        self._visualizer.update(
            tactile_data,
            analysis,
            joint_angles=current_angles,
            force_refs=force_refs,
            timestamp=current_time,
        )


class HoldController:
    """Runs one adaptive-hold control cycle at a time."""

    def __init__(
        self,
        hand: HandCommandPort,
        sensor: SensorFrameSource,
        safety: SafetyMonitor,
        tactile: TactileAnalyzer,
        visualizer: Optional[TactileVisualizer],
        joint_builder: JointCommandBuilder,
        config: AdaptiveGraspConfig,
        current_torque: int,
        contact_joint_angles: Optional[JointAngles] = None,
        force_reference_planner: Optional[ForceReferencePlanner] = None,
        position_hold_planner: Optional[PositionHoldPlanner] = None,
        stiff_position_hold_planner: Optional[
            IncrementalPositionHoldPlanner] = None,
        observer: Optional[HoldObserver] = None,
        hold_target_force_n: Optional[float] = None,
    ):
        self.hand = hand
        self._sensor = sensor
        self._safety = safety
        self._tactile = tactile
        self._joint_builder = joint_builder
        self.config = config
        self._current_torque = current_torque
        self._contact_joint_angles = normalize_joint_angles(
            contact_joint_angles or {})
        self._force_reference_planner = force_reference_planner
        self._position_hold_planner = position_hold_planner
        self._stiff_position_hold_planner = stiff_position_hold_planner
        self._hold_target_force_n = hold_target_force_n
        self._observer = observer or (_VisualizerHoldObserver(visualizer)
                                      if visualizer is not None else None)
        self._last_sample_time_s: Optional[float] = None
        self._consecutive_move_failures = 0
        self._max_consecutive_move_failures = self.config.position_hold_move_failure_limit

    def run_step(self, current_time: float) -> HoldStepResult:
        frame = self._read_hold_frame()

        safety = self._safety.check(
            frame.tactile_data,
            frame.joint_feedback,
            GraspState.ADAPTIVE_HOLD,
        )
        if safety.status == SafetyStatus.FAULT:
            return self._fault_result(safety)

        if frame.tactile_data is None:
            return HoldStepResult(
                result=HoldResult.CONTINUE,
                safety_report=safety,
                current_torque=self._current_torque,
            )

        analysis = self._tactile.update(frame.tactile_data)
        dt = self._compute_dt(frame.sample_time_s)
        command = self._plan_hold_command(analysis, frame.current_angles, dt)
        self._notify_hold_observer(
            frame.tactile_data,
            analysis,
            frame.current_angles,
            current_time,
            command.force_refs,
        )
        execute_result = self._execute_hold_command(command, analysis, safety)
        if execute_result is not None:
            return execute_result

        return HoldStepResult(
            result=HoldResult.CONTINUE,
            tactile_analysis=analysis,
            safety_report=safety,
            force_decisions=command.decisions,
            current_torque=self._current_torque,
        )

    def _read_hold_frame(self) -> _HoldSensorFrame:
        tactile_data = self._sensor.tactile_data
        joint_feedback = self._sensor.joint_feedback
        sample_time_s = self._sensor.sample_time_s
        return _HoldSensorFrame(
            tactile_data=tactile_data,
            joint_feedback=joint_feedback,
            sample_time_s=sample_time_s,
            current_angles=self._get_current_angles(joint_feedback),
        )

    def _compute_dt(self, sample_time_s: Optional[float]) -> float:
        if not isinstance(sample_time_s, (int, float)):
            sample_time_s = None

        if sample_time_s is None or self._last_sample_time_s is None:
            dt = self.config.control_period_s
        else:
            dt = sample_time_s - self._last_sample_time_s
            if dt <= 0.0 or dt > _MAX_CONTROL_DT_S:
                dt = self.config.control_period_s
        # Keep a valid sample timestamp as the next baseline even when dt falls back.
        self._last_sample_time_s = sample_time_s
        return dt

    def _fault_result(self, safety: SafetyReport) -> HoldStepResult:
        result = (HoldResult.FAULT_RELEASE
                  if self.config.enable_fault_release_fallback else
                  HoldResult.ERROR)
        return HoldStepResult(
            result=result,
            safety_report=safety,
            current_torque=self._current_torque,
        )

    def _notify_hold_observer(
        self,
        tactile_data: TactileData,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        current_time: float,
        force_refs: Optional[dict[TactileSensorId, float]] = None,
    ) -> None:
        if self._observer is None:
            return
        self._observer.on_hold_step(
            tactile_data=tactile_data,
            analysis=analysis,
            current_angles=current_angles,
            current_time=current_time,
            force_refs=force_refs,
        )

    def _plan_hold_command(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        dt: float,
    ) -> HoldCommand:
        if self._can_plan_stiff_position_hold():
            return self._plan_stiff_position_hold_command(
                analysis, current_angles)

        if self._can_plan_position_hold():
            return self._plan_position_hold_command(analysis, current_angles,
                                                    dt)

        return PositionHoldCommand(
            angles=current_angles,
            torque=self._current_torque,
            speed=0,
            decisions={},
        )

    def _can_plan_position_hold(self) -> bool:
        return (self.config.hold_command_mode is HoldCommandMode.POSITION
                and self._position_hold_planner is not None
                and self._force_reference_planner is not None)

    def _can_plan_stiff_position_hold(self) -> bool:
        return (self.config.hold_command_mode is HoldCommandMode.STIFF_POSITION
                and self._stiff_position_hold_planner is not None)

    def _plan_stiff_position_hold_command(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
    ) -> PositionHoldCommand:
        assert self._stiff_position_hold_planner is not None
        decisions = self._stiff_position_hold_planner.compute(
            analysis,
            current_angles,
            target_force_n=self._hold_target_force_n,
        )
        return PositionHoldCommand(
            angles=self._merge_target_angles(current_angles, decisions),
            torque=self._next_torque(decisions),
            speed=self._next_speed(decisions),
            decisions=decisions,
            force_refs=None,
        )

    def _plan_position_hold_command(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        dt: float,
    ) -> PositionHoldCommand:
        force_reference = self._force_reference_planner.compute(analysis,
                                                                dt=dt)
        decisions = self._position_hold_planner.compute(
            analysis,
            current_angles,
            force_reference,
            dt=dt,
        )
        return PositionHoldCommand(
            angles=self._merge_target_angles(current_angles, decisions),
            torque=self._next_torque(decisions),
            speed=self._next_speed(decisions),
            decisions=decisions,
            force_refs=force_reference.force_refs,
        )

    def _merge_target_angles(
        self,
        current_angles: JointAngles,
        decisions: ForceDecisions,
    ) -> JointAngles:
        next_angles = dict(current_angles)
        for decision in decisions.values():
            next_angles.update(decision.target_angles)
        return next_angles

    def _next_torque(self, decisions: ForceDecisions) -> int:
        if not decisions:
            return self._current_torque
        # Position hold applies one shared torque/speed to all active fingers;
        # individual ForceDecision values are expected to carry the same command.
        return next(iter(decisions.values())).next_torque

    def _next_speed(self, decisions: ForceDecisions) -> int:
        if not decisions:
            return 0
        # Position hold applies one shared torque/speed to all active fingers;
        # individual ForceDecision values are expected to carry the same command.
        next_speed = next(iter(decisions.values())).next_speed
        return 0 if next_speed is None else next_speed

    def _execute_hold_command(
        self,
        command: HoldCommand,
        analysis: TactileAnalysis,
        safety: SafetyReport,
    ) -> Optional[HoldStepResult]:
        joints, mode, next_torque = self._build_hold_payload(command)
        ok = self.hand.move_joints(joints, mode=mode)
        if ok:
            self._consecutive_move_failures = 0
            self._current_torque = next_torque
            return None

        self._consecutive_move_failures += 1
        _logger.error(
            "ADAPTIVE_HOLD: move_joints failed (%d/%d)",
            self._consecutive_move_failures,
            self._max_consecutive_move_failures,
        )
        if self._consecutive_move_failures < self._max_consecutive_move_failures:
            return None

        return HoldStepResult(
            result=HoldResult.ERROR,
            tactile_analysis=analysis,
            safety_report=safety,
            current_torque=self._current_torque,
        )

    def _build_hold_payload(
            self,
            command: HoldCommand) -> tuple[list[JointCommand], CtrlMode, int]:
        angles = self._clamp_to_contact_window(command.angles)
        joints = self._joint_builder.hold_position_command(
            command.torque,
            angles,
            speed=command.speed,
        )
        self._append_position_hold_thumb_aux_commands(joints)
        return joints, CtrlMode.POSITION, command.torque

    def _append_position_hold_thumb_aux_commands(
        self,
        joints: list[JointCommand],
    ) -> None:
        if self.config.hold_command_mode not in _POSITION_HOLD_MODES_WITH_THUMB_AUX:
            return

        command_by_id = {JointId(command.id): command for command in joints}
        for joint_id in _POSITION_HOLD_THUMB_AUX_JOINTS:
            if joint_id not in self._contact_joint_angles:
                continue

            command = command_by_id.get(joint_id)
            if command is None:
                joints.append(
                    JointCommand(
                        id=joint_id,
                        angle=self._contact_joint_angles[joint_id],
                        speed=100,
                        torque=100,
                    ))
                continue

            command.angle = self._contact_joint_angles[joint_id]
            command.speed = 100
            command.torque = 100

    def _clamp_to_contact_window(self, angles: JointAngles) -> JointAngles:
        if not self._contact_joint_angles:
            return angles

        clamped_angles = dict(angles)
        for joint_id, base_angle in self._contact_joint_angles.items():
            if joint_id not in clamped_angles:
                continue
            guard_margin = (
                self.config.position_hold_contact_angle_guard_margin_deg)
            lower = base_angle - guard_margin
            upper = base_angle + guard_margin
            clamped_angles[joint_id] = max(
                lower, min(clamped_angles[joint_id], upper))
        return clamped_angles

    def _get_current_angles(
            self, joint_feedback: Optional[list[JointCommand]]) -> JointAngles:
        if joint_feedback:
            return {normalize_joint_id(j.id): j.angle for j in joint_feedback}
        if self._contact_joint_angles:
            return dict(self._contact_joint_angles)
        return self._joint_builder.init_hold_angles()
