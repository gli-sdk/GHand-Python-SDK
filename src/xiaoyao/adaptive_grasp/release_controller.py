import logging
import threading
import time
from typing import Callable, Optional

from xiaoyao.dexhand import CtrlMode

from .config import AdaptiveGraspConfig
from .joint_builder import JointCommandBuilder
from .ports import HandCommandPort, SensorFrameSource
from .runtime import AdaptiveGraspRuntime
from .states import GraspState

_logger = logging.getLogger("xiaoyao.adaptive_grasp.release_controller")


class ReleaseController:
    def __init__(
        self,
        hand: HandCommandPort,
        sensor: SensorFrameSource,
        joint_builder: JointCommandBuilder,
        runtime: AdaptiveGraspRuntime,
        config: AdaptiveGraspConfig,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.hand = hand
        self.sensor = sensor
        self.joint_builder = joint_builder
        self.runtime = runtime
        self.config = config
        self.sleep = sleep

    def release(
        self,
        *,
        wait_control_thread: bool,
        release_wait_s: Optional[float] = None,
        control_thread: Optional[threading.Thread] = None,
    ) -> bool:
        self.runtime.state = GraspState.RELEASE
        self.runtime.running = False
        self.runtime.adaptive_hold_started_at = None
        self.sensor.stop(clear_joint_feedback=False)

        if (
            wait_control_thread
            and control_thread
            and control_thread.is_alive()
            and control_thread is not threading.current_thread()
        ):
            control_thread.join(timeout=2.0)

        joints = self.joint_builder.position_command(
            self.joint_builder.open_pose(),
            speed=self.config.release_open_speed,
            torque=self.config.release_open_torque,
        )
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        self.sleep(self.config.release_timeout_s if release_wait_s is None else release_wait_s)
        if not ok:
            _logger.error("RELEASE phase: move_joints failed")
            self.runtime.state = GraspState.ERROR
            return False

        self.runtime.state = GraspState.COMPLETED
        return True
