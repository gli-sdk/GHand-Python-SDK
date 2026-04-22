import math
import threading
import time
from typing import Mapping

import logging

from xiaoyao.dexhand import CtrlMode, DexHand, Joint, JointId

from .config import AdaptiveGraspConfig
from .force_planner import ForcePlanner, ObjectProfile
from .safety import SafetyMonitor, SafetyStatus
from .states import GraspState
from .tactile import TactileAnalyzer

_logger = logging.getLogger("xiaoyao.adaptive_grasp.controller")


class AdaptiveGrasper:
    _TORQUE_JOINTS = (
        JointId.THUMB_PIP,
        JointId.THUMB_MCP,
        JointId.FF_PIP,
        JointId.FF_MCP,
        JointId.MF_PIP,
        JointId.MF_MCP,
        JointId.RF_PIP,
        JointId.RF_MCP,
        JointId.LF_PIP,
        JointId.LF_MCP,
    )

    def __init__(self, hand: DexHand, config: AdaptiveGraspConfig | None = None):
        self.hand = hand
        self.config = config or AdaptiveGraspConfig()

        self.state = GraspState.IDLE
        self.current_torque = int(self._clamp_torque(self.config.base_torque))

        self._running = False
        self._control_thread: threading.Thread | None = None
        self._adaptive_hold_started_at: float | None = None
        self._get_monotonic_time = time.monotonic
        self._hold_joint_angles: dict[JointId, float] = {}

        self.tactile = TactileAnalyzer(self.config)
        self.force_planner = ForcePlanner(self.config, profile=None)
        self.safety = SafetyMonitor(self.config)

        self._reset_runtime_state()

    def set_object_profile(self, profile: ObjectProfile | None = None) -> None:
        self.force_planner = ForcePlanner(self.config, profile=profile)
        if profile is not None:
            self.tactile.set_friction_coeff(profile.friction_coeff)
        else:
            self.tactile.set_friction_coeff(self.config.default_friction_coeff)

        self._reset_runtime_state()

    def grasp(self) -> bool:
        try:
            self._running = True
            # 每次抓取前重置运行态，避免沿用上一次环路的积分与角度缓存。
            self._reset_runtime_state()
            # 按状态机顺序执行：OPEN -> PRE_GRASP -> CLOSING_TO_CONTACT。
            if not self._phase_open():
                self._running = False
                return False
            if not self._phase_pre_grasp():
                self._running = False
                return False
            if not self._phase_closing():
                self._running = False
                return False

            self.force_planner.set_baseline_angles(self._hold_joint_angles)
            self._start_adaptive_control()
            return True
        except Exception:
            _logger.exception("grasp failed with exception")
            self.state = GraspState.ERROR
            self._running = False
            return False

    def release(self) -> bool:
        return self._perform_release(join_control_thread=True)

    def stop(self) -> None:
        self._running = False
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)
        self.hand.stop()
        self.state = GraspState.STOPPED

    def get_state(self) -> GraspState:
        return self.state

    def _phase_open(self) -> bool:
        self.state = GraspState.OPEN
        # OPEN 阶段统一使用 POSITION 模式到张开姿态。
        speed = int(20 * self.config.fragile_speed_reduction) if self.force_planner.is_fragile_mode else 20
        torque = 20
        joints = self._build_position_joints(self._get_open_pose(), speed=speed, torque=torque)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(2)
        return ok

    def _phase_pre_grasp(self) -> bool:
        self.state = GraspState.PRE_GRASP
        # PRE_GRASP 阶段到预抓取姿态，给后续闭合留足形态先验。
        speed = int(50 * self.config.fragile_speed_reduction) if self.force_planner.is_fragile_mode else 50
        torque = 50
        joints = self._build_position_joints(self.config.pre_grasp_pose, speed=speed, torque=torque)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(5)
        return ok

    def _phase_closing(self) -> bool:
        self.state = GraspState.CLOSING_TO_CONTACT
        start = time.time()
        torque = int(self._clamp_torque(self.config.base_torque))
        self.current_torque = torque

        while self._running:
            if (time.time() - start) > self.config.phase_timeout:
                _logger.error("phase closing timeout")
                return False

            # 接触前在 TORQUE 模式下闭合找接触。
            joints = self._build_torque_joints(self.current_torque)
            if not self.hand.move_joints(joints, mode=CtrlMode.TORQUE):
                _logger.error("move_joints failed in phase closing")
                return False

            tactile_data = self._safe_get_tactile_data()
            joints_feedback = self._safe_get_joints()

            # 安全监控：空抓、传感器故障
            safety_report = self.safety.check(
                tactile_data=tactile_data,
                joint_feedback=joints_feedback,
                state=self.state,
            )
            if safety_report.status == SafetyStatus.FAULT:
                _logger.error(
                    "safety fault in closing: type=%s message=%s",
                    safety_report.fault_type,
                    safety_report.message,
                )
                if self.config.enable_fault_release_fallback:
                    return self._perform_release(join_control_thread=False)
                self.state = GraspState.ERROR
                self._running = False
                return False
            if safety_report.status == SafetyStatus.WARN:
                # 轻微异常（如单次数据丢包），冻结本周期，保持当前姿态
                time.sleep(self.config.control_period_s)
                continue

            if tactile_data:
                total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
                if total_fz >= self.config.contact_threshold_z:
                    # 达到接触阈值后，先做法向力校准，再切入 ADAPTIVE_HOLD。
                    if self._calibrate_closing_force(tactile_data, start):
                        return True
                    _logger.error("force calibration failed")
                    return False

            time.sleep(self.config.control_period_s)

        return False

    def _calibrate_closing_force(
        self,
        tactile_data: dict,
        phase_start: float,
        max_cycles: int = 2,
    ) -> bool:
        # 接触后法向力校准：在 1~2 个周期内将总法向力修正到 F_init ± 2 N。
        F_init = self.force_planner.F_init
        step = self.config.torque_adjust_step
        if self.force_planner.is_fragile_mode:
            step = int(step * self.config.fragile_step_reduction)

        # 90% 阈值提前减速：任一手指法向力接近上限时，步进增量临时降低 50%
        max_finger_fz = max(
            (abs(info.get_force_z()) for info in tactile_data.values()),
            default=0.0,
        )
        if max_finger_fz >= 0.9 * self.config.max_normal_force_per_finger:
            step = max(1, int(step * 0.5))

        for _ in range(max_cycles):
            if (time.time() - phase_start) > self.config.phase_timeout:
                return False
            if not self._running:
                return False

            total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
            if abs(total_fz - F_init) <= 2.0:
                return True

            if total_fz < F_init:
                self.current_torque = int(self._clamp_torque(self.current_torque + step))
            else:
                self.current_torque = int(self._clamp_torque(self.current_torque - step))

            joints = self._build_torque_joints(self.current_torque)
            if not self.hand.move_joints(joints, mode=CtrlMode.TORQUE):
                return False
            time.sleep(self.config.control_period_s)

            tactile_data = self._safe_get_tactile_data()
            if not tactile_data:
                return False

        # 微调结束后再次检查
        total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
        return abs(total_fz - F_init) <= 2.0

    def _start_adaptive_control(self) -> None:
        self.state = GraspState.ADAPTIVE_HOLD
        self._adaptive_hold_started_at = self._get_monotonic_time()
        self._control_thread = threading.Thread(target=self._adaptive_control_loop, daemon=True)
        self._control_thread.start()

    def _adaptive_control_loop(self) -> None:
        while self._running:
            try:
                self._run_control_step()
            except Exception:
                _logger.exception("adaptive control loop error")
                self._running = False
                self.state = GraspState.ERROR
                break
            time.sleep(self.config.control_period_s)

    def _run_control_step(self) -> bool:
        # 最高优先级：超时释放
        if self._should_auto_release():
            return self._perform_release(join_control_thread=False)

        tactile_data = self._safe_get_tactile_data()
        joints_feedback = self._safe_get_joints()

        # 安全监控
        safety_report = self.safety.check(
            tactile_data=tactile_data,
            joint_feedback=joints_feedback,
            state=self.state,
        )
        if safety_report.status == SafetyStatus.FAULT:
            _logger.error(
                "safety fault detected: type=%s message=%s",
                safety_report.fault_type,
                safety_report.message,
            )
            if self.config.enable_fault_release_fallback:
                # 异常降级：走 RELEASE 安全张开流程，避免直接停机导致手指保持夹紧
                return self._perform_release(join_control_thread=False)
            # 调试模式：直接停机报错
            self.state = GraspState.ERROR
            self._running = False
            return False
        if safety_report.status == SafetyStatus.WARN:
            # 冻结本周期，保持姿态
            return True

        if not tactile_data:
            return False

        # 触觉分析
        analysis = self.tactile.update(tactile_data)

        # 获取当前关节角度用于力规划
        current_angles = self._hold_joint_angles
        if joints_feedback:
            current_angles = self._extract_joint_angles(joints_feedback)

        # 力规划
        decision = self.force_planner.compute(analysis, current_angles)

        if abs(decision.control_u) <= self.config.epsilon:
            return True

        # 执行：POSITION 模式下发
        joints = self._build_hold_position_joints(
            torque_value=decision.next_torque,
            hold_joint_angles=decision.target_angles,
        )
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            self._hold_joint_angles = decision.target_angles
            self.current_torque = decision.next_torque
        return ok

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

    @staticmethod
    def _extract_joint_angles(joints_feedback: list) -> dict[JointId, float]:
        angles: dict[JointId, float] = {}
        for j in joints_feedback:
            jid = getattr(j, "id", j.get("id") if isinstance(j, dict) else None)
            jangle = getattr(j, "angle", j.get("angle", 0.0) if isinstance(j, dict) else 0.0)
            if jid is not None:
                angles[jid] = float(jangle)
        return angles

    def _build_torque_joints(self, torque: int) -> list[Joint]:
        joints = [Joint(id=joint_id, torque=torque) for joint_id in self._TORQUE_JOINTS]
        joints.append(Joint(id=JointId.THUMB_SWING, torque=5))
        joints.append(Joint(id=JointId.THUMB_ROTATION, torque=5))
        return joints

    def _init_hold_joint_angles(self) -> dict[JointId, float]:
        return {
            joint_id: self.config.pre_grasp_pose.get(joint_id, 0.0)
            for joint_id in self._TORQUE_JOINTS
        }

    def _reset_runtime_state(self) -> None:
        self._hold_joint_angles = self._init_hold_joint_angles()
        self.current_torque = int(self._clamp_torque(self.config.base_torque))
        self._adaptive_hold_started_at = None
        self.tactile.reset()
        self.force_planner.reset()
        self.safety.reset()

    def _build_position_joints(
        self,
        joint_angles: dict[JointId, float],
        speed: int = 100,
        torque: int = 100,
        speed_overrides: Mapping[JointId, int] | None = None,
        torque_overrides: Mapping[JointId, int] | None = None,
    ) -> list[Joint]:
        joints: list[Joint] = []
        speed_overrides = speed_overrides or {}
        torque_overrides = torque_overrides or {}
        for joint_id, angle in joint_angles.items():
            joint_speed = int(speed_overrides.get(joint_id, speed))
            joint_torque = int(torque_overrides.get(joint_id, torque))
            joints.append(Joint(id=joint_id, angle=angle, speed=joint_speed, torque=joint_torque))
        return joints

    def _build_hold_position_joints(
        self,
        torque_value: int | None = None,
        hold_joint_angles: Mapping[JointId, float] | None = None,
    ) -> list[Joint]:
        # ADAPTIVE_HOLD 专用 POSITION 指令构建：
        # 1) 仅作用于闭环相关关节集合；
        # 2) 统一应用保持阶段 speed/torque 限制；
        # 3) 允许调用方覆盖目标角与扭矩基准，其余走当前状态默认值。
        if torque_value is None:
            torque_value = self.current_torque
        limited_torque = int(
            self._clip(
                value=abs(self._clamp_torque(torque_value)),
                lower=0.0,
                upper=float(self.config.position_torque_limit),
            )
        )
        hold_joint_angles = hold_joint_angles or self._hold_joint_angles
        joints: list[Joint] = []
        for joint_id in self._TORQUE_JOINTS:
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

    def _perform_release(self, join_control_thread: bool) -> bool:
        self.state = GraspState.RELEASE
        self._running = False
        self._adaptive_hold_started_at = None

        control_thread = self._control_thread
        if (
            join_control_thread
            and control_thread
            and control_thread.is_alive()
            and control_thread is not threading.current_thread()
        ):
            control_thread.join(timeout=1.0)

        joints = self._build_position_joints(
            self._get_open_pose(),
            speed=self.config.release_open_speed,
            torque=self.config.release_open_torque,
        )
        # 先发一次 RELEASE 张开指令；若失败直接报错返回。
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if not ok:
            _logger.error("release move_joints failed")
            self.state = GraspState.ERROR
            return False

        target_pose = self._get_open_pose()
        settled_cycles = 0
        start = self._get_monotonic_time()
        feedback_supported = callable(getattr(self.hand, "get_joints", None))
        if feedback_supported:
            # 有关节反馈时按“误差阈值 + 连续周期数”判定真正到位。
            while (self._get_monotonic_time() - start) < self.config.release_timeout_s:
                joints_feedback = self._safe_get_joints()
                if joints_feedback is None:
                    break
                actual = {joint.id: joint.angle for joint in joints_feedback}
                is_settled = all(
                    abs(actual.get(joint_id, target_angle) - target_angle) <= self.config.theta_err_th
                    for joint_id, target_angle in target_pose.items()
                )
                if is_settled:
                    settled_cycles += 1
                    if settled_cycles >= self.config.release_check_cycles:
                        self.state = GraspState.COMPLETED
                        return True
                else:
                    settled_cycles = 0
                time.sleep(self.config.control_period_s)
            _logger.error("release joint settle timeout")
            self.state = GraspState.ERROR
            return False

        self.state = GraspState.COMPLETED if ok else GraspState.ERROR
        if not ok:
            _logger.error("release failed after move_joints")
        return ok

    def _clip(self, value: float, lower: float, upper: float) -> float:
        value_f = float(value)
        lower_f = float(lower)
        upper_f = float(upper)
        if upper_f < lower_f:
            upper_f = lower_f
        return max(lower_f, min(upper_f, value_f))

    def _clamp_torque(self, value: float) -> float:
        lower = -100.0
        upper = self._clip(value=float(self.config.max_torque), lower=lower, upper=100.0)
        return self._clip(value=value, lower=lower, upper=upper)

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
