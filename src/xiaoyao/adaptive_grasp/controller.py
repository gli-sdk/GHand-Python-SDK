import logging
import math
import threading
import time
from typing import Any, Mapping, Optional

from xiaoyao.dexhand import CtrlMode, DexHand, Joint, JointId, TactileSensorId
from .sensor import SensorClient

from .config import AdaptiveGraspConfig
from .states import GraspState
from .tactility import TactileAnalyzer
from .object_profile import ObjectProfile
from .force_planner import ForcePlanner
from .safety import SafetyMonitor, SafetyStatus
from .visualization import TactileVisualizer
from .utils import clip

_logger = logging.getLogger("xiaoyao.adaptive_grasp.controller")

# 关节到触觉传感器手指的映射，用于根据活跃手指过滤控制关节
_JOINT_TO_FINGER: dict[JointId, TactileSensorId] = {
    JointId.THUMB_PIP: TactileSensorId.THUMB,
    JointId.THUMB_MCP: TactileSensorId.THUMB,
    JointId.FF_PIP: TactileSensorId.FOREFINGER,
    JointId.FF_MCP: TactileSensorId.FOREFINGER,
    JointId.MF_PIP: TactileSensorId.MIDDLE_FINGER,
    JointId.MF_MCP: TactileSensorId.MIDDLE_FINGER,
    JointId.RF_PIP: TactileSensorId.RING_FINGER,
    JointId.RF_MCP: TactileSensorId.RING_FINGER,
    JointId.LF_PIP: TactileSensorId.LITTLE_FINGER,
    JointId.LF_MCP: TactileSensorId.LITTLE_FINGER,
}


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
        self.current_torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque)) # 初始力矩，限制在硬件范围内
        self._running = False # 控制循环运行标志
        self._control_thread: Optional[threading.Thread] = None # ADAPTIVE_HOLD 后台控制线程
        self._adaptive_hold_started_at: Optional[float] = None # ADAPTIVE_HOLD 阶段开始时间戳
        self._get_monotonic_time = time.monotonic # 单调时钟引用（便于测试 mock）

        # 根据活跃手指过滤参与力控/位控闭环的关节，避免不参与的手指被误驱动
        self._torque_joints = tuple(
            j for j in AdaptiveGrasper._TORQUE_JOINTS
            if _JOINT_TO_FINGER.get(j) in self.config.active_fingers
        )

        # 传感器客户端：统一封装 subscribe / 缓存 / 数据提取
        self._sensor = SensorClient(
            hand,
            active_fingers=set(self.config.active_fingers),
            get_monotonic_time=self._get_monotonic_time,
        )

        # 子模块
        self._tactile = TactileAnalyzer(self.config)
        self._safety = SafetyMonitor(self.config)
        self._force_planner: Optional[ForcePlanner] = None
        self._object_profile: Optional[ObjectProfile] = None
        self._visualizer: Optional[TactileVisualizer] = None
        if self.config.enable_visualization:
            self._visualizer = TactileVisualizer(
                active_fingers=set(self.config.active_fingers),
            )

        # 对外只读：最近一次控制周期的结果快照
        self._last_tactile_analysis: Optional[Any] = None
        self._last_safety_report: Optional[Any] = None
        self._last_force_decisions: Optional[Any] = None
        self._last_tactile_data_age_s: Optional[float] = None
        self._last_control_step_start_s: Optional[float] = None
        self._last_control_cycle_s: Optional[float] = None
        self._last_control_cycle_jitter_s: Optional[float] = None

    def grasp_core(self, object_profile: Optional[ObjectProfile] = None) -> bool:
        try:
            self._running = True
            self._reset_runtime_state()
            self._object_profile = object_profile
            self._force_planner = ForcePlanner(
                self.config, object_profile,
            )
            self._tactile.set_friction_coeff(
                object_profile.friction_coeff if object_profile else self.config.default_friction_coeff,
            )
            self._start_sensor_subscription()
            for phase_method, name in (
                (self._phase_open, "OPEN"),
                (self._phase_pre_grasp, "PRE_GRASP"),
                (self._phase_closing, "CLOSING"),
            ):
                if not phase_method():
                    _logger.error("%s phase failed", name)
                    self._cleanup_grasp()
                    return False
            self._start_adaptive_control()
            return True
        except Exception:
            _logger.exception("grasp_core 异常")
            self._cleanup_grasp(state=GraspState.ERROR)
            return False

    def _cleanup_grasp(self, state: GraspState = GraspState.STOPPED) -> None:
        self._running = False
        self._stop_sensor_subscription()
        if state != GraspState.STOPPED:
            self.state = state

    def release(self) -> bool: #外部主动调用
        return self._perform_release(wait_control_thread=True)

    def stop(self) -> None:
        self._running = False
        self._stop_sensor_subscription()
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)
        if self._visualizer is not None:
            self._visualizer.stop()
        self.hand.stop()
        self.state = GraspState.STOPPED

    def get_state(self) -> GraspState:
        return self.state

    @property
    def last_tactile_analysis(self) -> Optional[Any]:
        return self._last_tactile_analysis

    @property
    def last_safety_report(self) -> Optional[Any]:
        return self._last_safety_report

    @property
    def last_force_decisions(self) -> Optional[Any]:
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

    # ------------------------------------------------------------------
    # 阶段
    # ------------------------------------------------------------------
    def _execute_position_phase(
        self, state: GraspState, pose: dict[JointId, float], sleep_s: float,
    ) -> bool:
        self.state = state
        joints = self._build_position_joints(pose, speed=50, torque=50)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(sleep_s)
        return ok

    def _phase_open(self) -> bool:
        return self._execute_position_phase(
            GraspState.OPEN, self._get_open_pose(), sleep_s=3,
        )

    def _phase_pre_grasp(self) -> bool:
        return self._execute_position_phase(
            GraspState.PRE_GRASP, self.config.pre_grasp_pose, sleep_s=5,
        )

    def _phase_closing(self) -> bool:
        self.state = GraspState.CLOSING_TO_CONTACT
        start = time.time()
        self.current_torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque))

        if joints_feedback := self._safe_get_joints():
            self._safety.set_closing_baseline(joints_feedback)

        while self._running:
            if (time.time() - start) > self.config.phase_timeout:
                _logger.error("CLOSING phase timeout")
                return False

            self.hand.move_joints(self._build_torque_joints(self.current_torque), mode=CtrlMode.TORQUE)
            time.sleep(0.2)

            tactile_data = self._safe_get_tactile_data()
            joint_feedback = self._safe_get_joints()
            if tactile_data is None or joint_feedback is None:
                _logger.error("CLOSING phase: failed to get %s", "tactile data" if tactile_data is None else "joint feedback")
                return False

            if self._safety.is_grasp_empty(joint_feedback, self.state).status != SafetyStatus.OK:
                _logger.error("CLOSING phase: Grasp Empty")
                self.state = GraspState.ERROR
                return False

            if self._sensor.sum_active_finger_normal_force() >= self.config.contact_threshold_z:
                self._calibrate_force()
                time.sleep(self.config.control_period_s)
                return True

        return False

    def _calibrate_force(self) -> None:
        """使用 1-2 步力矩调整，使总法向力匹配 F_init，误差控制在 ±2N 内。"""
        if self._force_planner is None:
            return
        F_init = self._force_planner.F_init
        if F_init <= 0:
            return
        for _ in range(2): # 最多校准 2 步
            total_fz = self._sensor.sum_active_finger_normal_force()
            if abs(total_fz - F_init) <= 2.0:
                break
            step = self.config.torque_adjust_step
            if self._force_planner.is_fragile_mode:
                step = int(step * self.config.fragile_step_reduction)
            if total_fz < F_init:
                self.current_torque = int(clip(self.current_torque + step, -100.0, self.config.max_torque))
            else:
                self.current_torque = int(clip(self.current_torque - step, -100.0, self.config.max_torque))
            joints = self._build_torque_joints(self.current_torque)
            if not self.hand.move_joints(joints, mode=CtrlMode.TORQUE):
                _logger.error("FORCE_CALIBRATION: move_joints failed")
                break
            time.sleep(self.config.control_period_s)

    # ------------------------------------------------------------------
    # 自适应保持
    # ------------------------------------------------------------------
    def _start_adaptive_control(self) -> None:
        self.state = GraspState.ADAPTIVE_HOLD
        self._adaptive_hold_started_at = self._get_monotonic_time()
        self._control_thread = threading.Thread(target=self._adaptive_control_loop, daemon=True) # 后台守护线程
        self._control_thread.start()
        if self._visualizer is not None:
            self._visualizer.start()

    def _adaptive_control_loop(self) -> None:
        while self._running:
            self._run_control_step()
            time.sleep(self.config.control_period_s)

    def _run_control_step(self) -> bool:
        control_step_start_s = self._get_monotonic_time()
        if self._last_control_step_start_s is not None:
            control_cycle_s = control_step_start_s - self._last_control_step_start_s
            self._last_control_cycle_s = control_cycle_s
            self._last_control_cycle_jitter_s = control_cycle_s - self.config.control_period_s
        self._last_control_step_start_s = control_step_start_s

        self._last_tactile_analysis = None
        self._last_safety_report = None
        self._last_force_decisions = None

        if self._should_auto_release():
            return self._perform_release(wait_control_thread=False)

        tactile_data = self._safe_get_tactile_data()
        joint_feedback = self._safe_get_joints()

        # 1) 安全检查
        safety = self._safety.check(tactile_data, joint_feedback, self.state)
        self._last_safety_report = safety
        if safety.status == SafetyStatus.FAULT:
            if self.config.enable_fault_release_fallback:
                return self._perform_release(wait_control_thread=False)
            self.state = GraspState.ERROR
            self._running = False
            return False

        if tactile_data is None:
            return True # 传感器缺失时保持上一周期姿态，不中断循环

        # 2) 触觉分析
        analysis = self._tactile.update(tactile_data)
        self._last_tactile_analysis = analysis
        if self._visualizer is not None and tactile_data is not None:
            self._visualizer.update(tactile_data, analysis, timestamp=control_step_start_s)

        # 3) 力规划
        current_angles = self._get_current_angles(joint_feedback)
        if self._force_planner is not None:
            decisions = self._force_planner.compute(analysis, current_angles)
            self._last_force_decisions = decisions
            next_angles = dict(current_angles)
            for decision in decisions.values():
                next_angles.update(decision.target_angles)
            next_torque = next(iter(decisions.values())).next_torque if decisions else self.current_torque
        else:
            next_angles = current_angles
            next_torque = self.current_torque

        # 4) 执行
        joints = self._build_hold_position_joints(next_torque, next_angles)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if not ok:
            _logger.error("ADAPTIVE_HOLD: move_joints failed")
        return ok

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    def _start_sensor_subscription(self) -> None:
        self._sensor.start()

    def _stop_sensor_subscription(self) -> None:
        self._sensor.stop(clear_joint_feedback=False)

    def _safe_get_tactile_data(self) -> Optional[dict[TactileSensorId, Any]]:
        tactile_data = self._sensor.tactile_data
        if tactile_data is None:
            self._last_tactile_data_age_s = None
            return None
        self._last_tactile_data_age_s = self._sensor.data_age_s(self._get_monotonic_time())
        for finger, info in tactile_data.items():
            if not getattr(info, "state", True):
                _logger.error("TACTILE: active finger %s data invalid (state=False)", finger)
                return None
        return tactile_data

    def _safe_get_joints(self) -> Optional[list]:
        return self._sensor.joint_feedback

    def _get_current_angles(self, joint_feedback: Optional[list]) -> dict[JointId, float]:
        if joint_feedback:
            return {j.id: j.angle for j in joint_feedback}
        return self._init_hold_joint_angles()

    def _sum_active_finger_normal_force(self) -> float:
        return self._sensor.sum_active_finger_normal_force()

    def _build_torque_joints(self, torque: int) -> list[Joint]:
        active = set(self._torque_joints)
        joints = [
            Joint(id=joint_id, torque=torque) if joint_id in active else Joint(id=joint_id, angle=0.0, speed=0, torque=0)
            for joint_id in AdaptiveGrasper._TORQUE_JOINTS
        ]
        joints += [
            Joint(id=JointId.THUMB_ROTATION, angle=0.0, speed=0, torque=5),
            Joint(id=JointId.THUMB_SWING, angle=0.0, speed=0, torque=5),
        ]
        return joints

    def _init_hold_joint_angles(self) -> dict[JointId, float]:
        return {
            joint_id: self.config.pre_grasp_pose.get(joint_id, 0.0)
            for joint_id in self._torque_joints
        }

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
        self._sensor.reset()

    def _build_position_joints(
        self,
        joint_angles: dict[JointId, float],
        speed: int = 100,
        torque: int = 100,
    ) -> list[Joint]:
        joints: list[Joint] = []
        for joint_id, angle in joint_angles.items():
            joints.append(Joint(id=joint_id, angle=angle, speed=speed, torque=torque))
        return joints

    def _build_hold_position_joints(
        self,
        torque_value: Optional[int] = None,
        hold_joint_angles: Optional[Mapping[JointId, float]] = None,
    ) -> list[Joint]:
        if torque_value is None:
            torque_value = self.current_torque
        limited_torque = int(
            clip(
                abs(torque_value),
                0.0,
                float(self.config.position_torque_limit),
            ) # 限幅到位置模式力矩上限
        )
        hold_joint_angles = hold_joint_angles or self._init_hold_joint_angles()
        joints: list[Joint] = []
        for joint_id in self._torque_joints:
            joints.append(
                Joint(
                    id=joint_id,
                    angle=hold_joint_angles.get(joint_id, 0.0),
                    speed=int(self.config.position_speed_limit),
                    torque=limited_torque,
                )
            )
        return joints

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
        if self._visualizer is not None:
            self._visualizer.stop()

        control_thread = self._control_thread
        if (
            wait_control_thread
            and control_thread
            and control_thread.is_alive()
            and control_thread is not threading.current_thread()
        ):
            control_thread.join(timeout=1.0) # 等待控制线程优雅退出

        joints = self._build_position_joints(
            self._get_open_pose(),
            speed=self.config.release_open_speed,
            torque=self.config.release_open_torque,
        )
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if not ok:
            _logger.error("RELEASE phase: move_joints failed")
            self.state = GraspState.ERROR
            return False

        target_pose = self._get_open_pose()
        feedback_supported = callable(getattr(self.hand, "get_joints", None))
        if feedback_supported:
            if self._wait_joints_settled(
                target_pose,
                self.config.theta_err_th,
                self.config.release_check_cycles,
                self.config.release_timeout_s,
            ):
                self.state = GraspState.COMPLETED
                return True
            self.state = GraspState.ERROR
            return False
        # 无反馈支持时直接根据 move_joints 结果判定
        self.state = GraspState.COMPLETED if ok else GraspState.ERROR
        return ok

    def _wait_joints_settled(
        self,
        target_pose: dict[JointId, float],
        theta_err_th: float,
        check_cycles: int,
        timeout_s: float,
    ) -> bool:
        """轮询关节反馈，直到所有关节角度在阈值内连续满足指定周期数，或超时。"""
        settled_cycles = 0
        start = self._get_monotonic_time()
        while (self._get_monotonic_time() - start) < timeout_s:
            joints_feedback = self._safe_get_joints()
            if joints_feedback is None:
                _logger.error("Joint feedback lost during settle wait")
                return False
            actual = {j.id: j.angle for j in joints_feedback}
            is_settled = all(
                abs(actual.get(joint_id, target_angle) - target_angle) <= theta_err_th
                for joint_id, target_angle in target_pose.items()
            )
            if is_settled:
                settled_cycles += 1
                if settled_cycles >= check_cycles:
                    return True
            else:
                settled_cycles = 0
            time.sleep(self.config.control_period_s)
        _logger.error("Joint settle wait timeout")
        return False

    def _get_open_pose(self) -> dict[JointId, float]:
        return {
            JointId.THUMB_PIP: math.radians(0),
            JointId.THUMB_MCP: math.radians(0),
            JointId.THUMB_SWING: math.radians(0),
            JointId.THUMB_ROTATION: math.radians(0),
            JointId.FF_PIP: math.radians(0),
            JointId.FF_MCP: math.radians(0),
            JointId.FF_SWING: math.radians(0),
            JointId.MF_PIP: math.radians(0),
            JointId.MF_MCP: math.radians(0),
            JointId.RF_PIP: math.radians(0),
            JointId.RF_MCP: math.radians(0),
            JointId.LF_PIP: math.radians(0),
            JointId.LF_MCP: math.radians(0),
        }
