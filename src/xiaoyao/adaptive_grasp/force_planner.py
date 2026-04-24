import math
from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .object_profile import ObjectProfile
from .tactility import TactileAnalysis
from .utils import clip


_G = 9.8  # 重力加速度 (m/s^2)，用于将物体重量转换为重力

# 关节到触觉传感器手指的映射：同一根手指的多个关节共享一个力传感器
_JOINT_TO_FINGER: dict[JointId, TactileSensorId] = {
    JointId.THUMB_MCP: TactileSensorId.THUMB,
    JointId.THUMB_PIP: TactileSensorId.THUMB,
    JointId.FF_MCP: TactileSensorId.FOREFINGER,
    JointId.FF_PIP: TactileSensorId.FOREFINGER,
    JointId.FF_SWING: TactileSensorId.FOREFINGER,
    JointId.MF_MCP: TactileSensorId.MIDDLE_FINGER,
    JointId.MF_PIP: TactileSensorId.MIDDLE_FINGER,
    JointId.RF_MCP: TactileSensorId.RING_FINGER,
    JointId.RF_PIP: TactileSensorId.RING_FINGER,
    JointId.LF_MCP: TactileSensorId.LITTLE_FINGER,
    JointId.LF_PIP: TactileSensorId.LITTLE_FINGER,
}


@dataclass
class ForceDecision:
    control_u: float          # 复合控制律输出（总控制量）
    next_torque: int          # 下一周期目标力矩（速度限制后的值）
    target_angles: dict[JointId, float]  # 各关节目标角度
    is_fragile_mode: bool     # 是否处于易碎模式（限制速度和步长）
    near_limit: bool = False  # 是否有手指接近法向力上限（触发保守策略）


class _FingerPidState:
    """单指 PID 内部状态，用于法向力闭环积分和微分项。"""

    def __init__(self):
        self.integral: float = 0.0     # 积分累积误差
        self.prev_error: float = 0.0   # 上一周期误差（用于微分）


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
        self.is_fragile_mode = profile.is_fragile if profile else False  # 是否易碎物体

        self._finger_pid: dict[TactileSensorId, _FingerPidState] = {}
        self._hold_joint_angles: dict[JointId, float] = {}            # 当前保持姿态
        self._hold_joint_angle_baseline: dict[JointId, float] = {}    # 基线姿态（限制范围用）

    def _compute_F_init(self) -> float:
        """计算初始目标夹持力：重量×重力×安全系数 + 基础保持力，再钳位到安全区间。"""
        cfg = self.config
        if self.profile is None:
            return cfg.base_holding_force
        F = self.profile.weight_kg * _G * cfg.safety_factor + cfg.base_holding_force
        return clip(F, self.profile.safe_force_min, self.profile.safe_force_max)

    def _is_near_limit(self, finger_fz: dict[TactileSensorId, float]) -> bool:
        """判断是否有手指法向力超过 90% 上限（接近硬件/安全极限）。"""
        threshold = 0.9 * self.config.max_normal_force_per_finger
        return any(fz >= threshold for fz in finger_fz.values())

    def compute(self, analysis: TactileAnalysis, current_angles: dict[JointId, float]) -> ForceDecision:
        """
        入口：根据触觉分析计算控制决策。

        若 analysis.per_finger 存在，调用逐手指独立控制；
        否则回退到统一控制（单指 PID，所有关节同步）。
        """
        cfg = self.config

        if analysis.per_finger:
            return self._compute_per_finger(analysis, current_angles)

        # ---------- 统一控制回退（兼容无 per_finger 的情况） ----------
        near_limit = self._is_near_limit(analysis.finger_fz)
        finger_count = max(len(analysis.finger_fz), 1)
        F_n_ref = self.F_init / finger_count               # 每根手指分担的期望法向力
        max_fz = max(analysis.finger_fz.values()) if analysis.finger_fz else 0.0

        # 前馈：滑移风险 → 加紧；法向力超限 → 放松
        s_k = analysis.slip_risk
        e_nk = max(0.0, (max_fz - cfg.max_normal_force_per_finger) / (cfg.max_normal_force_per_finger + cfg.epsilon))
        u_ff = cfg.K_s * s_k - cfg.K_n * e_nk

        # PID：追踪每指期望法向力（这里用最大指力代表整体）
        pid_state = self._get_or_create_pid(TactileSensorId.THUMB)
        e_k = F_n_ref - max_fz
        pid_state.integral = clip(pid_state.integral + e_k * cfg.control_period_s, cfg.I_min, cfg.I_max)
        derivative = (e_k - pid_state.prev_error) / cfg.control_period_s
        pid_state.prev_error = e_k
        u_pid = cfg.K_p * e_k + cfg.K_i * pid_state.integral + cfg.K_d * derivative

        control_u = u_ff + u_pid

        # 易碎模式：法向力已达上限时禁止继续增加（只能卸力）
        if self.is_fragile_mode and max_fz >= cfg.max_normal_force_per_finger:
            control_u = min(control_u, 0.0)

        target_angles = self._allocate_delta_to_joints(control_u, current_angles, near_limit=near_limit)
        next_torque = self._compute_next_torque()

        return ForceDecision(
            control_u=control_u,
            next_torque=next_torque,
            target_angles=target_angles,
            is_fragile_mode=self.is_fragile_mode,
            near_limit=near_limit,
        )

    def _compute_per_finger(
        self, analysis: TactileAnalysis, current_angles: dict[JointId, float]
    ) -> ForceDecision:
        """
        逐手指独立控制：为每根手指单独计算 control_u 并映射到对应关节。

        返回所有手指中 control_u 绝对值最大的那个作为 representative，
        用于外部判断是否需要继续更新。
        """
        cfg = self.config
        finger_count = max(len(analysis.per_finger), 1)
        F_n_ref = self.F_init / finger_count

        target_angles = dict(current_angles)
        control_u_values: list[float] = []
        near_limit = self._is_near_limit(analysis.finger_fz)

        for finger, fa in analysis.per_finger.items():
            if finger not in cfg.active_fingers:
                continue  # 跳过非活跃手指，避免不参与的手指被闭环驱动
            s_total = fa.s_total
            fz = fa.fz

            # 前馈：滑移风险与法向力超限
            e_nk = max(0.0, (fz - cfg.max_normal_force_per_finger) / (cfg.max_normal_force_per_finger + cfg.epsilon))
            u_ff = cfg.K_s * s_total - cfg.K_n * e_nk

            # PID：独立追踪该手指的期望法向力
            pid_state = self._get_or_create_pid(finger)
            e_k = F_n_ref - fz
            pid_state.integral = clip(pid_state.integral + e_k * cfg.control_period_s, cfg.I_min, cfg.I_max)
            derivative = (e_k - pid_state.prev_error) / cfg.control_period_s
            pid_state.prev_error = e_k
            u_pid = cfg.K_p * e_k + cfg.K_i * pid_state.integral + cfg.K_d * derivative

            control_u = u_ff + u_pid

            # 易碎模式：单指法向力超限则禁止该手指继续增加
            if self.is_fragile_mode and fz >= cfg.max_normal_force_per_finger:
                control_u = min(control_u, 0.0)

            control_u_values.append(control_u)

            # 将该手指的 control_u 映射到对应关节（MCP/PIP 按比例分配）
            total_delta = control_u * math.radians(0.5)     # 控制量 → 角度增量（粗略映射）
            delta_limit = cfg.delta_theta_limit
            if self.is_fragile_mode:
                delta_limit *= cfg.fragile_step_reduction   # 易碎模式减小步长
            if near_limit:
                delta_limit *= 0.5                          # 接近上限时进一步保守
            total_delta = clip(total_delta, -delta_limit, delta_limit)

            mcp_delta = total_delta * cfg.K_MCP
            pip_delta = total_delta * cfg.K_PIP

            for joint_id, angle in current_angles.items():
                mapped_finger = _JOINT_TO_FINGER.get(joint_id)
                if mapped_finger != finger:
                    continue
                baseline = self._hold_joint_angle_baseline.get(joint_id, 0.0)
                min_a = baseline - math.radians(20.0)       # 相对基线最多回退 20°
                max_a = baseline + math.radians(20.0)       # 相对基线最多收紧 20°
                if "MCP" in joint_id.name:
                    target_angles[joint_id] = clip(angle + mcp_delta, min_a, max_a)
                elif "PIP" in joint_id.name:
                    target_angles[joint_id] = clip(angle + pip_delta, min_a, max_a)
                else:
                    # SWING/ROTATION 等辅助关节沿用当前角（不参与闭环微调）
                    target_angles[joint_id] = angle

        next_torque = self._compute_next_torque()

        # 返回绝对值最大的 control_u，保留符号，用于外部判断是否需要更新
        representative_control_u = max(control_u_values, key=abs) if control_u_values else 0.0
        return ForceDecision(
            control_u=representative_control_u,
            next_torque=next_torque,
            target_angles=target_angles,
            is_fragile_mode=self.is_fragile_mode,
            near_limit=near_limit,
        )

    def _allocate_delta_to_joints(
        self, control_u: float, current_angles: dict[JointId, float], *, near_limit: bool = False
    ) -> dict[JointId, float]:
        """
        统一控制下的角度分配：所有参与关节同步施加同一 control_u。

        与 _compute_per_finger 的区别：不区分手指，所有关节共享一个控制量。
        """
        cfg = self.config
        total_delta = control_u * math.radians(0.5)
        delta_limit = cfg.delta_theta_limit
        if self.is_fragile_mode:
            delta_limit *= cfg.fragile_step_reduction
        if near_limit:
            delta_limit *= 0.5
        total_delta = clip(total_delta, -delta_limit, delta_limit)

        mcp_delta = total_delta * cfg.K_MCP
        pip_delta = total_delta * cfg.K_PIP

        target_angles = dict(current_angles)
        for joint_id in current_angles:
            mapped_finger = _JOINT_TO_FINGER.get(joint_id)
            if mapped_finger is not None and mapped_finger not in cfg.active_fingers:
                continue  # 非活跃手指的关节保持当前角度，不参与统一控制
            baseline = self._hold_joint_angle_baseline.get(joint_id, 0.0)
            min_a = baseline - math.radians(20.0)
            max_a = baseline + math.radians(20.0)
            if "MCP" in joint_id.name:
                target_angles[joint_id] = clip(current_angles[joint_id] + mcp_delta, min_a, max_a)
            elif "PIP" in joint_id.name:
                target_angles[joint_id] = clip(current_angles[joint_id] + pip_delta, min_a, max_a)

        return target_angles

    def _compute_next_torque(self) -> int:
        """计算下一周期输出力矩：受速度限制，易碎模式再按比例降低。"""
        cfg = self.config
        speed_limit = cfg.position_speed_limit
        if self.is_fragile_mode:
            speed_limit = int(speed_limit * cfg.fragile_speed_reduction)
        return min(speed_limit, cfg.position_torque_limit)

    def reset(self) -> None:
        """重置所有运行时状态（PID 积分、保持角度等）。"""
        self._finger_pid.clear()
        self._hold_joint_angles = {}
        self._hold_joint_angle_baseline = {}

    def set_baseline_angles(self, angles: dict[JointId, float]) -> None:
        """设置基准角度：后续微调以此为中心，限制在 ±20° 范围内。"""
        self._hold_joint_angles = dict(angles)
        self._hold_joint_angle_baseline = dict(angles)

    def _get_or_create_pid(self, finger: TactileSensorId) -> _FingerPidState:
        """获取指定手指的 PID 状态，不存在则惰性创建。"""
        if finger not in self._finger_pid:
            self._finger_pid[finger] = _FingerPidState()
        return self._finger_pid[finger]
