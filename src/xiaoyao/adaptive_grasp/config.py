import math
from dataclasses import dataclass, field
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId
from xiaoyao.adaptive_grasp.object_profile import ObjectProfileRegistry


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
    "lily_pinch":{TactileSensorId.THUMB, TactileSensorId.MIDDLE_FINGER}
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
        JointId.FF_MCP: 10.0,
        JointId.FF_PIP: 30.0,
        JointId.THUMB_ROTATION: 0.0,
        JointId.THUMB_SWING: 90.0,
        JointId.THUMB_MCP: 3.0,
        JointId.THUMB_PIP: 0.0,
    },
    # 三指捏(食指-中指-大拇指)
    "three_finger_pinch": {
        JointId.LF_MCP: 0.0,
        JointId.LF_PIP: 0.0,
        JointId.RF_MCP: 0.0,
        JointId.RF_PIP: 0.0,
        JointId.MF_MCP: 49.0,
        JointId.MF_PIP: 10.0,
        JointId.FF_SWING: 0.0,
        JointId.FF_MCP: 41.0,
        JointId.FF_PIP: 14.0,
        JointId.THUMB_ROTATION: 0.0,
        JointId.THUMB_SWING: 85.0,
        JointId.THUMB_MCP: 4.0,
        JointId.THUMB_PIP: 4.0,
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
    # 兰花指
    "lily_pinch":{
        JointId.LF_MCP: 0.0,
        JointId.LF_PIP: 0.0,
        JointId.RF_MCP: 0.0,
        JointId.RF_PIP: 0.0,
        JointId.MF_MCP: 31.0,
        JointId.MF_PIP: 0.0,
        JointId.FF_SWING: 0.0,
        JointId.FF_MCP: 0.0,
        JointId.FF_PIP: 0.0,
        JointId.THUMB_ROTATION: 7.0,
        JointId.THUMB_SWING: 90.0,
        JointId.THUMB_MCP: 6.0,
        JointId.THUMB_PIP: 0.0,
    }
}
object = "balloon" # small small cone ballon
if object == "big":
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_MCP] = 0.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_PIP] = 0.0
elif object == "small":
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_MCP] = 3.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_PIP] = 0.0
elif object == "cone": #圆锥
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.FF_MCP] = 58.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.FF_PIP] = 0.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_ROTATION] = -2.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_SWING] = 90.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_MCP] = 0.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_PIP] = 0.0
elif object == "balloon":    
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.FF_MCP] = 25.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.FF_PIP] = 25.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_ROTATION] = 0.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_SWING] = 80.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_MCP] = 3.0
    _PRE_GRASP_PRESET_DEGREE["two_finger_pinch"][JointId.THUMB_PIP] = 5.0
elif object == "paper_cup":
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.FF_MCP] = 41.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.FF_PIP] = 14.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.MF_MCP] = 49.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.MF_PIP] = 10.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.THUMB_ROTATION] = 0.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.THUMB_SWING] = 85.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.THUMB_MCP] = 4.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.THUMB_PIP] = 4.0
elif object == "glass":
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.FF_MCP] = 35.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.FF_PIP] = 20.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.MF_MCP] = 45.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.MF_PIP] = 15.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.THUMB_ROTATION] = 0.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.THUMB_SWING] = 90.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.THUMB_MCP] = 11.0
    _PRE_GRASP_PRESET_DEGREE["three_finger_pinch"][JointId.THUMB_PIP] = 6.0

@dataclass
class PerFingerPidConfig:
    """单指独立 PID 参数配置；字段为 None 时回退到全局 AdaptiveGraspConfig 参数。"""
    K_p: Optional[float] = None
    K_i: Optional[float] = None
    K_d: Optional[float] = None
    I_min: Optional[float] = None
    I_max: Optional[float] = None


def _validate(
    name: str,
    val,
    *,
    greater_than=None,
    greater_equal=None,
    less_than=None,
    less_equal=None,
) -> None:
    """通用数值范围验证辅助函数。

    greater_than: 必须严格大于此值 (>)
    greater_equal: 必须大于等于此值 (>=)
    less_than: 必须严格小于此值 (<)
    less_equal: 必须小于等于此值 (<=)
    """
    if greater_than is not None and val <= greater_than:
        raise ValueError(f"{name} must be > {greater_than}")
    if greater_equal is not None and val < greater_equal:
        raise ValueError(f"{name} must be >= {greater_equal}")
    if less_than is not None and val >= less_than:
        raise ValueError(f"{name} must be < {less_than}")
    if less_equal is not None and val > less_equal:
        raise ValueError(f"{name} must be <= {less_equal}")


@dataclass
class AdaptiveGraspConfig:
    # 1.预抓取姿态（OPEN -> PRE_GRASP 阶段）
    pre_grasp_pose: dict[JointId, float] = field(default_factory=dict) # 预抓取关节目标角（单位：弧度）；为空时按预设自动生成。
    # 材质库配置：材质数据定义在 object_profile.py，config 只保存默认材质名。
    default_object: str = "balloon" # 材质名称获取完整属性。
    #预抓取姿态设定：
    """
    two_finger_pinch: 两指捏(食指-大拇指)
    three_finger_pinch: 三指捏(食指-中指-大拇指)
    four_finger_grasp: 四指握
    five_finger_grasp: 五指握
    """
    pre_grasp_preset: str = "two_finger_pinch" # 预抓取姿态预设名称。
    active_fingers: set[TactileSensorId] = field(default_factory=set) # 抓取时的手指集合；为空时按预设自动推导。
    per_finger_pid: dict[TactileSensorId, PerFingerPidConfig] = field(default_factory=dict) # 单指独立 PID 参数；未配置的手指回退到 position_hold_* 参数。
    #=============================================================================
    # 2.闭合接触阶段基础参数
    base_torque: int = 30 # 默认基础力矩，保留给兼容逻辑使用。
    phase_closing_torque: int = 30 # 闭合找接触阶段下发的力矩（力矩模式）。
    contact_threshold_z: float = 0.2 # 接触判定阈值（所有传感器法向力绝对值之和）。
    sliding_window_size: int = 10 # 触觉滑动窗口长度（用于方差估计）。
    torque_adjust_step: int = 5 # 力矩步进增量。
    max_torque: int = 80 # 力矩命令上限（同时受硬件 [-100,100] 限制）。
    phase_timeout: float = 10.0 # 张开/预抓取/闭合等阶段超时（秒）。
    control_period_s: float = 0.02 # 离散控制周期 Ts（秒），（优先使用函数传入的dt，其次使用前后帧的时间差，最后使用这个默认值）
    closing_period_s: float = 0.2 # 闭合接触阶段每次力矩指令后的休眠周期（秒）。
    #=============================================================================
    # 触觉统计与阈值（v_0 / v_th）
    max_normal_force_per_finger: float = 25.0 # 单指法向力上限 Fn,max N，触觉传感器最大量程；
    variance_threshold: float = 0.003    # 滑移方差阈值 v_th（需标定）；
    variance_baseline: float = 0.00001 # 滑移方差基线 v_0（需标定）。
    # 自适应保持阶段位置闭环控制/力矩闭环控制公用参数
    adaptive_hold_command_mode: str = "position" # "position" or "torque".
    force_ref_slip_warning_threshold: float = 0.40
    force_ref_stable_threshold: float = 0.20
    force_ref_slip_gain_n_per_s: float = 0.20
    force_ref_max_rise_step_n: float = 0.02
    force_ref_confirmed_boost_n: float = 0.05
    force_ref_decay_rate_n_per_s: float = 0.02
    force_ref_stable_decay_delay_s: float = 1.0
    force_ref_min_contact_ratio: float = 0.15

    # 自适应保持阶段的位置闭环控制
    position_speed_limit: int = 15 # 自适应保持阶段位置指令速度限幅。
    position_torque_limit: int = 15 # 自适应保持阶段位置指令力矩限幅。
    delta_theta_limit: float = math.radians(2) # 单周期总角增量限幅（弧度）。
    # MCP/PIP 角增量分配系数，满足 K_MCP + K_PIP = 1
    K_MCP: float = 0.1 # MCP 角增量分配系数
    K_PIP: float = 0.5 # PIP 角增量分配系数
    position_hold_K_p: float = 5.0
    position_hold_K_i: float = 0.2
    position_hold_K_d: float = 0.0
    position_hold_I_min: float = -2.0
    position_hold_I_max: float = 2.0
    K_n: float = 1.0 # Normal-force over-limit suppression gain K_n.
    
    #自适应保持阶段的力矩闭环控制
    adaptive_hold_torque: int = 5 # Torque sent to active MCP/PIP joints in torque hold mode.
    force_ref_margin_n: float = 0.10
    torque_hold_K_p: float = 15.0
    torque_hold_K_i: float = 0.5
    torque_hold_K_d: float = 0.0
    torque_hold_I_min: float = -1.0
    torque_hold_I_max: float = 1.0
    #=============================================================================
    # 释放阶段参数（超时触发与安全张开）
    release_hold_time_s: float = 20.0 # 自适应保持超时后自动进入释放的时长（秒）。
    release_open_speed: int = 50 # 释放阶段安全张开速度。
    release_open_torque: int = 50 # 释放阶段安全张开力矩。
    release_timeout_s: float = 5.0 # 释放到位等待超时（秒）。
    #=============================================================================
    # 切向力相关参数
    # 三指标融合权重，满足 α + β + γ = 1
    variance_weight: float = 0.34
    direction_weight: float = 0.33
    friction_weight: float = 0.33
    #==============================================================================
    # 数值稳定项（防分母为零）
    epsilon: float = 1e-6 # 数值稳定小量，避免分母为 0。
    # 新增参数
    slip_detect_debounce_cycles: int = 3 # 滑移防抖连续周期阈值
    fragile_torque_reduction: float = 0.8 # 易损模式力矩降低比例
    fragile_step_reduction: float = 0.5 # 易损模式角增量/力矩步进降低比例

    default_friction_coeff: float = 0.7 # 默认摩擦系数，物体参数库未提供时回退使用
    enable_fault_release_fallback: bool = True # 异常降级使能：安全监控返回故障时是否执行释放安全张开（True）或直接进入错误（False）
    enable_visualization: bool = True # 是否启用实时触觉数据可视化窗口（ADAPTIVE_HOLD 阶段）
    visualization_backend: str = "TkAgg" # matplotlib 后端（如 TkAgg、Agg、Qt5Agg 等）
    #=============================================================================
    # 闭合阶段运动停滞检测（触觉阈值不足时的备用接触判定）
    closing_stall_angle_threshold: float = math.radians(0.5) # 单周期关节停滞角度阈值（弧度）
    closing_stall_cycles: int = 5 # 连续停滞周期数才判定为接触



    def __post_init__(self) -> None:
        # 参数校验
        _validate("sliding_window_size", self.sliding_window_size, greater_equal=3)
        _validate("control_period_s", self.control_period_s, greater_than=0)
        _validate("closing_period_s", self.closing_period_s, greater_than=0)
        _validate("phase_closing_torque", self.phase_closing_torque, greater_equal=-100, less_equal=100)
        _validate("max_torque", self.max_torque, greater_than=0)
        _validate("phase_timeout", self.phase_timeout, greater_than=0)
        _validate("torque_adjust_step", self.torque_adjust_step, greater_than=0)
        _validate("variance_baseline", self.variance_baseline, greater_equal=0)
        _validate("adaptive_hold_torque", self.adaptive_hold_torque, greater_equal=-100, less_equal=100)
        _validate("force_ref_margin_n", self.force_ref_margin_n, greater_equal=0.0)
        _validate("force_ref_slip_warning_threshold", self.force_ref_slip_warning_threshold, greater_equal=0.0, less_equal=1.0)
        _validate("force_ref_stable_threshold", self.force_ref_stable_threshold, greater_equal=0.0, less_equal=1.0)
        _validate("force_ref_slip_gain_n_per_s", self.force_ref_slip_gain_n_per_s, greater_equal=0.0)
        _validate("force_ref_max_rise_step_n", self.force_ref_max_rise_step_n, greater_equal=0.0)
        _validate("force_ref_confirmed_boost_n", self.force_ref_confirmed_boost_n, greater_equal=0.0)
        _validate("force_ref_decay_rate_n_per_s", self.force_ref_decay_rate_n_per_s, greater_equal=0.0)
        _validate("force_ref_stable_decay_delay_s", self.force_ref_stable_decay_delay_s, greater_equal=0.0)
        _validate("force_ref_min_contact_ratio", self.force_ref_min_contact_ratio, greater_equal=0.0, less_equal=1.0)
        if self.force_ref_min_contact_ratio * len(self.active_fingers) > 1.0:
            raise ValueError("force_ref_min_contact_ratio * active_finger_count must be <= 1.0")
        _validate("torque_hold_K_p", self.torque_hold_K_p, greater_equal=0.0)
        _validate("torque_hold_K_i", self.torque_hold_K_i, greater_equal=0.0)
        _validate("torque_hold_K_d", self.torque_hold_K_d, greater_equal=0.0)
        if self.torque_hold_I_min > self.torque_hold_I_max:
            raise ValueError("torque_hold_I_min must be <= torque_hold_I_max")
        _validate("position_speed_limit", self.position_speed_limit, greater_equal=0, less_equal=100)
        _validate("position_torque_limit", self.position_torque_limit, greater_equal=0, less_equal=100)
        _validate("delta_theta_limit", self.delta_theta_limit, greater_than=0)
        _validate("K_MCP", self.K_MCP, greater_equal=0.0, less_equal=1.0)
        _validate("K_PIP", self.K_PIP, greater_equal=0.0, less_equal=1.0)
        _validate("release_hold_time_s", self.release_hold_time_s, greater_than=0)
        _validate("release_open_speed", self.release_open_speed, greater_equal=0, less_equal=100)
        _validate("release_open_torque", self.release_open_torque, greater_equal=0, less_equal=100)
        _validate("release_timeout_s", self.release_timeout_s, greater_than=0)
        _validate("K_n", self.K_n, greater_equal=0)
        _validate("position_hold_K_p", self.position_hold_K_p, greater_equal=0)
        _validate("position_hold_K_i", self.position_hold_K_i, greater_equal=0)
        _validate("position_hold_K_d", self.position_hold_K_d, greater_equal=0)
        _validate("epsilon", self.epsilon, greater_than=0)
        _validate("slip_detect_debounce_cycles", self.slip_detect_debounce_cycles, greater_than=0)
        _validate("fragile_step_reduction", self.fragile_step_reduction, greater_than=0.0, less_equal=1.0)
        _validate("variance_weight", self.variance_weight, greater_equal=0.0, less_equal=1.0)
        _validate("direction_weight", self.direction_weight, greater_equal=0.0, less_equal=1.0)
        _validate("friction_weight", self.friction_weight, greater_equal=0.0, less_equal=1.0)
        _validate("default_friction_coeff", self.default_friction_coeff, greater_than=0)
        _validate("max_normal_force_per_finger", self.max_normal_force_per_finger, greater_than=0)
        _validate("variance_threshold", self.variance_threshold, greater_equal=0)
        _validate("closing_stall_angle_threshold", self.closing_stall_angle_threshold, greater_than=0)
        _validate("closing_stall_cycles", self.closing_stall_cycles, greater_than=0)
        if not math.isclose(self.variance_weight + self.direction_weight + self.friction_weight, 1.0, abs_tol=1e-6):
            raise ValueError("variance_weight + direction_weight + friction_weight must equal 1.0")
        # if not math.isclose(self.K_MCP + self.K_PIP, 1.0, abs_tol=1e-6):
        #     raise ValueError("K_MCP + K_PIP must equal 1.0")
        if self.adaptive_hold_command_mode not in {"position", "torque"}:
            raise ValueError('adaptive_hold_command_mode must be "position" or "torque"')
        if self.variance_baseline >= self.variance_threshold:
            raise ValueError("variance_baseline must be < variance_threshold")
        if self.position_hold_I_min > self.position_hold_I_max:
            raise ValueError("position_hold_I_min must be <= position_hold_I_max")
        #=============================================================================
        if self.pre_grasp_pose:
            filtered = self._filter_passive_dip_joints(self.pre_grasp_pose)
            self.pre_grasp_pose = filtered if filtered else self._build_pre_grasp_pose_from_preset()
        else:
            self.pre_grasp_pose = self._build_pre_grasp_pose_from_preset()
        
        # 若未显式指定活跃手指，按预设自动推导；若预设未知则默认全开。
        if not self.active_fingers:
            self.active_fingers = set(_PRESET_ACTIVE_FINGERS.get(self.pre_grasp_preset, set(TactileSensorId)))

        # 验证 default_object 材质存在
        if ObjectProfileRegistry.get(self.default_object) is None:
            supported = ", ".join(sorted(ObjectProfileRegistry.list_all()))
            raise ValueError(f"default_object must be one of: {supported}")

    def _build_pre_grasp_pose_from_preset(self) -> dict[JointId, float]:
        if self.pre_grasp_preset not in _PRE_GRASP_PRESET_DEGREE:
            supported = ", ".join(sorted(_PRE_GRASP_PRESET_DEGREE.keys()))
            raise ValueError(f"pre_grasp_preset 必须是以下之一: {supported}")

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
