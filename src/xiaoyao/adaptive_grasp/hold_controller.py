import logging
from enum import auto, Enum
from dataclasses import dataclass
from typing import Any, Callable, Optional

from xiaoyao.dexhand import CtrlMode, DexHand, JointId
from .config import AdaptiveGraspConfig
from .sensor import SensorClient
from .safety import SafetyMonitor, SafetyReport, SafetyStatus
from .states import GraspState
from .tactility import TactileAnalyzer, TactileAnalysis
from .force_planner import ForcePlanner, ForceDecision
from .visualization import TactileVisualizer
from .joint_builder import JointCommandBuilder

_logger = logging.getLogger("xiaoyao.adaptive_grasp.hold_controller")


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
    force_decisions: Optional[dict] = None
    current_torque: Optional[int] = None


class HoldController:
    def __init__(
        self,
        hand: DexHand,
        sensor: SensorClient,
        safety: SafetyMonitor,
        tactile: TactileAnalyzer,
        force_planner: Optional[ForcePlanner],
        visualizer: Optional[TactileVisualizer],
        joint_builder: JointCommandBuilder,
        config: AdaptiveGraspConfig,
        current_torque: int,
        get_time: Callable[[], float],
    ):
        self.hand = hand
        self._sensor = sensor
        self._safety = safety
        self._tactile = tactile
        self._force_planner = force_planner
        self._visualizer = visualizer
        self._joint_builder = joint_builder
        self.config = config
        self._current_torque = current_torque
        self._get_monotonic_time = get_time
        self._consecutive_move_failures = 0
        self._max_consecutive_move_failures = 3

    def run_step(self, current_time: float) -> HoldStepResult:
        tactile_data = self._sensor.tactile_data
        joint_feedback = self._sensor.joint_feedback

        # 1) Safety check
        safety = self._safety.check(tactile_data, joint_feedback, GraspState.ADAPTIVE_HOLD)
        if safety.status == SafetyStatus.FAULT:
            if self.config.enable_fault_release_fallback:
                return HoldStepResult(
                    result=HoldResult.FAULT_RELEASE,
                    safety_report=safety,
                    current_torque=self._current_torque,
                )
            return HoldStepResult(
                result=HoldResult.ERROR,
                safety_report=safety,
                current_torque=self._current_torque,
            )

        if tactile_data is None:
            return HoldStepResult(
                result=HoldResult.CONTINUE,
                safety_report=safety,
                current_torque=self._current_torque,
            )

        # 2) Tactile analysis
        analysis = self._tactile.update(tactile_data)

        # 3) Force planning
        current_angles = self._get_current_angles(joint_feedback)
        if self._visualizer is not None and tactile_data is not None:
            self._visualizer.update(tactile_data, analysis, joint_angles=current_angles, timestamp=current_time)

        if self._force_planner is not None:
            decisions = self._force_planner.compute(analysis, current_angles)
            next_angles = dict(current_angles)
            for decision in decisions.values():
                next_angles.update(decision.target_angles)
            next_torque = next(iter(decisions.values())).next_torque if decisions else self._current_torque
        else:
            next_angles = current_angles
            next_torque = self._current_torque

        # 4) Execute
        joints = self._joint_builder.hold_position_command(next_torque, next_angles)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if not ok:
            self._consecutive_move_failures += 1
            _logger.error(
                "ADAPTIVE_HOLD: move_joints failed (%d/%d)",
                self._consecutive_move_failures,
                self._max_consecutive_move_failures,
            )
            if self._consecutive_move_failures >= self._max_consecutive_move_failures:
                return HoldStepResult(
                    result=HoldResult.ERROR,
                    tactile_analysis=analysis,
                    safety_report=safety,
                    current_torque=self._current_torque,
                )
        else:
            self._consecutive_move_failures = 0
            self._current_torque = next_torque

        return HoldStepResult(
            result=HoldResult.CONTINUE,
            tactile_analysis=analysis,
            safety_report=safety,
            force_decisions=decisions if self._force_planner else None,
            current_torque=self._current_torque,
        )

    def _get_current_angles(self, joint_feedback: Optional[list]) -> dict[JointId, float]:
        if joint_feedback:
            return {j.id: j.angle for j in joint_feedback}
        return self._joint_builder.init_hold_angles()
