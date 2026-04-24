import math
from dataclasses import dataclass, field
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId


_PASSIVE_DIP_JOINTS = {
    JointId.THUMB_DIP,
    JointId.FF_DIP,
    JointId.MF_DIP,
    JointId.RF_DIP,
    JointId.LF_DIP,
}

_ACTIVE_PRE_GRASP_JOINTS = (
    JointId.LF_MCP,
    JointId.LF_PIP,
    JointId.RF_MCP,
    JointId.RF_PIP,
    JointId.MF_MCP,
    JointId.MF_PIP,
    JointId.FF_SWING,
    JointId.FF_MCP,
    JointId.FF_PIP,
    JointId.THUMB_ROTATION,
    JointId.THUMB_SWING,
    JointId.THUMB_MCP,
    JointId.THUMB_PIP,
)

# 各预设对应的活跃手指（触觉传感器），用于过滤闭环控制中不参与的手指。
_PRESET_ACTIVE_FINGERS: dict[str, set[TactileSensorId]] = {
    "two_finger_pinch": {TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
    "three_finger_pinch": {TactileSensorId.THUMB, TactileSensorId.FOREFINGER, TactileSensorId.MIDDLE_FINGER},
    "four_finger_grasp": {TactileSensorId.THUMB, TactileSensorId.FOREFINGER, TactileSensorId.MIDDLE_FINGER, TactileSensorId.RING_FINGER},
    "five_finger_grasp": {TactileSensorId.THUMB, TactileSensorId.FOREFINGER, TactileSensorId.MIDDLE_FINGER, TactileSensorId.RING_FINGER, TactileSensorId.LITTLE_FINGER},
}

_PRE_GRASP_PRESET_DEGREE = {
    # 两指捏(食指-大拇指)
    "two_finger_pinch": {
        JointId.LF_MCP: 0.0,
        JointId.LF_PIP: 0.0,
        JointId.RF_MCP: 0.0,
        JointId.RF_PIP: 0.0,
        JointId.MF_MCP: 0.0,
        JointId.MF_PIP: 0.0,
        JointId.FF_SWING: 0.0,
        JointId.FF_MCP: 45.0,
        JointId.FF_PIP: 45.0,
        JointId.THUMB_ROTATION: 2.0,
        JointId.THUMB_SWING: 46.0,
        JointId.THUMB_MCP: 22.0,
        JointId.THUMB_PIP: 20.0,
    },
    # 三指捏(食指-中指-大拇指)
    "three_finger_pinch": {
        JointId.LF_MCP: 0.0,
        JointId.LF_PIP: 0.0,
        JointId.RF_MCP: 0.0,
        JointId.RF_PIP: 0.0,
        JointId.MF_MCP: 72.0,
        JointId.MF_PIP: 0.0,
        JointId.FF_SWING: 0.0,
        JointId.FF_MCP: 63.0,
        JointId.FF_PIP: 0.0,
        JointId.THUMB_ROTATION: 0.0,
        JointId.THUMB_SWING: 90.0,
        JointId.THUMB_MCP: 0.0,
        JointId.THUMB_PIP: 11.0,
    },
    # 四指握
    "four_finger_grasp": {
        JointId.LF_MCP: 0.0,
        JointId.LF_PIP: 0.0,
        JointId.RF_MCP: 60.0,
        JointId.RF_PIP: 25.0,
        JointId.MF_MCP: 53.0,
        JointId.MF_PIP: 30.0,
        JointId.FF_SWING: 0.0,
        JointId.FF_MCP: 45.0,
        JointId.FF_PIP: 35.0,
        JointId.THUMB_ROTATION: 2.0,
        JointId.THUMB_SWING: 60.0,
        JointId.THUMB_MCP: 2.0,
        JointId.THUMB_PIP: 21.0,
    },
    # 五指握
    "five_finger_grasp": {
        JointId.LF_MCP: 45.0,
        JointId.LF_PIP: 30.0,
        JointId.RF_MCP: 60.0,
        JointId.RF_PIP: 25.0,
        JointId.MF_MCP: 53.0,
        JointId.MF_PIP: 30.0,
        JointId.FF_SWING: 0.0,
        JointId.FF_MCP: 45.0,
        JointId.FF_PIP: 35.0,
        JointId.THUMB_ROTATION: 2.0,
        JointId.THUMB_SWING: 60.0,
        JointId.THUMB_MCP: 2.0,
        JointId.THUMB_PIP: 21.0,
    },
}


@dataclass
class PerFingerPidConfig:
    """单指独立 PID 参数配置；字段为 None 时回退到全局 AdaptiveGraspConfig 参数。"""
    K_p: Optional[float] = None
    K_i: Optional[float] = None
    K_d: Optional[float] = None
    I_min: Optional[float] = None
    I_max: Optional[float] = None


@dataclass
class AdaptiveGraspConfig:
    # 1.预抓取姿态（OPEN -> PRE_GRASP 阶段）
    pre_grasp_pose: dict[JointId, float] = field(default_factory=dict) # 预抓取关节目标角（单位：弧度）；为空时按预设自动生成。
    pre_grasp_preset: str = "two_finger_pinch" # 预抓取姿态预设名称。
    active_fingers: set[TactileSensorId] = field(default_factory=set) # 参与闭环控制的手指集合；为空时按 preset 自动推导。
    per_finger_pid: dict[TactileSensorId, PerFingerPidConfig] = field(default_factory=dict) # 单指独立 PID 参数；未配置的手指回退到全局 K_p/K_i/K_d。
    #=============================================================================
    # 2.CLOSING_TO_CONTACT 阶段基础参数
    base_torque: int = 15 # CLOSING_TO_CONTACT 阶段初始力矩（TORQUE 模式）。
    contact_threshold_z: float = 1.5 # 接触判定阈值（所有传感器法向力绝对值之和）。
    sliding_window_size: int = 10 # 触觉滑动窗口长度（用于方差估计）。
    torque_adjust_step: int = 5 # 力矩步进增量。
    max_torque: int = 80 # 力矩命令上限（同时受硬件 [-100,100] 限制）。
    phase_timeout: float = 10.0 # OPEN/PRE_GRASP/CLOSING 等阶段超时（秒）。
    control_period_s: float = 0.02 # 离散控制周期 Ts（秒），（优先使用函数传入的dt，其次使用前后帧的时间差，最后使用这个默认值）
    #=============================================================================
    # 触觉统计与阈值（v_0 / v_th）
    max_normal_force_per_finger: float = 25.0 # 单指法向力上限 Fn,max N，触觉传感器最大量程；
    variance_threshold: float = 0.003    # 滑移方差阈值 v_th（需标定）；
    variance_baseline: float = 0.00001 # 滑移方差基线 v_0（需标定）。

    # ADAPTIVE_HOLD 的 POSITION 闭环约束
    position_speed_limit: int = 15 # ADAPTIVE_HOLD 阶段 POSITION 指令速度限幅。
    position_torque_limit: int = 15 # ADAPTIVE_HOLD 阶段 POSITION 指令力矩限幅。
    delta_theta_limit: float = math.radians(4) # 单周期总角增量限幅 Delta theta_max（弧度）。
    # MCP/PIP 角增量分配系数，满足 K_MCP + K_PIP = 1
    K_MCP: float = 0.5 # MCP 角增量分配系数
    K_PIP: float = 0.5 # PIP 角增量分配系数
    #=============================================================================
    # RELEASE 阶段参数（超时触发与安全张开）
    release_hold_time_s: float = 20.0 # ADAPTIVE_HOLD 超时后自动进入 RELEASE 的时长（秒）。
    release_open_speed: int = 30 # RELEASE 阶段安全张开速度。
    release_open_torque: int = 30 # RELEASE 阶段安全张开力矩。
    release_timeout_s: float = 5.0 # RELEASE 到位等待超时（秒）。
    theta_err_th: float = math.radians(2.0) # RELEASE 到位角误差阈值（弧度）。
    release_check_cycles: int = 3 # RELEASE 连续到位判定周期数。
    #=============================================================================
    # 前馈 + PID 控制律参数（u_k = u_ff + u_pid）
    # s_ref: 目标滑移风险；K_s/K_n: 前馈增益；K_p/K_i/K_d: PID 增益
    s_ref: float = 0.25 # 目标滑移风险水平 s_ref。
    K_s: float = 1.0 # 滑移前馈增益 K_s。
    K_n: float = 1.0 # 法向超限抑制增益 K_n。
    K_p: float = 0.5 # PID 比例增益 K_p。
    K_i: float = 0.01 # PID 积分增益 K_i。
    K_d: float = 0.005 # PID 微分增益 K_d。
    # 积分项限幅（防积分饱和）
    I_min: float = -1.0 # PID 积分项下限（防积分饱和）。
    I_max: float = 1.0 # PID 积分项上限（防积分饱和）。
    # 数值稳定项（防分母为零）
    epsilon: float = 1e-6 # 数值稳定小量，避免分母为 0。
    # 新增参数
    safety_factor: float = 1.5 # 安全系数 S_f，范围 [1.2, 2.0]，默认 1.5
    base_holding_force: float = 0.5 # 基础夹持力 F_base（N），默认 0.5
    slip_detect_debounce_cycles: int = 3 # 滑移防抖连续周期阈值
    fragile_speed_reduction: float = 0.8 # 易损模式速度降低比例
    fragile_torque_reduction: float = 0.8 # 易损模式力矩降低比例
    fragile_step_reduction: float = 0.5 # 易损模式角增量/力矩步进降低比例
    # 三指标融合权重，满足 α + β + γ = 1
    variance_weight: float = 0.5
    direction_weight: float = 0.3
    friction_weight: float = 0.2
    default_friction_coeff: float = 0.7 # 默认摩擦系数，物体参数库未提供时 fallback
    enable_fault_release_fallback: bool = True # 异常降级使能：SafetyMonitor 返回 FAULT 时是否走 RELEASE 安全张开（True）或直接进入 ERROR（False）

    def __post_init__(self) -> None:
        if self.sliding_window_size < 3:
            raise ValueError("sliding_window_size must be >= 3")
        if self.control_period_s <= 0:
            raise ValueError("control_period_s must be > 0")
        if self.max_torque <= 0:
            raise ValueError("max_torque must be > 0")
        if self.phase_timeout <= 0:
            raise ValueError("phase_timeout must be > 0")
        if self.torque_adjust_step <= 0:
            raise ValueError("torque_adjust_step must be > 0")
        if self.variance_baseline < 0:
            raise ValueError("variance_baseline must be >= 0")
        if not 0 <= self.position_speed_limit <= 100:
            raise ValueError("position_speed_limit must be in [0, 100]")
        if not 0 <= self.position_torque_limit <= 100:
            raise ValueError("position_torque_limit must be in [0, 100]")
        if self.delta_theta_limit <= 0:
            raise ValueError("delta_theta_limit must be > 0")
        if not 0.0 <= self.K_MCP <= 1.0:
            raise ValueError("K_MCP must be in [0.0, 1.0]")
        if not 0.0 <= self.K_PIP <= 1.0:
            raise ValueError("K_PIP must be in [0.0, 1.0]")
        if not math.isclose(self.K_MCP + self.K_PIP, 1.0, abs_tol=1e-6):
            raise ValueError("K_MCP + K_PIP must equal 1.0")
        if self.release_hold_time_s <= 0:
            raise ValueError("release_hold_time_s must be > 0")
        if not 0 <= self.release_open_speed <= 100:
            raise ValueError("release_open_speed must be in [0, 100]")
        if not 0 <= self.release_open_torque <= 100:
            raise ValueError("release_open_torque must be in [0, 100]")
        if self.release_timeout_s <= 0:
            raise ValueError("release_timeout_s must be > 0")
        if self.theta_err_th <= 0:
            raise ValueError("theta_err_th must be > 0")
        if self.release_check_cycles <= 0:
            raise ValueError("release_check_cycles must be > 0")
        if not 0.0 <= self.s_ref <= 1.0:
            raise ValueError("s_ref must be in [0.0, 1.0]")
        if self.K_s < 0 or self.K_n < 0 or self.K_p < 0 or self.K_i < 0 or self.K_d < 0:
            raise ValueError("K_s/K_n/K_p/K_i/K_d must be >= 0")
        if self.I_min > self.I_max:
            raise ValueError("I_min must be <= I_max")
        if self.epsilon <= 0:
            raise ValueError("epsilon must be > 0")
        if not 1.2 <= self.safety_factor <= 2.0:
            raise ValueError("safety_factor must be in [1.2, 2.0]")
        if self.base_holding_force < 0:
            raise ValueError("base_holding_force must be >= 0")
        if self.slip_detect_debounce_cycles <= 0:
            raise ValueError("slip_detect_debounce_cycles must be > 0")
        if not 0.0 < self.fragile_speed_reduction <= 1.0:
            raise ValueError("fragile_speed_reduction must be in (0.0, 1.0]")
        if not 0.0 < self.fragile_step_reduction <= 1.0:
            raise ValueError("fragile_step_reduction must be in (0.0, 1.0]")
        if not 0.0 <= self.variance_weight <= 1.0:
            raise ValueError("variance_weight must be in [0.0, 1.0]")
        if not 0.0 <= self.direction_weight <= 1.0:
            raise ValueError("direction_weight must be in [0.0, 1.0]")
        if not 0.0 <= self.friction_weight <= 1.0:
            raise ValueError("friction_weight must be in [0.0, 1.0]")
        if not math.isclose(self.variance_weight + self.direction_weight + self.friction_weight, 1.0, abs_tol=1e-6):
            raise ValueError("variance_weight + direction_weight + friction_weight must equal 1.0")
        if self.default_friction_coeff <= 0:
            raise ValueError("default_friction_coeff must be > 0")
        if self.max_normal_force_per_finger <= 0:
            raise ValueError("max_normal_force_per_finger must be > 0")
        if self.variance_threshold < 0:
            raise ValueError("variance_threshold must be >= 0")
        if self.variance_baseline >= self.variance_threshold:
            raise ValueError("variance_baseline must be < variance_threshold")

        if self.pre_grasp_pose:
            filtered = self._filter_passive_dip_joints(self.pre_grasp_pose)
            self.pre_grasp_pose = filtered if filtered else self._build_pre_grasp_pose_from_preset()
        else:
            self.pre_grasp_pose = self._build_pre_grasp_pose_from_preset()

        # 若未显式指定活跃手指，按 preset 自动推导；若 preset 未知则默认全开。
        if not self.active_fingers:
            self.active_fingers = set(_PRESET_ACTIVE_FINGERS.get(self.pre_grasp_preset, set(TactileSensorId)))

    def _build_pre_grasp_pose_from_preset(self) -> dict[JointId, float]:
        if self.pre_grasp_preset not in _PRE_GRASP_PRESET_DEGREE:
            supported = ", ".join(sorted(_PRE_GRASP_PRESET_DEGREE.keys()))
            raise ValueError(f"pre_grasp_preset must be one of: {supported}")

        # 预设表按角度维护，统一在这里转换成弧度，避免单位混用。
        degrees_map = _PRE_GRASP_PRESET_DEGREE[self.pre_grasp_preset]
        pose: dict[JointId, float] = {}
        for joint_id in _ACTIVE_PRE_GRASP_JOINTS:
            pose[joint_id] = math.radians(degrees_map.get(joint_id, 0.0))
        return pose

    @staticmethod
    def _filter_passive_dip_joints(
        pose: dict[JointId, float],
    ) -> dict[JointId, float]:
        return {
            joint_id: angle
            for joint_id, angle in pose.items()
            if joint_id not in _PASSIVE_DIP_JOINTS
        }
