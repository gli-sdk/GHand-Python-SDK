import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from xiaoyao.dexhand import CtrlMode, Joint, JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .ports import GraspSequenceHandPort, SensorFrameSource
from .runtime import GraspState
from .safety import SafetyMonitor, SafetyStatus
from .joint_builder import JointCommandBuilder
from .object_profile import ObjectProfile
from .utils import clip

_logger = logging.getLogger("adaptive_grasp.grasp_sequence")


@dataclass(frozen=True)
class ContactSnapshot:
    joint_angles: dict[JointId, float]
    finger_fz: dict[TactileSensorId, float]
    total_fz: float
    torque: int
    reason: str
    timestamp_s: float


@dataclass(frozen=True)
class ClosingSensorFrame:
    tactile_data: dict[TactileSensorId, Any]
    joint_feedback: list[Joint]
    total_fz: float
    touch_flags: dict[TactileSensorId, bool]


class PhaseResult:
    def __init__(
        self,
        success: bool,
        final_torque: int,
        should_release: bool = False,
        contact_snapshot: Optional[ContactSnapshot] = None,
    ):
        self.success = success
        self.final_torque = final_torque
        self.should_release = should_release
        self.contact_snapshot = contact_snapshot


class PhaseController:
    def __init__(
        self,
        hand: GraspSequenceHandPort,
        sensor: SensorFrameSource,
        safety: SafetyMonitor,
        joint_builder: JointCommandBuilder,
        config: AdaptiveGraspConfig,
        get_time: Callable[[], float],
        on_state_change: Callable[[GraspState], None],
        object_profile: Optional[ObjectProfile] = None,
    ):
        self.hand = hand
        self._sensor = sensor
        self._safety = safety
        self._joint_builder = joint_builder
        self.config = config
        self._object_profile = object_profile
        self._get_monotonic_time = get_time
        self._on_state_change = on_state_change
        self.current_torque = self._phase_closing_torque()
        self._phase_should_release = False
        self._contact_snapshot: Optional[ContactSnapshot] = None

    def run(self, is_running: Callable[[], bool]) -> PhaseResult:
        self._phase_should_release = False
        self._contact_snapshot = None
        for phase_method, name in (
            (self._phase_open, "OPEN"),
            (self._phase_pre_grasp, "PRE_GRASP"),
            (self._phase_closing, "CLOSING"),
        ):
            if not is_running():
                return PhaseResult(
                    success=False,
                    final_torque=self.current_torque,
                    should_release=self._phase_should_release,
                    contact_snapshot=self._contact_snapshot,
                )
            if not phase_method(is_running):
                _logger.error("%s phase failed", name)
                self._set_state(GraspState.ERROR)
                return PhaseResult(
                    success=False,
                    final_torque=self.current_torque,
                    should_release=self._phase_should_release,
                    contact_snapshot=self._contact_snapshot,
                )
        return PhaseResult(
            success=True,
            final_torque=self.current_torque,
            contact_snapshot=self._contact_snapshot,
        )

    def _set_state(self, state: GraspState) -> None:
        self._on_state_change(state)

    def _phase_closing_torque(self) -> int:
        torque = (
            self._object_profile.phase_closing_torque
            if self._object_profile is not None
            else 30
        )
        return int(clip(torque, -100.0, self.config.max_torque))

    def _execute_position_phase(
        self,
        state: GraspState,
        pose: dict[JointId, float],
        speed: int,
        torque: int,
    ) -> bool:
        self._set_state(state)
        joints = self._joint_builder.position_command(pose, speed=speed, torque=torque)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        time.sleep(0.02)
        if not self.hand.wait_for_motion_completion():
            return False 
        return ok

    def _phase_open(self, is_running: Callable[[], bool] = lambda: True) -> bool:
        return self._execute_position_phase(
            GraspState.OPEN,
            self._joint_builder.open_pose(),
            speed=self.config.open_speed,
            torque=self.config.open_torque,
        )

    def _phase_pre_grasp(self, is_running: Callable[[], bool] = lambda: True) -> bool:
        return self._execute_position_phase(
            GraspState.PRE_GRASP,
            self.config.pre_grasp_pose,
            speed=self.config.pre_grasp_speed,
            torque=self.config.pre_grasp_torque,
        )

    def _phase_closing(self, is_running: Callable[[], bool]) -> bool:
        self._set_state(GraspState.CLOSING_TO_CONTACT)
        start = self._get_monotonic_time()
        self.current_torque = self._phase_closing_torque()

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

            frame = self._read_closing_sensor_frame()
            if frame is None:
                return False

            if self._is_empty_grasp(frame.joint_feedback):
                return False

            if self._try_confirm_force_contact(frame):
                return True

            current_angles = {j.id: j.angle for j in frame.joint_feedback}
            if self._is_joints_stalled(prev_angles, current_angles):
                stall_counter += 1
                if self._try_confirm_stall_contact(stall_counter, frame):
                    return True
            else:
                stall_counter = 0
            prev_angles = current_angles

        return False

    def _read_closing_sensor_frame(self) -> Optional[ClosingSensorFrame]:
        tactile_data = self._sensor.tactile_data
        joint_feedback = self._sensor.joint_feedback
        if tactile_data is None or joint_feedback is None:
            _logger.error(
                "CLOSING phase: failed to get %s",
                "tactile data" if tactile_data is None else "joint feedback",
            )
            return None
        return ClosingSensorFrame(
            tactile_data=tactile_data,
            joint_feedback=joint_feedback,
            total_fz=self._sensor.sum_active_finger_normal_force(),
            touch_flags=self._sensor.active_finger_touch_flag(),
        )

    def _is_empty_grasp(self, joint_feedback: list[Joint]) -> bool:
        report = self._safety.is_grasp_empty(
            joint_feedback,
            GraspState.CLOSING_TO_CONTACT,
        )
        if report.status == SafetyStatus.OK:
            return False

        _logger.error("CLOSING phase: Grasp Empty")
        self._phase_should_release = True
        self._set_state(GraspState.ERROR)
        return True

    def _try_confirm_force_contact(self, frame: ClosingSensorFrame) -> bool:
        if frame.total_fz < self.config.closing_total_contact_threshold_n:
            return False
        if not all(frame.touch_flags.values()):
            return False

        self._record_contact_snapshot(
            frame.joint_feedback,
            frame.tactile_data,
            frame.total_fz,
            "force_threshold",
        )
        time.sleep(self.config.control_period_s)
        return True

    def _try_confirm_stall_contact(
        self,
        stall_counter: int,
        frame: ClosingSensorFrame,
    ) -> bool:
        _logger.debug(
            "CLOSING: joint stall detected (%d/%d)",
            stall_counter,
            self.config.closing_stall_cycles,
        )
        if stall_counter < self.config.closing_stall_cycles:
            return False

        _logger.info("CLOSING: torque-stall contact confirmed")
        self._record_contact_snapshot(
            frame.joint_feedback,
            frame.tactile_data,
            frame.total_fz,
            "torque_stall",
        )
        time.sleep(self.config.control_period_s)
        return True

    def _record_contact_snapshot(
        self,
        joint_feedback: list[Joint],
        tactile_data: dict[TactileSensorId, Any],
        total_fz: float,
        reason: str,
    ) -> None:
        joint_angles = {
            j.id: j.angle
            for j in joint_feedback
            if j.id in self._joint_builder.torque_joints
        }
        finger_fz = {
            finger: abs(info.get_force_z())
            for finger, info in tactile_data.items()
            if finger in self.config.active_fingers
        }
        self._contact_snapshot = ContactSnapshot(
            joint_angles=joint_angles,
            finger_fz=finger_fz,
            total_fz=total_fz,
            torque=self.current_torque,
            reason=reason,
            timestamp_s=self._get_monotonic_time(),
        )
        _logger.info(
            "CLOSING: contact snapshot recorded reason=%s total_fz=%.2f joints=%d",
            reason,
            total_fz,
            len(joint_angles),
        )

    def _is_joints_stalled(self, prev: dict[JointId, float], current: dict[JointId, float]) -> bool:
        if not prev or not current:
            return False
        for joint_id in self._joint_builder.torque_joints:
            delta = abs(current.get(joint_id, 0.0) - prev.get(joint_id, 0.0))
            if delta > self.config.closing_stall_angle_threshold:
                return False
        return True
