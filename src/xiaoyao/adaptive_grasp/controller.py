import logging
import math
import threading
import time
from typing import Mapping, Optional

from xiaoyao.dexhand import CtrlMode, DexHand, Joint, JointId, TactileSensorId

from .config import AdaptiveGraspConfig
from .states import GraspState
from .tactility import TactileAnalyzer
from .object_profile import ObjectProfile
from .force_planner import ForcePlanner
from .safety import SafetyMonitor, SafetyStatus
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

        # Submodules
        self._tactile = TactileAnalyzer(self.config)
        self._safety = SafetyMonitor(self.config)
        self._force_planner: Optional[ForcePlanner] = None
        self._object_profile: Optional[ObjectProfile] = None

    def grasp_core(self, object_profile: Optional[ObjectProfile] = None) -> bool:
        try:
            self._running = True
            self._reset_runtime_state()
            # 基于材质库，初始化相关参数
            self._object_profile = object_profile
            if object_profile is not None:
                self._force_planner = ForcePlanner(self.config, object_profile)
                self._tactile.set_friction_coeff(object_profile.friction_coeff)
            else:
                self._force_planner = ForcePlanner(self.config, None)
                self._tactile.set_friction_coeff(self.config.default_friction_coeff)
            # 顺序执行状态机
            if not self._phase_open(): #OPEN 阶段
                self._running = False
                return False
            if not self._phase_pre_grasp(): # 预抓取阶段
                self._running = False
                return False
            if not self._phase_closing(): #闭合找接触阶段
                self._running = False
                return False

            self._start_adaptive_control() # 自适应保持阶段
            return True
        except Exception:
            self.state = GraspState.ERROR
            self._running = False
            return False

    def release(self) -> bool: #外部主动调用
        return self._perform_release(wait_control_thread=True)

    def stop(self) -> None:
        self._running = False
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)
        self.hand.stop()
        self.state = GraspState.STOPPED

    def get_state(self) -> GraspState:
        return self.state

    # ------------------------------------------------------------------
    # Phases
    # ------------------------------------------------------------------
    def _phase_open(self) -> bool:
        self.state = GraspState.OPEN
        joints = self._build_position_joints(self._get_open_pose(), speed=20, torque=20)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(2) # 等待手指张开到位
        else:
            _logger.error("OPEN phase: move_joints failed")
        return ok

    def _phase_pre_grasp(self) -> bool:
        self.state = GraspState.PRE_GRASP
        joints = self._build_position_joints(self.config.pre_grasp_pose, speed=50, torque=50)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(5) # 等待预抓取姿态到位
        else:
            _logger.error("PRE_GRASP phase: move_joints failed")
        return ok

    def _phase_closing(self) -> bool:
        self.state = GraspState.CLOSING_TO_CONTACT
        start = time.time() # 阶段开始时间，用于超时判定
        torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque)) # 初始闭合力矩
        self.current_torque = torque

        while self._running:
            if (time.time() - start) > self.config.phase_timeout:
                _logger.error("CLOSING phase timeout")
                return False

            joints = self._build_torque_joints(self.current_torque)
            if not self.hand.move_joints(joints, mode=CtrlMode.TORQUE):
                _logger.error("CLOSING phase: move_joints failed")
                return False

            tactile_data = self._safe_get_tactile_data()
            if tactile_data:
                total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
                if total_fz >= self.config.contact_threshold_z:
                    # Force calibration before entering ADAPTIVE_HOLD
                    self._calibrate_force(tactile_data)
                    return True

                # Safety: empty grasp check
                safety = self._safety.check(tactile_data, None, self.state)
                if safety.status == SafetyStatus.FAULT:
                    _logger.error("CLOSING phase: safety FAULT")
                    self.state = GraspState.ERROR
                    return False

            time.sleep(self.config.control_period_s)

        return False

    def _calibrate_force(self, tactile_data: dict) -> None:
        """Match total normal force to F_init within ±2N using 1-2 torque steps."""
        if self._force_planner is None:
            return
        F_init = self._force_planner.F_init
        if F_init <= 0:
            return
        for _ in range(2): # 最多校准 2 步
            total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
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
            self.hand.move_joints(joints, mode=CtrlMode.TORQUE)
            time.sleep(self.config.control_period_s)
            tactile_data = self._safe_get_tactile_data() or tactile_data # 读取新数据，失败则沿用旧数据

    # ------------------------------------------------------------------
    # ADAPTIVE_HOLD
    # ------------------------------------------------------------------
    def _start_adaptive_control(self) -> None:
        self.state = GraspState.ADAPTIVE_HOLD
        self._adaptive_hold_started_at = self._get_monotonic_time()
        # Set baseline angles from current joint feedback if available
        joints_feedback = self._safe_get_joints()
        if joints_feedback:
            baseline = {j.id: j.angle for j in joints_feedback}
        else:
            baseline = self._init_hold_joint_angles()
        if self._force_planner is not None:
            self._force_planner.set_baseline_angles(baseline)
        self._control_thread = threading.Thread(target=self._adaptive_control_loop, daemon=True) # 后台守护线程
        self._control_thread.start()

    def _adaptive_control_loop(self) -> None:
        while self._running:
            self._run_control_step()
            time.sleep(self.config.control_period_s)

    def _run_control_step(self) -> bool:
        if self._should_auto_release():
            return self._perform_release(wait_control_thread=False)

        tactile_data = self._safe_get_tactile_data()
        joint_feedback = self._safe_get_joints()

        # 1) Safety check
        safety = self._safety.check(tactile_data, joint_feedback, self.state)
        if safety.status == SafetyStatus.FAULT:
            if self.config.enable_fault_release_fallback:
                return self._perform_release(wait_control_thread=False)
            self.state = GraspState.ERROR
            self._running = False
            return False

        if tactile_data is None:
            return True # 传感器缺失时保持上一周期姿态，不中断循环

        # 2) Tactile analysis
        analysis = self._tactile.update(tactile_data)

        # 3) Force planning
        current_angles = self._get_current_angles(joint_feedback)
        if self._force_planner is not None:
            decision = self._force_planner.compute(analysis, current_angles)
            next_angles = decision.target_angles
            next_torque = decision.next_torque
        else:
            # Fallback to V1.0-like behavior if no planner
            next_angles = current_angles
            next_torque = self.current_torque

        # 4) Execute
        joints = self._build_hold_position_joints(next_torque, next_angles)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if not ok:
            _logger.error("ADAPTIVE_HOLD: move_joints failed")
        return ok

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _safe_get_tactile_data(self):
        try:
            return self.hand.get_tactile_data()
        except Exception:
            return None

    def _safe_get_joints(self):
        get_joints = getattr(self.hand, "get_joints", None)
        if not callable(get_joints):
            return None
        try:
            return get_joints()
        except Exception:
            return None

    def _get_current_angles(self, joint_feedback: Optional[list]) -> dict[JointId, float]:
        if joint_feedback:
            return {j.id: j.angle for j in joint_feedback}
        return self._init_hold_joint_angles()

    def _build_torque_joints(self, torque: int) -> list[Joint]:
        return [Joint(id=joint_id, torque=torque) for joint_id in self._torque_joints]

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
            ) # 限幅到 POSITION 力矩上限
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
