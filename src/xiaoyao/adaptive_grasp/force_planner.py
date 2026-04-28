import math
import time
from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .object_profile import ObjectProfile
from .tactility import TactileAnalysis, PerFingerAnalysis
from .utils import clip, JOINT_TO_FINGER


_G = 9.8  # 重力加速度 (m/s^2)，用于将物体重量转换为重力


@dataclass
class ForceDecision:
    control_u: float          # 复合控制律输出（总控制量）
    next_torque: int          # 下一周期目标力矩（速度限制后的值）
    target_angles: dict[JointId, float]  # 各关节目标角度
    is_fragile_mode: bool     # 是否处于易碎模式（限制速度和步长）
    near_limit: bool = False  # 是否有手指接近法向力上限（触发保守策略）


@dataclass
class _PidParams:
    """单指 PID 参数打包。"""
    K_p: float
    K_i: float
    K_d: float
    I_min: float
    I_max: float


class _FingerPidState:
    """单指 PID 内部状态，用于法向力闭环积分和微分项。"""
    def __init__(self):
        self.integral: float = 0.0     # 积分累积误差
        self.prev_error: float = 0.0   # 上一周期误差（用于微分）
        self._initialized: bool = False  # 首次调用标记，避免微分项跳变


class ForcePlanner:
    """
    力规划器：根据触觉分析结果计算关节目标角度与力矩。

    核心逻辑：
    1. 前馈项（u_ff）：滑移风险越大越加紧，法向力越限越放松。
    2. PID 项（u_pid）：追踪期望法向力 F_n_ref，使总法向力维持在 F_init 附近。
    3. 易碎模式：一旦法向力达到上限，只允许卸力（control_u <= 0）。
    """

    def __init__(self, config: AdaptiveGraspConfig, profile: Optional[ObjectProfile] = None):
        self.config = config
        self.profile = profile
        self.F_init = self._compute_F_init()              # 初始目标夹持力（N）
        #self.F_init =1.0
        self.is_fragile_mode = profile.is_fragile if profile else False  # 是否易碎物体

        self._finger_pid: dict[TactileSensorId, _FingerPidState] = {}
        self._last_compute_time: Optional[float] = None
        self._get_monotonic_time = time.monotonic

    def _compute_F_init(self) -> float:
        """
        计算初始目标夹持力，确保落在 [safe_force_min, 0.9·fz_limit] 的安全窗口。
        """

        cfg = self.config
        if self.profile is None:
            return cfg.base_holding_force

        finger_count = len(cfg.active_fingers) or 2 # 至少假设2根手指

        #1） 基于物理： 所有手指的摩擦力=摩擦系数*法向力=重力
        F = self.profile.weight_kg * _G / self.profile.friction_coeff / finger_count

        #2）单指上限
        fz_limit = self.profile.safe_force_max / finger_count

        #3) 安全窗口
        f_min = self.profile.safe_force_min
        f_max= 0.9*fz_limit if self.profile.is_fragile else fz_limit  # 如果易碎*0.9

        #) 把F钳制到安全窗口内
        F_clipped = clip(F, f_min, f_max)

        return F_clipped
    def _get_max_normal_force_per_finger(self, finger_count: int) -> float:
        """获取单指法向力上限：优先使用物体材质库的安全总力均摊，否则回退到配置值。"""
        if self.profile is not None:
            return self.profile.safe_force_max / finger_count
        return self.config.max_normal_force_per_finger

    def _get_effective_contact_count(self, finger_fz: dict[TactileSensorId, float]) -> int:
        active_finger_count = max(len(self.config.active_fingers), 1)
        contacting_fingers = sum(
            1
            for finger in self.config.active_fingers
            if finger_fz.get(finger, 0.0) > self.config.epsilon
        )
        return contacting_fingers or active_finger_count

    def _is_near_limit(self, finger_fz: dict[TactileSensorId, float], finger_count: int) -> bool:
        """判断是否有手指法向力超过 90% 上限（接近硬件/安全极限）。"""
        threshold = 0.9 * self._get_max_normal_force_per_finger(finger_count)
        return any(finger_fz.get(finger, 0.0) >= threshold for finger in self.config.active_fingers)

    def compute(
        self, analysis: TactileAnalysis, current_angles: dict[JointId, float], dt: Optional[float] = None
    ) -> dict[TactileSensorId, ForceDecision]:
        """
        为每根活跃手指独立计算控制决策。

        若 analysis.per_finger 存在，逐手指独立计算 control_u；
        否则回退到统一 control_u（所有活跃手指共用同一控制量）。
        返回字典：{手指 -> ForceDecision}，其中每个 ForceDecision 仅包含该手指对应关节的目标角度。
        外部可根据各手指的 control_u 单独判断是否下发更新。
        """
        cfg = self.config

        # 确定实际时间差 dt（PID 计算使用）
        now = self._get_monotonic_time()
        if dt is not None and dt > 0:
            actual_dt = dt
        elif self._last_compute_time is not None:
            actual_dt = now - self._last_compute_time
            if actual_dt <= 0 or actual_dt > 1.0:
                actual_dt = cfg.control_period_s
        else:
            actual_dt = cfg.control_period_s
        self._last_compute_time = now

        finger_count = self._get_effective_contact_count(analysis.finger_fz)
        near_limit = self._is_near_limit(analysis.finger_fz, finger_count)
        decisions: dict[TactileSensorId, ForceDecision] = {}

        if analysis.per_finger:
            for finger in cfg.active_fingers:
                finger_analysis = analysis.per_finger.get(finger)
                if finger_analysis is None:
                    continue
                control_u = self._compute_finger_control_u(finger, finger_analysis, finger_count, actual_dt)
                decisions[finger] = self._build_finger_decision(finger, control_u, current_angles, near_limit)
        else:
            control_u = self._compute_unified_control_u(analysis, finger_count, actual_dt)
            for finger in cfg.active_fingers:
                decisions[finger] = self._build_finger_decision(finger, control_u, current_angles, near_limit)

        return decisions

    def _compute_pid_control_u(
        self,
        finger: TactileSensorId,
        s_k: float,
        fz: float,
        fz_limit: float,
        F_n_ref: float,
        dt: float,
    ) -> float:
        """前馈+PID计算。"""
        pid_state = self._get_or_create_pid(finger)
        e_k = F_n_ref - fz
        pid_param = self._get_pid_params(finger)
        pid_state.integral = clip(pid_state.integral + e_k * dt, pid_param.I_min, pid_param.I_max)
        if pid_state._initialized:
            derivative = (e_k - pid_state.prev_error) / dt
        else:
            derivative = 0.0
            pid_state._initialized = True
        pid_state.prev_error = e_k
        u_pid = pid_param.K_p * e_k + pid_param.K_i * pid_state.integral + pid_param.K_d * derivative

        control_u = u_pid
        if self.is_fragile_mode and fz >= fz_limit:
            control_u = min(control_u, 0.0)

        return control_u

    def _compute_finger_control_u(
        self,
        finger: TactileSensorId,
        per_finger_analysis: PerFingerAnalysis,
        finger_count: int,
        dt: float,
    ) -> float:
        F_n_ref = self.F_init / finger_count
        fz_limit = self._get_max_normal_force_per_finger(finger_count)
        return self._compute_pid_control_u(
            finger,
            s_k=per_finger_analysis.s_total,
            fz=per_finger_analysis.fz,
            fz_limit=fz_limit,
            F_n_ref=F_n_ref,
            dt=dt,
        )

    def _compute_unified_control_u(self, analysis: TactileAnalysis, finger_count: int, dt: float) -> float:
        """无 per_finger 时回退：用大拇指代表整体计算统一 control_u。

        注意：统一控制复用 THUMB 的 PID 状态以保持向后兼容。
        """
        F_n_ref = self.F_init / finger_count
        max_fz_limit = self._get_max_normal_force_per_finger(finger_count)
        max_fz = max(analysis.finger_fz.values()) if analysis.finger_fz else 0.0
        return self._compute_pid_control_u(
            TactileSensorId.THUMB,
            s_k=analysis.slip_risk,
            fz=max_fz,
            fz_limit=max_fz_limit,
            F_n_ref=F_n_ref,
            dt=dt,
        )

    def _build_finger_decision(
        self,
        finger: TactileSensorId,
        control_u: float,
        current_angles: dict[JointId, float],
        near_limit: bool,
    ) -> ForceDecision:
        """将单指 control_u 映射为该手指对应关节的角度增量，封装为 ForceDecision。"""
        cfg = self.config
        target_angles: dict[JointId, float] = {}

        total_delta = control_u 
        delta_limit = cfg.delta_theta_limit
        if self.is_fragile_mode:
            delta_limit *= cfg.fragile_step_reduction
        if near_limit:
            delta_limit *= 0.8 
        total_delta = clip(total_delta, -delta_limit, delta_limit)

        mcp_delta = total_delta * cfg.K_MCP
        pip_delta = total_delta * cfg.K_PIP

        for joint_id, angle in current_angles.items():
            mapped_finger = JOINT_TO_FINGER.get(joint_id)
            if mapped_finger != finger:
                continue
            # THUMB_SWING,THUMB_ROTATION,FF_SWING这些关节保留角度，不更新
            if "MCP" in joint_id.name:
                target_angles[joint_id] = angle + mcp_delta
            elif "PIP" in joint_id.name:
                target_angles[joint_id] = angle + pip_delta
            else:
                target_angles[joint_id] = angle

        return ForceDecision(
            control_u=control_u,
            next_torque=self._compute_next_torque(),
            target_angles=target_angles,
            is_fragile_mode=self.is_fragile_mode,
            near_limit=near_limit,
        )

    def _compute_next_torque(self) -> int:
        """计算下一周期输出力矩：受cfg中的力矩限制，易碎模式再按比例降低。"""
        cfg = self.config
        next_torque = cfg.position_torque_limit
        if self.is_fragile_mode:
            next_torque = int(cfg.position_torque_limit * cfg.fragile_torque_reduction)
        return next_torque

    def reset(self) -> None:
        """重置所有运行时状态（PID 积分、保持角度等）。"""
        self._finger_pid.clear()
        self._last_compute_time = None

    def _get_or_create_pid(self, finger: TactileSensorId) -> _FingerPidState:
        """获取指定手指的 PID 状态，不存在则惰性创建。"""
        if finger not in self._finger_pid:
            self._finger_pid[finger] = _FingerPidState()
        return self._finger_pid[finger]

    def _get_pid_param(self, finger: TactileSensorId, param_name: str) -> float:
        """获取单指 PID 参数；若该手指未单独配置，则回退到全局 AdaptiveGraspConfig 参数。"""
        per_finger_cfg = self.config.per_finger_pid.get(finger)
        if per_finger_cfg is not None:
            val = getattr(per_finger_cfg, param_name, None)
            if val is not None:
                return val
        return getattr(self.config, param_name)

    def _get_pid_params(self, finger: TactileSensorId) -> _PidParams:
        """一次性获取单指全部 PID 参数。"""
        return _PidParams(
            K_p=self._get_pid_param(finger, "K_p"),
            K_i=self._get_pid_param(finger, "K_i"),
            K_d=self._get_pid_param(finger, "K_d"),
            I_min=self._get_pid_param(finger, "I_min"),
            I_max=self._get_pid_param(finger, "I_max"),
        )
