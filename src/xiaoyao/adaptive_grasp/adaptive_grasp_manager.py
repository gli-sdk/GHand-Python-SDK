import logging
import threading
import time
from typing import Optional

from xiaoyao.dexhand import DexHand, JointId, TactileSensorId

from .adaptive_hold_loop import HoldController, HoldResult
from .adaptive_hold_runner import AdaptiveHoldRunner
from .components import build_adaptive_grasp_components
from .config import AdaptiveGraspConfig
from .grasp_sequence import ContactSnapshot, PhaseController
from .hand_adapter import ensure_hand_command_port
from .object_profile import ObjectProfile, ObjectProfileRegistry
from .position_hold_planner import ForceDecision
from .release_controller import ReleaseController
from .runtime import AdaptiveGraspRuntime
from .safety import SafetyReport
from .states import GraspState
from .tactility import TactileAnalysis
from .torque_hold_planner import TorqueHoldDecision

_logger = logging.getLogger("xiaoyao.adaptive_grasp.adaptive_grasp_manager")


_NO_CONTROL_THREAD_OVERRIDE = object()


class AdaptiveGrasper:
    def __init__(self, hand: DexHand, config: Optional[AdaptiveGraspConfig] = None):
        self.hand = hand
        self._hand_port = ensure_hand_command_port(hand)
        self.config = config or AdaptiveGraspConfig()
        self._runtime = AdaptiveGraspRuntime()
        self._get_monotonic_time = time.monotonic
        self._control_thread_override = _NO_CONTROL_THREAD_OVERRIDE

        self._configure_subscription_periods()

        self._components = build_adaptive_grasp_components(
            hand=hand,
            config=self.config,
            get_monotonic_time=self._get_monotonic_time,
        )
        self._sensor = self._components.sensor
        self._tactile = self._components.tactile
        self._safety = self._components.safety
        self._joint_builder = self._components.joint_builder
        self._hold_planner_factory = self._components.hold_planner_factory
        self._visualizer = self._components.visualizer
        self._torque_joints = self._joint_builder.torque_joints

        self._release_controller = ReleaseController(
            hand=self._hand_port,
            sensor=self._sensor,
            joint_builder=self._joint_builder,
            runtime=self._runtime,
            config=self.config,
            sleep=lambda duration: time.sleep(duration),
        )
        self._hold_runner = AdaptiveHoldRunner(
            runtime=self._runtime,
            sensor=self._sensor,
            release_controller=self._release_controller,
            config=self.config,
            hold_controller_factory=self._build_hold_controller,
            get_monotonic_time=self._get_monotonic_time,
            sleep=lambda duration: time.sleep(duration),
        )

        self._grasp_sequence: Optional[PhaseController] = None
        self._adaptive_hold_loop: Optional[HoldController] = None

    def grasp_core(self, object_profile: Optional[ObjectProfile] = None) -> bool:
        try:
            self._prepare_grasp_runtime(object_profile)
            result = self._run_grasp_sequence()
            if not result.success:
                if result.should_release:
                    self._perform_release(wait_control_thread=False)
                    return False
                self._cleanup_grasp(state=GraspState.ERROR)
                return False

            self.current_torque = result.final_torque
            self._runtime.last_contact_snapshot = result.contact_snapshot

            self._start_adaptive_control()
            return True
        except KeyboardInterrupt:
            self._cleanup_grasp(state=GraspState.STOPPED)
            raise
        except Exception:
            _logger.exception("grasp_core exception")
            self._cleanup_grasp(state=GraspState.ERROR)
            return False

    @property
    def state(self) -> GraspState:
        return self._runtime.state

    @state.setter
    def state(self, value: GraspState) -> None:
        self._runtime.state = value

    @property
    def _running(self) -> bool:
        return self._runtime.running

    @_running.setter
    def _running(self, value: bool) -> None:
        self._runtime.running = value

    @property
    def current_torque(self) -> int:
        return self._runtime.current_torque

    @current_torque.setter
    def current_torque(self, value: int) -> None:
        self._runtime.current_torque = value

    @property
    def _control_thread(self):
        if self._control_thread_override is not _NO_CONTROL_THREAD_OVERRIDE:
            return self._control_thread_override
        return self._hold_runner.thread

    @_control_thread.setter
    def _control_thread(self, value) -> None:
        self._control_thread_override = value

    @property
    def _object_profile(self) -> Optional[ObjectProfile]:
        return self._runtime.object_profile

    @_object_profile.setter
    def _object_profile(self, value: Optional[ObjectProfile]) -> None:
        self._runtime.object_profile = value

    @property
    def _adaptive_hold_started_at(self) -> Optional[float]:
        return self._runtime.adaptive_hold_started_at

    @_adaptive_hold_started_at.setter
    def _adaptive_hold_started_at(self, value: Optional[float]) -> None:
        self._runtime.adaptive_hold_started_at = value

    @property
    def _last_tactile_analysis(self) -> Optional[TactileAnalysis]:
        return self._runtime.last_tactile_analysis

    @_last_tactile_analysis.setter
    def _last_tactile_analysis(self, value: Optional[TactileAnalysis]) -> None:
        self._runtime.last_tactile_analysis = value

    @property
    def _last_safety_report(self) -> Optional[SafetyReport]:
        return self._runtime.last_safety_report

    @_last_safety_report.setter
    def _last_safety_report(self, value: Optional[SafetyReport]) -> None:
        self._runtime.last_safety_report = value

    @property
    def _last_force_decisions(self) -> Optional[dict[TactileSensorId, ForceDecision]]:
        return self._runtime.last_force_decisions

    @_last_force_decisions.setter
    def _last_force_decisions(self, value: Optional[dict[TactileSensorId, ForceDecision]]) -> None:
        self._runtime.last_force_decisions = value

    @property
    def _last_torque_hold_decision(self) -> Optional[TorqueHoldDecision]:
        return self._runtime.last_torque_hold_decision

    @_last_torque_hold_decision.setter
    def _last_torque_hold_decision(self, value: Optional[TorqueHoldDecision]) -> None:
        self._runtime.last_torque_hold_decision = value

    @property
    def _last_tactile_data_age_s(self) -> Optional[float]:
        return self._runtime.last_tactile_data_age_s

    @_last_tactile_data_age_s.setter
    def _last_tactile_data_age_s(self, value: Optional[float]) -> None:
        self._runtime.last_tactile_data_age_s = value

    @property
    def _last_control_step_start_s(self) -> Optional[float]:
        return self._runtime.last_control_step_start_s

    @_last_control_step_start_s.setter
    def _last_control_step_start_s(self, value: Optional[float]) -> None:
        self._runtime.last_control_step_start_s = value

    @property
    def _last_control_cycle_s(self) -> Optional[float]:
        return self._runtime.last_control_cycle_s

    @_last_control_cycle_s.setter
    def _last_control_cycle_s(self, value: Optional[float]) -> None:
        self._runtime.last_control_cycle_s = value

    @property
    def _last_control_cycle_jitter_s(self) -> Optional[float]:
        return self._runtime.last_control_cycle_jitter_s

    @_last_control_cycle_jitter_s.setter
    def _last_control_cycle_jitter_s(self, value: Optional[float]) -> None:
        self._runtime.last_control_cycle_jitter_s = value

    @property
    def _last_contact_snapshot(self) -> Optional[ContactSnapshot]:
        return self._runtime.last_contact_snapshot

    @_last_contact_snapshot.setter
    def _last_contact_snapshot(self, value: Optional[ContactSnapshot]) -> None:
        self._runtime.last_contact_snapshot = value

    def _set_state(self, state: GraspState) -> None:
        self._runtime.state = state

    def _cleanup_grasp(self, state: GraspState = GraspState.STOPPED) -> None:
        self._runtime.running = False
        self._stop_sensor_subscription()
        self._runtime.state = state

    def release(self) -> bool:
        return self._perform_release(wait_control_thread=True)

    def release_fast(self, wait_s: float = 2.0) -> bool:
        return self._perform_release(wait_control_thread=False, release_wait_s=wait_s)

    def stop(self) -> None:
        self._runtime.running = False
        self._stop_sensor_subscription()
        self._hold_runner.stop()
        self._join_control_thread_override(timeout=1.0)
        self._finalize_visualizer(detach_window=True)
        self._hand_port.stop()
        self._runtime.state = GraspState.STOPPED

    def stop_visualizer(self) -> None:
        if self._visualizer is not None:
            self._visualizer.stop()

    def wait_for_visualizer_close(self) -> None:
        if self._visualizer is not None:
            self._visualizer.wait_until_closed()

    def poll_visualizer(self) -> None:
        if self._visualizer is not None:
            self._visualizer.poll()

    def get_state(self) -> GraspState:
        return self._runtime.state

    @property
    def last_tactile_analysis(self) -> Optional[TactileAnalysis]:
        return self._runtime.last_tactile_analysis

    @property
    def last_safety_report(self) -> Optional[SafetyReport]:
        return self._runtime.last_safety_report

    @property
    def last_force_decisions(self) -> Optional[dict[TactileSensorId, ForceDecision]]:
        return self._runtime.last_force_decisions

    @property
    def last_torque_hold_decision(self) -> Optional[TorqueHoldDecision]:
        return self._runtime.last_torque_hold_decision

    @property
    def last_tactile_data_age_s(self) -> Optional[float]:
        return self._runtime.last_tactile_data_age_s

    @property
    def last_control_cycle_s(self) -> Optional[float]:
        return self._runtime.last_control_cycle_s

    @property
    def last_control_cycle_jitter_s(self) -> Optional[float]:
        return self._runtime.last_control_cycle_jitter_s

    @property
    def last_contact_snapshot(self) -> Optional[ContactSnapshot]:
        return self._runtime.last_contact_snapshot

    def _build_hold_controller(self, contact_snapshot: Optional[ContactSnapshot]) -> HoldController:
        planners = self._hold_planner_factory.create(
            self._runtime.object_profile,
            contact_snapshot,
        )
        return HoldController(
            self._hand_port,
            self._sensor,
            self._safety,
            self._tactile,
            self._visualizer,
            self._joint_builder,
            self.config,
            self.current_torque,
            contact_joint_angles=(
                contact_snapshot.joint_angles
                if contact_snapshot is not None
                else None
            ),
            torque_hold_planner=planners.torque_hold_planner,
            force_reference_planner=planners.force_reference_planner,
            position_hold_planner=planners.position_hold_planner,
        )

    def _start_adaptive_control(self) -> None:
        self._control_thread_override = _NO_CONTROL_THREAD_OVERRIDE
        self._hold_runner.get_monotonic_time = self._get_monotonic_time
        self._hold_runner.start(self._runtime.last_contact_snapshot)
        self._adaptive_hold_loop = self._hold_runner.hold_controller
        if self._visualizer is not None:
            self._visualizer.start()

    def _prepare_grasp_runtime(self, object_profile: Optional[ObjectProfile]) -> None:
        self._runtime.reset_for_grasp()
        self._reset_runtime_components()
        self._control_thread_override = _NO_CONTROL_THREAD_OVERRIDE
        self._runtime.object_profile = (
            object_profile
            or ObjectProfileRegistry.get(self.config.default_object)
        )
        self._tactile.set_friction_coeff(self._runtime_friction_coeff())
        self._start_sensor_subscription()

    def _runtime_friction_coeff(self) -> float:
        if self._runtime.object_profile is not None:
            return self._runtime.object_profile.friction_coeff
        return self.config.default_friction_coeff

    def _run_grasp_sequence(self):
        self._grasp_sequence = PhaseController(
            self._hand_port,
            self._sensor,
            self._safety,
            self._joint_builder,
            self.config,
            self._get_monotonic_time,
            on_state_change=self._set_state,
            object_profile=self._runtime.object_profile,
        )
        return self._grasp_sequence.run(lambda: self._runtime.running)

    def _contact_joint_angles(self) -> Optional[dict[JointId, float]]:
        if self._runtime.last_contact_snapshot is None:
            return None
        return self._runtime.last_contact_snapshot.joint_angles

    def _adaptive_control_loop(self) -> None:
        self._hold_runner.get_monotonic_time = self._get_monotonic_time
        if self._adaptive_hold_loop is not None:
            self._hold_runner.hold_controller = self._adaptive_hold_loop
        self._hold_runner._run_loop()
        self._adaptive_hold_loop = self._hold_runner.hold_controller

    def _update_control_cycle_timing(self, step_start: float) -> None:
        self._runtime.update_control_cycle_timing(
            step_start,
            control_period_s=self.config.control_period_s,
        )

    def _record_hold_step(self, step, step_start: float) -> None:
        self._runtime.record_hold_step(step, self._sensor, step_start)

    def _handle_hold_result(self, result: HoldResult) -> bool:
        if result in (HoldResult.AUTO_RELEASE, HoldResult.FAULT_RELEASE):
            self._perform_release(wait_control_thread=False)
            return True
        if result == HoldResult.ERROR:
            self._cleanup_grasp(state=GraspState.ERROR)
            return True
        return False

    def _should_auto_release(self, current_time: Optional[float] = None) -> bool:
        if self._runtime.adaptive_hold_started_at is None:
            return False
        now = self._get_monotonic_time() if current_time is None else current_time
        elapsed = now - self._runtime.adaptive_hold_started_at
        return elapsed >= self.config.release_hold_time_s

    def _perform_release(
        self,
        wait_control_thread: bool,
        release_wait_s: Optional[float] = None,
    ) -> bool:
        return self._release_controller.release(
            wait_control_thread=wait_control_thread,
            release_wait_s=release_wait_s,
            control_thread=self._control_thread,
        )

    def _finalize_visualizer(self, detach_window: bool) -> None:
        if self._visualizer is None:
            return
        self._visualizer.stop()
        if detach_window:
            self._visualizer.detach_window()

    def _start_sensor_subscription(self) -> None:
        self._sensor.start()

    def _stop_sensor_subscription(self) -> None:
        self._sensor.stop(clear_joint_feedback=False)

    def _reset_runtime_state(self) -> None:
        state = self._runtime.state
        running = self._runtime.running
        self._runtime.reset_for_grasp()
        self._runtime.state = state
        self._runtime.running = running
        self._reset_runtime_components()

    def _reset_runtime_components(self) -> None:
        self._tactile.reset()
        self._safety.reset()
        self._sensor.reset()
        self._grasp_sequence = None
        self._adaptive_hold_loop = None
        self._hold_runner.hold_controller = None

    def _configure_subscription_periods(self) -> None:
        configure_periods = getattr(self._hand_port, "configure_subscription_periods", None)
        if configure_periods is None:
            return
        configure_periods(
            recv_period_s=self.config.tactile_sensor_update_period_s,
            dispatch_period_s=self.config.tactile_dispatch_period_s,
        )

    def _join_control_thread_override(self, *, timeout: float) -> None:
        thread = self._control_thread_override
        if (
            thread is _NO_CONTROL_THREAD_OVERRIDE
            or thread is None
            or thread is threading.current_thread()
        ):
            return
        is_alive = getattr(thread, "is_alive", None)
        join = getattr(thread, "join", None)
        if is_alive is None or join is None or not is_alive():
            return
        join(timeout=timeout)
