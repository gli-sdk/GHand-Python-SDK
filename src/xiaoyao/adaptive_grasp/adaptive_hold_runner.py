import logging
import threading
import time
from typing import Callable, Optional, Protocol

from .adaptive_hold_loop import HoldController, HoldResult, HoldStepResult
from .config import AdaptiveGraspConfig
from .grasp_sequence import ContactSnapshot
from .ports import SensorFrameSource
from .release_controller import ReleaseController
from .runtime import AdaptiveGraspRuntime
from .states import GraspState

_logger = logging.getLogger("xiaoyao.adaptive_grasp.adaptive_hold_runner")


class _HoldControllerLike(Protocol):
    def run_step(self, current_time: float) -> HoldStepResult:
        ...


class _ReleaseControllerLike(Protocol):
    def release(
        self,
        *,
        wait_control_thread: bool,
        release_wait_s: Optional[float] = None,
        control_thread: Optional[threading.Thread] = None,
    ) -> bool:
        ...


class AdaptiveHoldRunner:
    """Runs adaptive-hold control cycles against shared runtime state."""

    def __init__(
        self,
        runtime: AdaptiveGraspRuntime,
        sensor: SensorFrameSource,
        release_controller: ReleaseController | _ReleaseControllerLike,
        config: AdaptiveGraspConfig,
        hold_controller_factory: Callable[[ContactSnapshot], HoldController | _HoldControllerLike],
        get_monotonic_time: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.runtime = runtime
        self.sensor = sensor
        self.release_controller = release_controller
        self.config = config
        self.hold_controller_factory = hold_controller_factory
        self.get_monotonic_time = get_monotonic_time
        self.sleep = sleep
        self._hold_controller: Optional[HoldController | _HoldControllerLike] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def thread(self) -> Optional[threading.Thread]:
        return self._thread

    def start(self, contact_snapshot: ContactSnapshot, *, start_thread: bool = True) -> None:
        self._hold_controller = self.hold_controller_factory(contact_snapshot)
        self.runtime.state = GraspState.ADAPTIVE_HOLD
        self.runtime.adaptive_hold_started_at = self.get_monotonic_time()

        if not start_thread:
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def run_once(self) -> bool:
        step_start = self.get_monotonic_time()
        self.runtime.update_control_cycle_timing(
            step_start,
            control_period_s=self.config.control_period_s,
        )

        if self._should_auto_release(step_start):
            self._release()
            return False

        if self._hold_controller is None:
            raise RuntimeError("adaptive hold runner has not been started")

        step = self._hold_controller.run_step(step_start)
        self.runtime.record_hold_step(step, self.sensor, step_start)

        if step.result == HoldResult.CONTINUE:
            return True
        if step.result in (HoldResult.AUTO_RELEASE, HoldResult.FAULT_RELEASE):
            self._release()
            return False

        self._cleanup_error()
        return False

    def stop(self) -> None:
        self.runtime.running = False
        thread = self._thread
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=1.0)

    def _run_loop(self) -> None:
        try:
            while self.runtime.running:
                if not self.run_once():
                    break
                self.sleep(self.config.control_period_s)
        except Exception:
            _logger.exception("adaptive hold runner loop exception")
            self._cleanup_error()

    def _should_auto_release(self, step_start: float) -> bool:
        started_at = self.runtime.adaptive_hold_started_at
        if started_at is None:
            return False
        return step_start - started_at >= self.config.release_hold_time_s

    def _release(self) -> bool:
        return self.release_controller.release(
            wait_control_thread=False,
            control_thread=self._thread,
        )

    def _cleanup_error(self) -> None:
        self.runtime.state = GraspState.ERROR
        self.runtime.running = False
        self.sensor.stop(clear_joint_feedback=False)
