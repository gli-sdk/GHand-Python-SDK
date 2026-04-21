import math
import threading
import time
from collections import deque
from typing import Mapping

from xiaoyao.dexhand import CtrlMode, DexHand, Joint, JointId, TactileSensorId

from .config import AdaptiveGraspConfig
from .force_planner import ForcePlanner, ObjectProfile
from .safety import SafetyMonitor, SafetyStatus
from .states import GraspState
from .tactile import TactileAnalyzer


class AdaptiveGrasper:
    # 控制量到关节总角增量的映射系数：u 每增加 1，对应闭合约 0.5°。
    _HOLD_CLOSURE_STEP_PER_TORQUE = math.radians(0.5)
    # 相对 ADAPTIVE_HOLD 基线角度的累计变化保护上限（防止持续收紧/放松过度）。
    _HOLD_CLOSURE_MAX_DELTA = math.radians(20.0)
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
    _MCP_JOINTS = (
        JointId.THUMB_MCP,
        JointId.FF_MCP,
        JointId.MF_MCP,
        JointId.RF_MCP,
        JointId.LF_MCP,
    )
    _PIP_JOINTS = (
        JointId.THUMB_PIP,
        JointId.FF_PIP,
        JointId.MF_PIP,
        JointId.RF_PIP,
        JointId.LF_PIP,
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
        self._pid_integral: float = 0.0
        self._pid_prev_error: float = 0.0
        self._tactile_windows: dict[TactileSensorId, deque[float]] = {}
        self._hold_joint_angles: dict[JointId, float] = {}
        self._hold_joint_angle_baseline: dict[JointId, float] = {}

        self.tactile = TactileAnalyzer(self.config)
        self.force_planner = ForcePlanner(self.config, profile=None)
        self.safety = SafetyMonitor(self.config)

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
        self.state = GraspState.OPENING
        # OPEN 阶段统一使用 POSITION 模式到张开姿态。
        joints = self._build_position_joints(self._get_open_pose(),speed = 20,torque=20)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(2)
        return ok

    def _phase_pre_grasp(self) -> bool:
        self.state = GraspState.PRE_GRASPING
        # PRE_GRASP 阶段到预抓取姿态，给后续闭合留足形态先验。
        joints = self._build_position_joints(self.config.pre_grasp_pose,speed=50,torque=50)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(5)
        return ok

    def _phase_closing(self) -> bool:
        self.state = GraspState.CLOSING
        start = time.time()
        torque = int(self._clamp_torque(self.config.base_torque))
        self.current_torque = torque

        while self._running:
            if (time.time() - start) > self.config.phase_timeout:
                return False

            # 接触前在 TORQUE 模式下闭合找接触。
            joints = self._build_torque_joints(self.current_torque)
            if not self.hand.move_joints(joints, mode=CtrlMode.TORQUE):
                return False

            tactile_data = self._safe_get_tactile_data()
            if tactile_data:
                total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
                if total_fz >= self.config.contact_threshold_z:
                    # 达到接触阈值后切入 ADAPTIVE_HOLD。
                    return True

            time.sleep(self.config.control_period_s)

        return False

    def _start_adaptive_control(self) -> None:
        self.state = GraspState.ADAPTIVE_HOLDING
        self._adaptive_hold_started_at = self._get_monotonic_time()
        self._control_thread = threading.Thread(target=self._adaptive_control_loop, daemon=True)
        self._control_thread.start()

    def _adaptive_control_loop(self) -> None:
        while self._running:
            self._run_control_step()
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
            current_angles = {joint.id: joint.angle for joint in joints_feedback}

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

    def _build_torque_joints(self, torque: int) -> list[Joint]:
        return [Joint(id=joint_id, torque=torque) for joint_id in self._TORQUE_JOINTS]

    def _init_hold_joint_angles(self) -> dict[JointId, float]:
        return {
            joint_id: self.config.pre_grasp_pose.get(joint_id, 0.0)
            for joint_id in self._TORQUE_JOINTS
        }

    def _reset_runtime_state(self) -> None:
        self._tactile_windows = {
            finger: deque(maxlen=self.config.sliding_window_size)
            for finger in TactileSensorId
        }
        self._hold_joint_angles = self._init_hold_joint_angles()
        self._hold_joint_angle_baseline = dict(self._hold_joint_angles)
        self.current_torque = int(self._clamp_torque(self.config.base_torque))
        self._adaptive_hold_started_at = None
        self._pid_integral = 0.0
        self._pid_prev_error = 0.0
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

    def _get_next_hold_joint_angles(self, control_u: float) -> dict[JointId, float]:
        # 控制量很小时直接保持当前目标，避免抖动。
        if abs(control_u) <= self._HOLD_CLOSURE_STEP_PER_TORQUE:
            return dict(self._hold_joint_angles)

        # 先把控制量映射为“总角增量”，再做单周期限幅。
        raw_total_delta = float(control_u) * self._HOLD_CLOSURE_STEP_PER_TORQUE
        total_delta = self._clip(
            value=raw_total_delta,
            lower=-float(self.config.delta_theta_limit),
            upper=float(self.config.delta_theta_limit),
        )
        # 按配置系数把总增量分配给 MCP 与 PIP。
        mcp_delta = total_delta * float(self.config.K_MCP)
        pip_delta = total_delta * float(self.config.K_PIP)

        next_angles = dict(self._hold_joint_angles)
        for joint_id in self._TORQUE_JOINTS:
            baseline_angle = self._hold_joint_angle_baseline.get(joint_id, 0.0)
            current_angle = next_angles.get(joint_id, baseline_angle)
            # 每个关节都相对进入 ADAPTIVE_HOLD 的基线角做累计保护限幅。
            min_angle = baseline_angle - self._HOLD_CLOSURE_MAX_DELTA
            max_angle = baseline_angle + self._HOLD_CLOSURE_MAX_DELTA
            if joint_id in self._MCP_JOINTS:
                next_value = current_angle + mcp_delta
            else:
                next_value = current_angle + pip_delta
            next_angles[joint_id] = self._clip(next_value, min_angle, max_angle)
        return next_angles

    def _normalize_slip_risk(self, variance: float) -> float:
        cfg = self.config
        if variance <= cfg.variance_baseline:
            return 0.0
        if variance >= cfg.variance_threshold:
            return 1.0
        denom = (cfg.variance_threshold - cfg.variance_baseline) + cfg.epsilon
        return self._clip(
            value=(variance - cfg.variance_baseline) / denom,
            lower=0.0,
            upper=1.0,
        )

    def _normal_force_error(self, max_fz: float) -> float:
        limit = self.config.max_normal_force_per_finger
        return self._clip(
            value=(max_fz - limit) / (limit + self.config.epsilon),
            lower=0.0,
            upper=float("inf"),
        )

    def _compute_control_u(self, variance: float, max_fz: float) -> float:
        # 前馈项：滑移风险推动收紧，法向超限推动卸力。
        s_k = self._normalize_slip_risk(variance)
        e_nk = self._normal_force_error(max_fz)
        u_ff = (self.config.K_s * s_k) - (self.config.K_n * e_nk)

        # PID 项：围绕 s_ref 调节，积分项带上下限以避免积分饱和。
        e_k = self.config.s_ref - s_k
        self._pid_integral = self._clip(
            value=self._pid_integral + (e_k * self.config.control_period_s),
            lower=self.config.I_min,
            upper=self.config.I_max,
        )
        derivative = (e_k - self._pid_prev_error) / self.config.control_period_s
        self._pid_prev_error = e_k
        u_pid = (
            (self.config.K_p * e_k)
            + (self.config.K_i * self._pid_integral)
            + (self.config.K_d * derivative)
        )
        return u_ff + u_pid

    def _should_auto_release(self) -> bool:
        if self._adaptive_hold_started_at is None:
            return False
        elapsed = self._get_monotonic_time() - self._adaptive_hold_started_at
        return elapsed >= self.config.release_hold_time_s

    def _perform_release(self, join_control_thread: bool) -> bool:
        self.state = GraspState.RELEASING
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
            self.state = GraspState.ERROR
            return False

        self.state = GraspState.COMPLETED if ok else GraspState.ERROR
        return ok

    def _calculate_variance(self) -> float:
        values = []
        for window in self._tactile_windows.values():
            if len(window) < 3:
                continue
            mean = sum(window) / len(window)
            var = sum((item - mean) ** 2 for item in window) / len(window)
            values.append(var)
        return max(values) if values else 0.0

    def _calculate_torque_from_slip(self, finger_fz: dict[TactileSensorId, float], variance: float) -> int:
        if not finger_fz:
            return self.current_torque
        if any(fz >= self.config.max_normal_force_per_finger for fz in finger_fz.values()):
            return self.current_torque

        if variance >= self.config.variance_threshold:
            target = self.current_torque + self.config.torque_adjust_step
            return int(round(self._clamp_torque(target)))

        return self.current_torque

    def _calculate_next_torque(self, finger_fz: dict[TactileSensorId, float], variance: float) -> int:
        if not finger_fz:
            return self.current_torque

        return self._calculate_torque_from_slip(finger_fz=finger_fz, variance=variance)

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
