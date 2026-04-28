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
            (self._phase_closing, "CLOSING"),
        ):
            if not is_running():
                return PhaseResult(success=False, final_torque=self.current_torque)
            if not phase_method(force_planner, is_running):
                _logger.error("%s phase failed", name)
                return PhaseResult(success=False, final_torque=self.current_torque)
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

    def _phase_open(self, force_planner: Optional[ForcePlanner] = None, is_running: Callable[[], bool] = lambda: True) -> bool:
        return self._execute_position_phase(
            GraspState.OPEN, self._joint_builder.open_pose(), sleep_s=3,
        )

    def _phase_pre_grasp(self, force_planner: Optional[ForcePlanner] = None, is_running: Callable[[], bool] = lambda: True) -> bool:
        return self._execute_position_phase(
            GraspState.PRE_GRASP, self.config.pre_grasp_pose, sleep_s=5,
        )

    def _phase_closing(self, force_planner: Optional[ForcePlanner], is_running: Callable[[], bool]) -> bool:
        self._set_state(GraspState.CLOSING_TO_CONTACT)
        start = self._get_monotonic_time()
        self.current_torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque))

        if joints_feedback := self._sensor.joint_feedback:
            self._safety.set_closing_baseline(joints_feedback)

        stall_counter = 0
        prev_angles: dict[JointId, float] = {}

        while is_running():
            if (self._get_monotonic_time() - start) > self.config.phase_timeout:
                _logger.error("CLOSING phase timeout")
                return False

            self.hand.move_joints(self._joint_builder.torque_command(self.current_torque), mode=CtrlMode.TORQUE)
            time.sleep(self.config.closing_period_s)

            tactile_data = self._sensor.tactile_data
            joint_feedback = self._sensor.joint_feedback
            if tactile_data is None or joint_feedback is None:
                _logger.error("CLOSING phase: failed to get %s", "tactile data" if tactile_data is None else "joint feedback")
                return False

            from .safety import SafetyStatus
            if self._safety.is_grasp_empty(joint_feedback, GraspState.CLOSING_TO_CONTACT).status != SafetyStatus.OK:
                _logger.error("CLOSING phase: Grasp Empty")
                self._set_state(GraspState.ERROR)
                return False

            if self._sensor.sum_active_finger_normal_force() >= self.config.contact_threshold_z:
                self._calibrate_force(force_planner)
                time.sleep(self.config.control_period_s)
                return True

            current_angles = {j.id: j.angle for j in joint_feedback}
            if self._is_joints_stalled(prev_angles, current_angles):
                stall_counter += 1
                _logger.debug("CLOSING: joint stall detected (%d/%d)", stall_counter, self.config.closing_stall_cycles)
                if stall_counter >= self.config.closing_stall_cycles:
                    _logger.info("CLOSING: torque-stall contact confirmed")
                    self._calibrate_force(force_planner)
                    time.sleep(self.config.control_period_s)
                    return True
            else:
                stall_counter = 0
            prev_angles = current_angles

        return False

    def _is_joints_stalled(self, prev: dict[JointId, float], current: dict[JointId, float]) -> bool:
        if not prev or not current:
            return False
        for joint_id in self._joint_builder._torque_joints:
            delta = abs(current.get(joint_id, 0.0) - prev.get(joint_id, 0.0))
            if delta > self.config.closing_stall_angle_threshold:
                return False
        return True

    def _calibrate_force(self, force_planner: Optional[Any]) -> None:
        pass  # Will be implemented in Task 4
