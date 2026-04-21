import math
from dataclasses import dataclass, field
from typing import Optional

from xiaoyao.dexhand import JointId


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
class AdaptiveGraspConfig:
    # 1.预抓取姿态（OPEN -> PRE_GRASP 阶段）
    # 预抓取关节目标角（单位：弧度）；为空时按预设自动生成。
    pre_grasp_pose: dict[JointId, float] = field(default_factory=dict)
    # 预抓取姿态预设名称。
    pre_grasp_preset: str = "three_finger_pinch"
    #=============================================================================
    # 2.CLOSING_TO_CONTACT 阶段基础参数
    # CLOSING_TO_CONTACT 阶段初始力矩（TORQUE 模式）。
    base_torque: int = 15
    # 接触判定阈值（所有传感器法向力绝对值之和）。
    contact_threshold_z: float = 1.5
    # 触觉滑动窗口长度（用于方差估计）。
    sliding_window_size: int = 10
    # 力矩步进增量（风险上升时用于收紧）。
    torque_adjust_step: int = 5
    # 力矩命令上限（同时受硬件 [-100,100] 限制）。
    max_torque: int = 80
    # OPEN/PRE_GRASP/CLOSING 等阶段超时（秒）。
    phase_timeout: float = 10.0
    # 离散控制周期 Ts（秒）。
    control_period_s: float = 0.01
    #=============================================================================
    # 触觉统计与阈值（v_0 / v_th）
    # 软硬度系数（0~1），用于推导默认阈值。
    stiffness: float = 0.5
    # 单指法向力上限 Fn,max；为空时由 stiffness 估计。
    max_normal_force_per_finger: Optional[float] = None
    # 滑移方差阈值 v_th；为空时由 stiffness 估计。
    variance_threshold: Optional[float] = None
    # 滑移方差基线 v_0。
    variance_baseline: float = 0.0
    # ADAPTIVE_HOLD 的 POSITION 闭环约束
    # ADAPTIVE_HOLD 阶段 POSITION 指令速度上限。
    position_speed_limit: int = 20
    # ADAPTIVE_HOLD 阶段 POSITION 指令力矩上限。
    position_torque_limit: int = 35
    # 单周期总角增量限幅 Delta theta_max（弧度）。
    delta_theta_limit: float = math.radians(2)
    # MCP/PIP 角增量分配系数，满足 K_MCP + K_PIP = 1
    # MCP 角增量分配系数（与 K_PIP 之和应为 1）。
    K_MCP: float = 0.5
    # PIP 角增量分配系数（与 K_MCP 之和应为 1）。
    K_PIP: float = 0.5
    #=============================================================================
    # RELEASE 阶段参数（超时触发与安全张开）
    # ADAPTIVE_HOLD 超时后自动进入 RELEASE 的时长（秒）。
    release_hold_time_s: float = 20.0
    # RELEASE 阶段安全张开速度。
    release_open_speed: int = 30
    # RELEASE 阶段安全张开力矩。
    release_open_torque: int = 30
    # RELEASE 到位等待超时（秒）。
    release_timeout_s: float = 5.0
    # RELEASE 到位角误差阈值（弧度）。
    theta_err_th: float = math.radians(2.0)
    # RELEASE 连续到位判定周期数。
    release_check_cycles: int = 5
    #=============================================================================
    # 前馈 + PID 控制律参数（u_k = u_ff + u_pid）
    # s_ref: 目标滑移风险；K_s/K_n: 前馈增益；K_p/K_i/K_d: PID 增益
    # 目标滑移风险水平 s_ref。
    s_ref: float = 0.25
    # 滑移前馈增益 K_s。
    K_s: float = 1.0
    # 法向超限抑制增益 K_n。
    K_n: float = 1.0
    # PID 比例增益 K_p。
    K_p: float = 0.0
    # PID 积分增益 K_i。
    K_i: float = 0.0
    # PID 微分增益 K_d。
    K_d: float = 0.0
    # 积分项限幅（防积分饱和）
    # PID 积分项下限（防积分饱和）。
    I_min: float = -1.0
    # PID 积分项上限（防积分饱和）。
    I_max: float = 1.0
    # 数值稳定项（防分母为零）
    # 数值稳定小量，避免分母为 0。
    epsilon: float = 1e-6
    # V2.0 新增参数
    # 安全系数 S_f，范围 [1.2, 2.0]，默认 1.5
    safety_factor: float = 1.5
    # 基础夹持力 F_base（N），默认 0.5
    base_holding_force: float = 0.5
    # 滑移防抖连续周期阈值
    slip_detect_debounce_cycles: int = 3
    # 易损模式速度降低比例
    fragile_speed_reduction: float = 0.7
    # 易损模式角增量/力矩步进降低比例
    fragile_step_reduction: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.stiffness <= 1.0:
            raise ValueError("stiffness must be in [0.0, 1.0]")
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

        if self.max_normal_force_per_finger is None:
            self.max_normal_force_per_finger = 0.1 + 2.9 * self.stiffness
        if self.variance_threshold is None:
            self.variance_threshold = 0.05 + 0.15 * self.stiffness

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
