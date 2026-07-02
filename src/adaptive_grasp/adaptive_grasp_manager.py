import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from ghand import GHand, TactileSensorId

from .adaptive_hold_loop import HoldController
from .adaptive_hold_runner import AdaptiveHoldRunner
from .config import AdaptiveGraspConfig
from .grasp_sequence import ContactSnapshot, PhaseController
from .hand_adapter import ensure_hand_command_port
from .hold_planner_factory import HoldPlannerFactory
from .joint_builder import JointCommandBuilder, TORQUE_CONTROL_JOINTS
from .object_profile import ObjectProfile, ObjectProfileRegistry
from .ports import SensorFrameSource
from .position_hold_planner import ForceDecision
from .release_controller import ReleaseController
from .runtime import AdaptiveGraspRuntime, GraspState
from .safety import SafetyMonitor, SafetyReport
from .sensor import SensorClient
from .tactility import TactileAnalysis, TactileAnalyzer
from .torque_hold_planner import TorqueHoldDecision
from .utils import JOINT_TO_FINGER, join_thread_if_alive
from .visualization import TactileVisualizer

_logger = logging.getLogger("adaptive_grasp.adaptive_grasp_manager")


_NO_CONTROL_THREAD_OVERRIDE = object()


@dataclass
class AdaptiveGraspComponents:
    sensor: Any
    tactile: TactileAnalyzer
    safety: SafetyMonitor
    joint_builder: JointCommandBuilder
    hold_planner_factory: HoldPlannerFactory
    visualizer: Optional[TactileVisualizer]


def build_adaptive_grasp_components(
    *,
    hand: Any,
    config: AdaptiveGraspConfig,
    get_monotonic_time: Any,
    sensor: Optional[Any] = None,
) -> AdaptiveGraspComponents:
    active_fingers = set(config.active_fingers)
    sensor_client = (
        sensor
        if sensor is not None
        else SensorClient(
            hand,
            active_fingers=active_fingers,
            finger_touch_threshold_n=config.finger_touch_threshold_n,
            get_monotonic_time=get_monotonic_time,
        )
    )
    torque_joints = tuple(
        joint_id
        for joint_id in TORQUE_CONTROL_JOINTS
        if JOINT_TO_FINGER[joint_id] in active_fingers
    )
    visualizer = (
        TactileVisualizer(
            active_fingers=active_fingers,
            backend=config.visualization_backend,
        )
        if config.enable_visualization
        else None
    )

    return AdaptiveGraspComponents(
        sensor=sensor_client,
        tactile=TactileAnalyzer(config),
        safety=SafetyMonitor(config),
        joint_builder=JointCommandBuilder(config, torque_joints),
        hold_planner_factory=HoldPlannerFactory(config),
        visualizer=visualizer,
    )


class AdaptiveGrasper:
    def __init__(
        self,
        hand: GHand,
        config: Optional[AdaptiveGraspConfig] = None,
        *,
        sensor: Optional[SensorFrameSource] = None,
    ):
        self.hand = hand
        try:
            self.hand.tactile_zero()
        except Exception:
            _logger.exception("Failed to zero tactile sensors")
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
            sensor=sensor,
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

    def grasp_core(self, object_profile: Optional[ObjectProfile] = None) -> bool:
        try:
            self._prepare_grasp_runtime(object_profile)
            result = self._run_grasp_sequence()
            self._runtime.last_safety_report = result.safety_report
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

    def _set_state(self, state: GraspState) -> None:
        self._runtime.state = state

    def _cleanup_grasp(self, state: GraspState = GraspState.STOPPED) -> None:
        self._runtime.running = False
        self._stop_sensor_subscription()
        self._runtime.state = state

    def release(self) -> bool:
        """Open the hand and complete the normal release phase."""
        return self._perform_release(wait_control_thread=True)

    def release_and_wait_for_visualizer_close(self) -> bool:
        """Release the grasp, then wait for the visualizer window to close."""
        ok = self.release()
        self.wait_for_visualizer_close()
        return ok

    def wait_for_completion(self, poll_period_s: float = 0.1) -> GraspState:
        """Wait for adaptive hold/release to finish without initiating release."""
        if poll_period_s <= 0:
            raise ValueError("poll_period_s must be > 0")

        while self.get_state() in (GraspState.ADAPTIVE_HOLD, GraspState.RELEASE):
            self.poll_visualizer()
            if self.get_state() not in (GraspState.ADAPTIVE_HOLD, GraspState.RELEASE):
                break
            time.sleep(poll_period_s)

        self._join_control_thread_override(timeout=1.0)
        return self.get_state()

    def emergency_release(self, wait_s: float = 2.0) -> bool:
        """Open the hand immediately without waiting for the control thread."""
        return self._perform_release(wait_control_thread=False, release_wait_s=wait_s)

    def shutdown(self) -> None:
        """Stop control, sensors, visualization, and hand transport without opening."""
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

    def _reset_runtime_components(self) -> None:
        self._tactile.reset()
        self._safety.reset()
        self._sensor.reset()
        self._grasp_sequence = None
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
        if thread is _NO_CONTROL_THREAD_OVERRIDE:
            return
        join_thread_if_alive(thread, timeout=timeout)
