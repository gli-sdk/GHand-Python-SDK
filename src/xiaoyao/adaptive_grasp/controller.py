import logging
import math
import threading
import time
from typing import Any, Mapping, Optional

from xiaoyao.dexhand import CtrlMode, DexHand, ErrorCode, Joint, JointId, State, TactileInfo, TactileSensorId

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

        # 传感器数据缓存（由 hand.subscribe 统一更新）
        self._latest_tactile_data: Optional[dict[TactileSensorId, Any]] = None
        self._latest_joint_feedback: Optional[list] = None
        self._sub_id: Optional[int] = None

        # 子模块
        self._tactile = TactileAnalyzer(self.config)
        self._safety = SafetyMonitor(self.config)
        self._force_planner: Optional[ForcePlanner] = None
        self._object_profile: Optional[ObjectProfile] = None

        # 对外只读：最近一次控制周期的结果快照
        self._last_tactile_analysis: Optional[Any] = None
        self._last_safety_report: Optional[Any] = None
        self._last_force_decisions: Optional[Any] = None
        self._last_tactile_sample_time_s: Optional[float] = None
        self._last_tactile_data_age_s: Optional[float] = None
        self._last_control_step_start_s: Optional[float] = None
        self._last_control_cycle_s: Optional[float] = None
        self._last_control_cycle_jitter_s: Optional[float] = None

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
            self._start_sensor_subscription()
            # 顺序执行状态机
            if not self._phase_open(): #OPEN 阶段
                self._running = False
                self._stop_sensor_subscription()
                return False
            if not self._phase_pre_grasp(): # 预抓取阶段
                self._running = False
                self._stop_sensor_subscription()
                return False
            if not self._phase_closing(): #闭合找接触阶段
                self._running = False
                self._stop_sensor_subscription()
                return False

            self._start_adaptive_control() # 自适应保持阶段
            return True
        except Exception:
            _logger.exception("grasp_core 异常")
            self.state = GraspState.ERROR
            self._running = False
            self._stop_sensor_subscription()
            return False

    def release(self) -> bool: #外部主动调用
        return self._perform_release(wait_control_thread=True)

    def stop(self) -> None:
        self._running = False
        self._stop_sensor_subscription()
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)
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
    def _phase_open(self) -> bool:
        self.state = GraspState.OPEN
        joints = self._build_position_joints(self._get_open_pose(), speed=50, torque=50)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(3) # 等待手指张开到位
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
        torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque)) # 初始闭合力矩设定
        self.current_torque = torque

        # 记录闭合启动时的初始关节角度（空抓判断基准）
        joints_feedback = self._safe_get_joints()
        if joints_feedback:
            self._safety.set_closing_baseline(joints_feedback)

        while self._running:
            if (time.time() - start) > self.config.phase_timeout:
                _logger.error("CLOSING phase timeout")
                return False

            joints = self._build_torque_joints(self.current_torque)
            self.hand.move_joints(joints, mode=CtrlMode.TORQUE)
            time.sleep(0.2)
            # 获取触觉传感器数据和关节反馈，用于空抓检测和接触判定
            # 获取触觉数据和关节反馈（由订阅回调统一更新）
            tactile_data = self._safe_get_tactile_data()
            if tactile_data is None:
                _logger.error("CLOSING phase: failed to get tactile data")
                return False
            joint_feedback = self._safe_get_joints()
            if joint_feedback is None:
                _logger.error("CLOSING phase: failed to get joint feedback")
                return False

            
            total_fz = self._sum_active_finger_normal_force(tactile_data)
            # 判断是否抓空
            if total_fz >= self.config.contact_threshold_z:
                # 进入自适应保持前进行力校准
                self._calibrate_force(tactile_data)
                time.sleep(self.config.control_period_s)
                return True
            else:
                empty_grasp_report = self._safety.IsGraspEmpty(joint_feedback, self.state)
                if empty_grasp_report.status != SafetyStatus.OK:
                    _logger.error("CLOSING phase: Grasp Empty")
                    self.state = GraspState.ERROR
                    return False
            
        return False

    def _calibrate_force(self, tactile_data: dict) -> None:
        """使用 1-2 步力矩调整，使总法向力匹配 F_init，误差控制在 ±2N 内。"""
        if self._force_planner is None:
            return
        F_init = self._force_planner.F_init
        if F_init <= 0:
            return
        for _ in range(2): # 最多校准 2 步
            total_fz = self._sum_active_finger_normal_force(tactile_data)
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
            tactile_data = self._safe_get_tactile_data() or tactile_data # 读取新数据，失败则沿用旧数据

    # ------------------------------------------------------------------
    # 自适应保持
    # ------------------------------------------------------------------
    def _start_adaptive_control(self) -> None:
        self.state = GraspState.ADAPTIVE_HOLD
        self._adaptive_hold_started_at = self._get_monotonic_time()
        self._control_thread = threading.Thread(target=self._adaptive_control_loop, daemon=True) # 后台守护线程
        self._control_thread.start()

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
    def _sensor_update_callback(self, tpdo: Any) -> None:
        """订阅回调：从 Tpdo 提取触觉数据和关节反馈，存入缓存。"""
        # 触觉数据提取（与 hand.get_tactile_data 保持一致）
        tactile_data = {
            TactileSensorId.THUMB: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 0)),
                resultant_force=tpdo.thumb_tactile.resultant_force,
                distributed_force=tpdo.thumb_tactile.sample_force,
            ),
            TactileSensorId.FOREFINGER: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 1)),
                resultant_force=tpdo.ff_tactile.resultant_force,
                distributed_force=tpdo.ff_tactile.sample_force,
            ),
            TactileSensorId.MIDDLE_FINGER: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 2)),
                resultant_force=tpdo.mf_tactile.resultant_force,
                distributed_force=tpdo.mf_tactile.sample_force,
            ),
            TactileSensorId.RING_FINGER: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 3)),
                resultant_force=tpdo.rf_tactile.resultant_force,
                distributed_force=tpdo.rf_tactile.sample_force,
            ),
            TactileSensorId.LITTLE_FINGER: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 4)),
                resultant_force=tpdo.lf_tactile.resultant_force,
                distributed_force=tpdo.lf_tactile.sample_force,
            ),
        }
        # 过滤活动手指
        self._latest_tactile_data = {
            finger: info
            for finger, info in tactile_data.items()
            if finger in self.config.active_fingers
        }
        self._last_tactile_sample_time_s = self._get_monotonic_time()

        # 关节反馈提取（与 hand.get_joints 保持一致）
        joint_mappings = [
            (JointId.THUMB_DIP, tpdo.th_dip),
            (JointId.THUMB_PIP, tpdo.th_pip),
            (JointId.THUMB_MCP, tpdo.th_mcp),
            (JointId.THUMB_SWING, tpdo.th_swing),
            (JointId.THUMB_ROTATION, tpdo.th_rot),
            (JointId.FF_DIP, tpdo.ff_dip),
            (JointId.FF_PIP, tpdo.ff_pip),
            (JointId.FF_MCP, tpdo.ff_mcp),
            (JointId.FF_SWING, tpdo.ff_swing),
            (JointId.MF_DIP, tpdo.mf_dip),
            (JointId.MF_PIP, tpdo.mf_pip),
            (JointId.MF_MCP, tpdo.mf_mcp),
            (JointId.RF_DIP, tpdo.rf_dip),
            (JointId.RF_PIP, tpdo.rf_pip),
            (JointId.RF_MCP, tpdo.rf_mcp),
            (JointId.LF_DIP, tpdo.lf_dip),
            (JointId.LF_PIP, tpdo.lf_pip),
            (JointId.LF_MCP, tpdo.lf_mcp),
        ]
        joints: list[Joint] = []
        for joint_id, joint_tpdo in joint_mappings:
            joints.append(
                Joint(
                    id=joint_id,
                    angle=joint_tpdo.angle,
                    speed=joint_tpdo.speed,
                    torque=joint_tpdo.torque,
                    state=State(joint_tpdo.state),
                    error=ErrorCode(joint_tpdo.error),
                )
            )
        self._latest_joint_feedback = joints

    def _start_sensor_subscription(self) -> None:
        self._latest_tactile_data = None
        self._latest_joint_feedback = None
        self._sub_id = self.hand.subscribe(self._sensor_update_callback)

    def _stop_sensor_subscription(self) -> None:
        if self._sub_id is not None:
            try:
                self.hand.unsubscribe(self._sub_id)
            except Exception:
                _logger.exception("Failed to unsubscribe sensor data")
            self._sub_id = None
        self._latest_tactile_data = None
        self._latest_joint_feedback = None

    def _safe_get_tactile_data(self) -> Optional[dict[TactileSensorId, Any]]:
        tactile_data = self._latest_tactile_data
        if tactile_data is None:
            self._last_tactile_data_age_s = None
            return None
        sample_time_s = self._last_tactile_sample_time_s
        if sample_time_s is not None:
            self._last_tactile_data_age_s = self._get_monotonic_time() - sample_time_s
        for finger, info in tactile_data.items():
            if not getattr(info, "state", True):
                if self.state in (GraspState.CLOSING_TO_CONTACT, GraspState.ADAPTIVE_HOLD):
                    _logger.error("TACTILE: active finger %s offline in %s", finger, self.state.name)
                    return None
        return tactile_data

    def _safe_get_joints(self) -> Optional[list]:
        return self._latest_joint_feedback

    def _get_current_angles(self, joint_feedback: Optional[list]) -> dict[JointId, float]:
        if joint_feedback:
            return {j.id: j.angle for j in joint_feedback}
        return self._init_hold_joint_angles()

    def _sum_active_finger_normal_force(self, tactile_data: Mapping[TactileSensorId, Any]) -> float:
        return sum(
            abs(info.get_force_z())
            for finger, info in tactile_data.items()
            if finger in self.config.active_fingers
        )

    def _build_torque_joints(self, torque: int) -> list[Joint]:
        active = set(self._torque_joints)
        joints = []
        for joint_id in AdaptiveGrasper._TORQUE_JOINTS:
            if joint_id in active:
                joints.append(Joint(id=joint_id, torque=torque))
            else:
                joints.append(Joint(id=joint_id, angle=0.0, speed=0, torque=0))
        joints.append(Joint(id=JointId.THUMB_ROTATION, angle=0.0, speed=0, torque=5))
        joints.append(Joint(id=JointId.THUMB_SWING, angle=0.0, speed=0, torque=5))
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
        self._last_tactile_sample_time_s = None
        self._last_tactile_data_age_s = None
        self._last_control_step_start_s = None
        self._last_control_cycle_s = None
        self._last_control_cycle_jitter_s = None
        self._latest_tactile_data = None
        self._latest_joint_feedback = None

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
