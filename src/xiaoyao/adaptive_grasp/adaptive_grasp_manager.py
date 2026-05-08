import logging
import threading
import time
from typing import Optional

from xiaoyao.dexhand import CtrlMode, DexHand, JointId, TactileSensorId
from .sensor import SensorClient

from .config import AdaptiveGraspConfig
from .states import GraspState
from .tactility import TactileAnalyzer, TactileAnalysis
from .object_profile import ObjectProfile, ObjectProfileRegistry
from .force_planner import ForcePlanner, ForceDecision
from .safety import SafetyMonitor, SafetyReport
from .visualization import TactileVisualizer
from .utils import clip, JOINT_TO_FINGER
from .joint_builder import JointCommandBuilder
from .grasp_sequence import PhaseController
from .adaptive_hold_loop import HoldController, HoldResult

_logger = logging.getLogger("xiaoyao.adaptive_grasp.adaptive_grasp_manager")


class AdaptiveGrasper:
    _TORQUE_JOINTS = (
        JointId.THUMB_PIP, JointId.THUMB_MCP,
        JointId.FF_PIP, JointId.FF_MCP,
        JointId.MF_PIP, JointId.MF_MCP,
        JointId.RF_PIP, JointId.RF_MCP,
        JointId.LF_PIP, JointId.LF_MCP,
    )

    def __init__(self, hand: DexHand, config: Optional[AdaptiveGraspConfig] = None):
        self.hand = hand
        self.config = config or AdaptiveGraspConfig()
        self.state = GraspState.IDLE
        self.current_torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque))
        self._running = False
        self._control_thread: Optional[threading.Thread] = None
        self._adaptive_hold_started_at: Optional[float] = None
        self._get_monotonic_time = time.monotonic

        self._torque_joints = tuple(
            j for j in AdaptiveGrasper._TORQUE_JOINTS
            if JOINT_TO_FINGER.get(j) in self.config.active_fingers
        )

        self._sensor = SensorClient(
            hand,
            active_fingers=set(self.config.active_fingers),
            get_monotonic_time=self._get_monotonic_time,
        )

        self._tactile = TactileAnalyzer(self.config)
        self._safety = SafetyMonitor(self.config)
        self._force_planner: Optional[ForcePlanner] = None
        self._object_profile: Optional[ObjectProfile] = None
        self._visualizer: Optional[TactileVisualizer] = None
        if self.config.enable_visualization:
            self._visualizer = TactileVisualizer(
                active_fingers=set(self.config.active_fingers),
                backend=self.config.visualization_backend,
            )

        self._joint_builder = JointCommandBuilder(self.config, self._torque_joints)
        self._grasp_sequence: Optional[PhaseController] = None
        self._adaptive_hold_loop: Optional[HoldController] = None

        self._last_tactile_analysis: Optional[TactileAnalysis] = None
        self._last_safety_report: Optional[SafetyReport] = None
        self._last_force_decisions: Optional[dict[TactileSensorId, ForceDecision]] = None
        self._last_tactile_data_age_s: Optional[float] = None
        self._last_control_step_start_s: Optional[float] = None
        self._last_control_cycle_s: Optional[float] = None
        self._last_control_cycle_jitter_s: Optional[float] = None

    def grasp_core(self, object_profile: Optional[ObjectProfile] = None) -> bool:
        try:
            self._running = True
            self._reset_runtime_state()
            self._object_profile = object_profile or ObjectProfileRegistry.get(self.config.default_object)
            self._force_planner = ForcePlanner(self.config, self._object_profile)
            self._tactile.set_friction_coeff(
                self._object_profile.friction_coeff if self._object_profile else self.config.default_friction_coeff,
            )
            self._start_sensor_subscription()

            self._grasp_sequence = PhaseController(
                self.hand, self._sensor, self._safety, self._joint_builder,
                self.config, self._get_monotonic_time, on_state_change=self._set_state,
            )
            result = self._grasp_sequence.run(self._force_planner, lambda: self._running)
            if not result.success:
                if result.should_release:
                    self._perform_release(wait_control_thread=False)
                    return False
                self._cleanup_grasp(state=GraspState.ERROR)
                return False
            self.current_torque = result.final_torque

            self._start_adaptive_control()
            return True
        except KeyboardInterrupt:
            self._cleanup_grasp(state=GraspState.STOPPED)
            raise
        except Exception:
            _logger.exception("grasp_core exception")
            self._cleanup_grasp(state=GraspState.ERROR)
            return False

    def _set_state(self, state: GraspState) -> None:
        self.state = state

    def _cleanup_grasp(self, state: GraspState = GraspState.STOPPED) -> None:
        self._running = False
        self._stop_sensor_subscription()
        if state != GraspState.STOPPED:
            self.state = state

    def release(self) -> bool:
        return self._perform_release(wait_control_thread=True)

    def stop(self) -> None:
        self._running = False
        self._stop_sensor_subscription()
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)
        self._finalize_visualizer(detach_window=True)
        self.hand.stop()
        self.state = GraspState.STOPPED

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
        return self.state

    @property
    def last_tactile_analysis(self) -> Optional[TactileAnalysis]:
        return self._last_tactile_analysis

    @property
    def last_safety_report(self) -> Optional[SafetyReport]:
        return self._last_safety_report

    @property
    def last_force_decisions(self) -> Optional[dict[TactileSensorId, ForceDecision]]:
        return self._last_force_decisions

    @property
    def last_tactile_data_age_s(self) -> Optional[float]:
        return self._last_tactile_data_age_s

    @property
    def last_control_cycle_s(self) -> Optional[float]:
        return self._last_control_cycle_s

    @property
    def last_control_cycle_jitter_s(self) -> Optional[float]:
        return self._last_control_cycle_jitter_s

    def _start_adaptive_control(self) -> None:
        self.state = GraspState.ADAPTIVE_HOLD
        self._adaptive_hold_started_at = self._get_monotonic_time()
        self._adaptive_hold_loop = HoldController(
            self.hand, self._sensor, self._safety, self._tactile,
            self._force_planner, self._visualizer, self._joint_builder,
            self.config, self.current_torque, self._get_monotonic_time,
        )
        self._control_thread = threading.Thread(target=self._adaptive_control_loop, daemon=True)
        self._control_thread.start()
        if self._visualizer is not None:
            self._visualizer.start()

    def _adaptive_control_loop(self) -> None:
        while self._running:
            step_start = self._get_monotonic_time()
            if self._last_control_step_start_s is not None:
                control_cycle_s = step_start - self._last_control_step_start_s
                self._last_control_cycle_s = control_cycle_s
                self._last_control_cycle_jitter_s = control_cycle_s - self.config.control_period_s
            self._last_control_step_start_s = step_start

            if self._should_auto_release():
                self._perform_release(wait_control_thread=False)
                break

            step = self._adaptive_hold_loop.run_step(step_start)
            self._last_tactile_analysis = step.tactile_analysis
            self._last_safety_report = step.safety_report
            self._last_force_decisions = step.force_decisions
            if step.current_torque is not None:
                self.current_torque = step.current_torque

            tactile_data = self._sensor.tactile_data
            self._last_tactile_data_age_s = self._sensor.data_age_s(step_start) if tactile_data is not None else None

            if step.result == HoldResult.AUTO_RELEASE:
                self._perform_release(wait_control_thread=False)
                break
            if step.result == HoldResult.FAULT_RELEASE:
                self._perform_release(wait_control_thread=False)
                break
            if step.result == HoldResult.ERROR:
                self.state = GraspState.ERROR
                self._running = False
                break

            time.sleep(self.config.control_period_s)

    def _should_auto_release(self) -> bool:
        if self._adaptive_hold_started_at is None:
            return False
        elapsed = self._get_monotonic_time() - self._adaptive_hold_started_at
        return elapsed >= self.config.release_hold_time_s

    def _perform_release(self, wait_control_thread: bool) -> bool:
        self.state = GraspState.RELEASE
        self._running = False
        self._adaptive_hold_started_at = None
        self._stop_sensor_subscription()

        control_thread = self._control_thread
        if (
            wait_control_thread
            and control_thread
            and control_thread.is_alive()
            and control_thread is not threading.current_thread()
        ):
            control_thread.join(timeout=2.0)

        joints = self._joint_builder.position_command(
            self._joint_builder.open_pose(),
            speed=self.config.release_open_speed,
            torque=self.config.release_open_torque,
        )
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        time.sleep(self.config.release_timeout_s)
        if not ok:
            _logger.error("RELEASE phase: move_joints failed")
            self.state = GraspState.ERROR
            return False

        self.state = GraspState.COMPLETED
        return True

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
        self._tactile.reset()
        self._safety.reset()
        if self._force_planner is not None:
            self._force_planner.reset()
        self.current_torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque))
        self._adaptive_hold_started_at = None
        self._last_tactile_analysis = None
        self._last_safety_report = None
        self._last_force_decisions = None
        self._last_tactile_data_age_s = None
        self._last_control_step_start_s = None
        self._last_control_cycle_s = None
        self._last_control_cycle_jitter_s = None
        self._object_profile = None
        self._force_planner = None
        self._grasp_sequence = None
        self._adaptive_hold_loop = None
        self._sensor.reset()
