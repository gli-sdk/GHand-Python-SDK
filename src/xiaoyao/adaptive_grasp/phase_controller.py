import logging
import time
from typing import Any, Callable, Optional

from xiaoyao.dexhand import CtrlMode, DexHand, Joint, JointId
from .config import AdaptiveGraspConfig
from .states import GraspState
from .sensor import SensorClient
from .safety import SafetyMonitor
from .force_planner import ForcePlanner
from .joint_builder import JointCommandBuilder
from .utils import clip

_logger = logging.getLogger("xiaoyao.adaptive_grasp.phase_controller")


class PhaseResult:
    def __init__(self, success: bool, final_torque: int):
        self.success = success
        self.final_torque = final_torque


class PhaseController:
    def __init__(
        self,
        hand: DexHand,
        sensor: SensorClient,
        safety: SafetyMonitor,
        joint_builder: JointCommandBuilder,
        config: AdaptiveGraspConfig,
        get_time: Callable[[], float],
        on_state_change: Callable[[GraspState], None],
    ):
        self.hand = hand
        self._sensor = sensor
        self._safety = safety
        self._joint_builder = joint_builder
        self.config = config
        self._get_monotonic_time = get_time
        self._on_state_change = on_state_change
        self.current_torque = int(clip(config.base_torque, -100.0, config.max_torque))

    def run(self, force_planner: Optional[ForcePlanner], is_running: Callable[[], bool]) -> PhaseResult:
        for phase_method, name in (
            (self._phase_open, "OPEN"),
            (self._phase_pre_grasp, "PRE_GRASP"),
        ):
            if not is_running():
                return PhaseResult(success=False, final_torque=self.current_torque)
            if not phase_method():
                _logger.error("%s phase failed", name)
                return PhaseResult(success=False, final_torque=self.current_torque)
        # CLOSING will be added in Task 3
        return PhaseResult(success=True, final_torque=self.current_torque)

    def _set_state(self, state: GraspState) -> None:
        self._on_state_change(state)

    def _execute_position_phase(self, state: GraspState, pose: dict[JointId, float], sleep_s: float) -> bool:
        self._set_state(state)
        joints = self._joint_builder.position_command(pose, speed=50, torque=50)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(sleep_s)
        return ok

    def _phase_open(self) -> bool:
        return self._execute_position_phase(
            GraspState.OPEN, self._joint_builder.open_pose(), sleep_s=3,
        )

    def _phase_pre_grasp(self) -> bool:
        return self._execute_position_phase(
            GraspState.PRE_GRASP, self.config.pre_grasp_pose, sleep_s=5,
        )
