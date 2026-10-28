# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..types import HandControlMode

from .config import AdaptiveGraspConfig
from .joint_builder import JointCommandBuilder
from .ports import HandCommandPort, SensorFrameSource
from .runtime import AdaptiveGraspRuntime
from .runtime import GraspState
from .utils import join_thread_if_alive

_logger = logging.getLogger("adaptive_grasp.release_controller")


@dataclass
class _ReleaseOperation:
    owner_thread: threading.Thread
    done: threading.Event = field(default_factory=threading.Event)
    result: bool = False


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
        self._release_lock = threading.Lock()
        self._release_operation: Optional[_ReleaseOperation] = None
        self._command_lock = threading.Lock()

    def move_hold_joints(self, joints, mode: HandControlMode) -> bool:
        with self._command_lock:
            if not self.runtime.running:
                return True
            return self.hand.move_joints(joints, mode=mode)

    def release(
        self,
        *,
        wait_control_thread: bool,
        release_wait_s: Optional[float] = None,
        control_thread: Optional[threading.Thread] = None,
    ) -> bool:
        current_thread = threading.current_thread()
        with self._release_lock:
            operation = self._release_operation
            if operation is None:
                operation = _ReleaseOperation(owner_thread=current_thread)
                self._release_operation = operation
                owns_operation = True
            else:
                owns_operation = False

        if not owns_operation:
            if operation.owner_thread is current_thread or control_thread is current_thread:
                return False
            operation.done.wait()
            return operation.result

        result = False
        try:
            with self._command_lock:
                self.runtime.state = GraspState.RELEASE
                self.runtime.running = False
            self.runtime.adaptive_hold_started_at = None
            self.sensor.stop(clear_joint_feedback=False)

            if wait_control_thread:
                join_thread_if_alive(control_thread, timeout=2.0)

            joints = self.joint_builder.position_command(
                self.joint_builder.open_pose(),
                velocity=self.config.release_open_velocity,
                current=self.config.release_open_current,
            )
            with self._command_lock:
                ok = self.hand.move_joints(joints, mode=HandControlMode.POSITION)
            self.sleep(self.config.release_timeout_s if release_wait_s is None else release_wait_s)
            if not ok:
                _logger.error("RELEASE phase: move_joints failed")
                self.runtime.state = GraspState.ERROR
                return False

            self.runtime.state = GraspState.COMPLETED
            result = True
            return True
        finally:
            operation.result = result
            operation.done.set()
            with self._release_lock:
                if self._release_operation is operation:
                    self._release_operation = None
