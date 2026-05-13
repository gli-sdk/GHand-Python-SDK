import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional

from xiaoyao.dexhand import CtrlMode, Joint, JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .force_reference_planner import ForceReferencePlanner
from .joint_builder import JointCommandBuilder
from .position_hold_planner import ForceDecision, PositionHoldPlanner
from .ports import HandCommandPort, SensorFrameSource
from .safety import SafetyMonitor, SafetyReport, SafetyStatus
from .states import GraspState
from .tactility import TactileAnalyzer, TactileAnalysis
from .torque_hold_planner import TorqueHoldDecision, TorqueHoldPlanner
from .utils import clip
from .visualization import TactileVisualizer

_logger = logging.getLogger("xiaoyao.adaptive_grasp.adaptive_hold_loop")

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
    torque_hold_decision: Optional[TorqueHoldDecision] = None
    current_torque: Optional[int] = None


@dataclass
class _HoldCommand:
    mode: CtrlMode
    angles: JointAngles
    torque: int
    speed: Optional[int] = None
    decisions: Optional[ForceDecisions] = None
    finger_torques: Optional[dict[TactileSensorId, float]] = None
    torque_hold_decision: Optional[TorqueHoldDecision] = None
    force_refs: Optional[dict[TactileSensorId, float]] = None


@dataclass(frozen=True)
class _HoldSensorFrame:
    tactile_data: Optional[TactileData]
    joint_feedback: Optional[list[Joint]]
    sample_time_s: Optional[float]
    current_angles: JointAngles


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
        torque_hold_planner: Optional[TorqueHoldPlanner] = None,
        force_reference_planner: Optional[ForceReferencePlanner] = None,
        position_hold_planner: Optional[PositionHoldPlanner] = None,
    ):
        self.hand = hand
        self._sensor = sensor
        self._safety = safety
        self._tactile = tactile
        self._visualizer = visualizer
        self._joint_builder = joint_builder
        self.config = config
        self._current_torque = current_torque
        self._contact_joint_angles = dict(contact_joint_angles or {})
        self._torque_hold_planner = torque_hold_planner
        self._force_reference_planner = force_reference_planner
        self._position_hold_planner = position_hold_planner
        self._last_sample_time_s: Optional[float] = None
        self._consecutive_move_failures = 0
        self._max_consecutive_move_failures = self.config.adaptive_hold_move_failure_limit

    def apply_torque_hold(self) -> bool:
        """Hold with torque mode by commanding active fingers' MCP/PIP joints."""
        joints = self._joint_builder.hold_torque_command(self.config.torque_hold_base_torque)
        return self.hand.move_joints(joints, mode=CtrlMode.TORQUE)

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
        self._update_visualizer(
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
            torque_hold_decision=command.torque_hold_decision,
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
            if dt <= 0.0 or dt > 1.0:
                dt = self.config.control_period_s
        self._last_sample_time_s = sample_time_s
        return dt

    def _fault_result(self, safety: SafetyReport) -> HoldStepResult:
        result = (
            HoldResult.FAULT_RELEASE
            if self.config.enable_fault_release_fallback
            else HoldResult.ERROR
        )
        return HoldStepResult(
            result=result,
            safety_report=safety,
            current_torque=self._current_torque,
        )

    def _update_visualizer(
        self,
        tactile_data: TactileData,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        current_time: float,
        force_refs: Optional[dict[TactileSensorId, float]] = None,
    ) -> None:
        if self._visualizer is None:
            return
        self._visualizer.update(
            tactile_data,
            analysis,
            joint_angles=current_angles,
            force_refs=force_refs,
            timestamp=current_time,
        )

    def _plan_hold_command(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        dt: float,
    ) -> _HoldCommand:
        if self._can_plan_torque_hold():
            return self._plan_torque_hold_command(analysis, current_angles, dt)

        if self._can_plan_position_hold():
            return self._plan_position_hold_command(analysis, current_angles, dt)

        return _HoldCommand(
            mode=self._default_hold_mode(),
            angles=current_angles,
            torque=self._default_hold_torque(),
        )

    def _can_plan_torque_hold(self) -> bool:
        return (
            self.config.adaptive_hold_command_mode == "torque"
            and self._torque_hold_planner is not None
            and self._force_reference_planner is not None
        )

    def _can_plan_position_hold(self) -> bool:
        return (
            self.config.adaptive_hold_command_mode == "position"
            and self._position_hold_planner is not None
            and self._force_reference_planner is not None
        )

    def _plan_torque_hold_command(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        dt: float,
    ) -> _HoldCommand:
        force_reference = self._force_reference_planner.compute(analysis, dt=dt)
        decision = self._torque_hold_planner.compute(
            analysis,
            force_reference,
            dt=dt,
        )
        return _HoldCommand(
            mode=CtrlMode.TORQUE,
            angles=current_angles,
            torque=self._max_rounded_torque(decision.finger_torques, self._current_torque),
            finger_torques=decision.finger_torques,
            torque_hold_decision=decision,
            force_refs=force_reference.force_refs,
        )

    def _plan_position_hold_command(
        self,
        analysis: TactileAnalysis,
        current_angles: JointAngles,
        dt: float,
    ) -> _HoldCommand:
        force_reference = self._force_reference_planner.compute(analysis, dt=dt)
        decisions = self._position_hold_planner.compute(
            analysis,
            current_angles,
            force_reference,
            dt=dt,
        )
        return _HoldCommand(
            mode=CtrlMode.POSITION,
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
        return next(iter(decisions.values())).next_torque

    def _next_speed(self, decisions: ForceDecisions) -> int:
        if not decisions:
            return 0
        next_speed = next(iter(decisions.values())).next_speed
        return 0 if next_speed is None else next_speed

    def _default_hold_torque(self) -> int:
        if self.config.adaptive_hold_command_mode == "torque":
            return self.config.torque_hold_base_torque
        return self._current_torque

    def _default_hold_mode(self) -> CtrlMode:
        if self.config.adaptive_hold_command_mode == "torque":
            return CtrlMode.TORQUE
        return CtrlMode.POSITION

    def _execute_hold_command(
        self,
        command: _HoldCommand,
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

    def _build_hold_payload(self, command: _HoldCommand) -> tuple[list[Joint], CtrlMode, int]:
        if command.mode == CtrlMode.TORQUE:
            return self._build_torque_hold_payload(command)

        angles = self._clamp_to_contact_window(command.angles)
        joints = self._joint_builder.hold_position_command(
            command.torque,
            angles,
            speed=command.speed,
        )
        return joints, command.mode, command.torque

    def _build_torque_hold_payload(self, command: _HoldCommand) -> tuple[list[Joint], CtrlMode, int]:
        if command.finger_torques is None:
            torque = command.torque
            return self._joint_builder.hold_torque_command(torque), command.mode, torque

        next_torque = self._max_rounded_torque(command.finger_torques, command.torque)
        return (
            self._joint_builder.hold_per_finger_torque_command(command.finger_torques),
            command.mode,
            next_torque,
        )

    def _max_rounded_torque(
        self,
        finger_torques: dict[TactileSensorId, float],
        default_torque: int,
    ) -> int:
        return round(
            clip(
                max(finger_torques.values(), default=float(default_torque)),
                -100.0,
                self.config.max_torque,
            )
        )

    def _clamp_to_contact_window(self, angles: JointAngles) -> JointAngles:
        if not self._contact_joint_angles:
            return angles

        clamped_angles = dict(angles)
        for joint_id, base_angle in self._contact_joint_angles.items():
            if joint_id not in clamped_angles:
                continue
            lower = base_angle - self.config.contact_snapshot_angle_limit
            upper = base_angle + self.config.contact_snapshot_angle_limit
            clamped_angles[joint_id] = max(lower, min(clamped_angles[joint_id], upper))
        return clamped_angles

    def _get_current_angles(self, joint_feedback: Optional[list[Joint]]) -> JointAngles:
        if joint_feedback:
            return {j.id: j.angle for j in joint_feedback}
        if self._contact_joint_angles:
            return dict(self._contact_joint_angles)
        return self._joint_builder.init_hold_angles()
