import math
from dataclasses import dataclass, field
from typing import Optional

from xiaoyao.adaptive_grasp.object_profile import ObjectProfileRegistry
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

_PRESET_ACTIVE_FINGERS: dict[str, set[TactileSensorId]] = {
    "two_finger_pinch": {TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
    "three_finger_pinch": {
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
    },
    "three_finger_grasp": {
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
    },
    "four_finger_grasp": {
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
        TactileSensorId.RING_FINGER,
    },
    "five_finger_grasp": set(TactileSensorId),
    "lily_pinch": {TactileSensorId.THUMB, TactileSensorId.MIDDLE_FINGER},
    "small_pinch": {TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
    "smooth_ball": {TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
    "balloon_pinch": {TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
    "paper_cup_pinch": {
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
    },
    "glass_pinch": {
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
    },
    "plastic_three_pinch":{
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
    },
    "paper_cup_grasp":{
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
        TactileSensorId.RING_FINGER,
        TactileSensorId.LITTLE_FINGER
    },
    "paper_cup_two_finger_grasp":{
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
    }
}


def _pose_degrees(
    *,
    lf_mcp: float = 0.0,
    lf_pip: float = 0.0,
    rf_mcp: float = 0.0,
    rf_pip: float = 0.0,
    mf_mcp: float = 0.0,
    mf_pip: float = 0.0,
    ff_swing: float = 0.0,
    ff_mcp: float = 0.0,
    ff_pip: float = 0.0,
    thumb_rotation: float = 0.0,
    thumb_swing: float = 90.0,
    thumb_mcp: float = 0.0,
    thumb_pip: float = 0.0,
) -> dict[JointId, float]:
    return {
        JointId.LF_MCP: lf_mcp,
        JointId.LF_PIP: lf_pip,
        JointId.RF_MCP: rf_mcp,
        JointId.RF_PIP: rf_pip,
        JointId.MF_MCP: mf_mcp,
        JointId.MF_PIP: mf_pip,
        JointId.FF_SWING: ff_swing,
        JointId.FF_MCP: ff_mcp,
        JointId.FF_PIP: ff_pip,
        JointId.THUMB_ROTATION: thumb_rotation,
        JointId.THUMB_SWING: thumb_swing,
        JointId.THUMB_MCP: thumb_mcp,
        JointId.THUMB_PIP: thumb_pip,
    }


_PRE_GRASP_PRESET_DEGREE = {
    "two_finger_pinch": _pose_degrees(
        ff_mcp=60.0,
        ff_pip=20.0,
        thumb_swing=80.0,
        thumb_mcp=0.0,
        thumb_pip=0.0,
    ),
    "three_finger_pinch": _pose_degrees(
        mf_mcp=50.0,
        mf_pip=10.0,
        ff_mcp=42.0,
        ff_pip=10.0,
        ff_swing=5.0,
        thumb_swing=80.0,
        thumb_pip=10,
        thumb_mcp=20.0,
        thumb_rotation=5.0,
    ),
    "three_finger_grasp": _pose_degrees(
        mf_mcp=36.0,
        mf_pip=35.0,
        ff_mcp=28.0,
        ff_pip=41.0,
        thumb_swing=80.0,
        thumb_pip=28,
        thumb_mcp=10.0,
    ),
    "four_finger_grasp": _pose_degrees(
        rf_mcp=60.0,
        rf_pip=25.0,
        mf_mcp=53.0,
        mf_pip=30.0,
        ff_mcp=45.0,
        ff_pip=35.0,
        thumb_rotation=2.0,
        thumb_swing=60.0,
        thumb_mcp=2.0,
        thumb_pip=21.0,
    ),
    "five_finger_grasp": _pose_degrees(
        lf_mcp=45.0,
        lf_pip=30.0,
        rf_mcp=60.0,
        rf_pip=25.0,
        mf_mcp=53.0,
        mf_pip=30.0,
        ff_mcp=45.0,
        ff_pip=35.0,
        thumb_rotation=2.0,
        thumb_swing=60.0,
        thumb_mcp=2.0,
        thumb_pip=21.0,
    ),
    "lily_pinch": _pose_degrees(
        mf_mcp=31.0,
        thumb_rotation=7.0,
        thumb_mcp=6.0,
    ),
    "small_pinch": _pose_degrees(
        thumb_swing=84,
        thumb_pip=10,
        ff_mcp=45.0,
        ff_pip=22.0,
        thumb_mcp=3.0,
    ),
    "smooth_ball": _pose_degrees(
        ff_mcp=60.0,
        ff_pip=10,
        thumb_swing=80,
        thumb_mcp=15,
    ),
    "balloon_pinch": _pose_degrees(
        ff_mcp=25.0,
        ff_pip=25.0,
        thumb_swing=80.0,
        thumb_mcp=3.0,
        thumb_pip=5.0,
    ),
    "paper_cup_pinch": _pose_degrees(
        mf_mcp=49.0,
        mf_pip=10.0,
        ff_mcp=41.0,
        ff_pip=14.0,
        thumb_swing=85.0,
        thumb_mcp=4.0,
        thumb_pip=4.0,
    ),
    "glass_pinch": _pose_degrees(
        mf_mcp=45.0,
        mf_pip=15.0,
        ff_mcp=35.0,
        ff_pip=20.0,
        thumb_mcp=11.0,
        thumb_pip=6.0,
    ),
    "plastic_three_pinch":_pose_degrees(
        thumb_mcp=16,
        thumb_rotation=2,
        thumb_swing=71,
        ff_pip=20,
        ff_mcp=29,
        ff_swing=5,
        mf_pip=18,
        mf_mcp=40
    ),
    "paper_cup_grasp":_pose_degrees(
        thumb_mcp=15,
        thumb_pip=20,
        thumb_swing=80,
        thumb_rotation=4,
        ff_pip=45,
        ff_mcp=25,
        mf_pip=40,
        mf_mcp=40,
        rf_pip=40,
        rf_mcp=40,
        lf_pip=35,
        lf_mcp=35,
    ),
    "paper_cup_two_finger_grasp":_pose_degrees(
        thumb_swing=75,
        thumb_pip=28,
        ff_pip=50,
        ff_mcp=20
    )
}

_OBJECT_PRE_GRASP_PRESET = {
    "balloon": "balloon_pinch",
    "paper_cup": "paper_cup_pinch",
    "glass": "glass_pinch",
}


@dataclass
class PerFingerPidConfig:
    """Optional per-finger overrides for the position-hold PID."""

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
    """Configuration entry point for the adaptive grasp SDK."""

    # Object and pre-grasp pose.
    default_object: str = "balloon"
    pre_grasp_preset: Optional[str] = None
    pre_grasp_pose: dict[JointId, float] = field(default_factory=dict)
    active_fingers: set[TactileSensorId] = field(default_factory=set)
    per_finger_pid: dict[TactileSensorId, PerFingerPidConfig] = field(default_factory=dict)

    # Open, pre-grasp, and closing-to-contact phases.
    open_speed: int = 50
    open_torque: int = 50
    open_wait_s: float = 3.0
    pre_grasp_speed: int = 50
    pre_grasp_torque: int = 50
    pre_grasp_wait_s: float = 5.0
    closing_total_contact_threshold_n: float = 0.2
    finger_touch_threshold_n: float = 0.1
    max_torque: int = 80
    thumb_aux_torque: int = 3
    phase_timeout: float = 10.0
    control_period_s: float = 0.02
    closing_period_s: float = 0.2
    closing_stall_angle_threshold: float = math.radians(0.5)
    closing_stall_cycles: int = 5

    # Tactile subscription timing. Keep these aligned unless you intentionally
    # want to dispatch cached frames faster/slower than hardware reads.
    tactile_sensor_update_period_s: float = 0.02 #多久从 EtherCAT client 读取一次最新数据
    tactile_dispatch_period_s: float = 0.02 #多久把当前缓存的数据回调给订阅者

    # Tactile slip analysis.
    sliding_window_size: int = 10
    max_normal_force_per_finger: float = 25.0
    variance_threshold: float = 0.003
    variance_baseline: float = 0.00001
    variance_weight: float = 0.2
    direction_weight: float = 0.3
    friction_weight: float = 0.5
    epsilon: float = 1e-6
    slip_detect_debounce_cycles: int = 3
    default_friction_coeff: float = 0.7

    # Shared force-reference planner.
    adaptive_hold_command_mode: str = "position" #position or torque
    force_ref_margin_n: float = 0.10
    force_ref_slip_warning_threshold: float = 0.40
    force_ref_stable_threshold: float = 0.20
    force_ref_slip_gain_n_per_s: float = 0.20
    force_ref_max_rise_step_n: float = 0.02
    force_ref_confirmed_boost_n: float = 0.05
    force_ref_decay_rate_n_per_s: float = 0.02
    force_ref_stable_decay_delay_s: float = 1.0
    force_ref_min_contact_ratio: float = 0.15

    # Position hold mode.
    delta_theta_limit: float = math.radians(3)
    contact_snapshot_angle_limit: float = math.radians(20)
    adaptive_hold_move_failure_limit: int = 3
    near_force_limit_ratio: float = 0.9
    near_limit_step_scale: float = 0.8
    thumb_K_MCP: float = 0.7
    thumb_K_PIP: float = 0.3
    finger_K_MCP: float = 0.5
    finger_K_PIP: float = 0.5
    position_hold_K_p: float = 0.08
    position_hold_K_i: float = 0.02
    position_hold_K_d: float = 0.0
    position_hold_I_min: float = -1.0
    position_hold_I_max: float = 1.0
    direct_slip_risk_deadband: float = 0.25
    direct_slip_risk_full: float = 0.85
    direct_slip_risk_gamma: float = 1.5
    direct_slip_confirmed_boost_ratio: float = 0.5
    K_n: float = 1.0 #法向力超限时的关节角度释放系数，超限多少，乘该系数，就是手指关节角度的减少量

    # Torque hold mode.
    torque_hold_base_torque: int = 5
    torque_hold_K_p: float = 8.0
    torque_hold_K_i: float = 0.2
    torque_hold_K_d: float = 0.0
    torque_hold_I_min: float = -2.0
    torque_hold_I_max: float = 2.0

    # Release phase.
    release_hold_time_s: float = 20.0
    release_open_speed: int = 50
    release_open_torque: int = 50
    release_timeout_s: float = 5.0

    # Safety policy.
    sensor_missing_fault_cycles: int = 3
    empty_grasp_angle_threshold: float = math.radians(30.0)
    drop_detect_force_per_finger_n: float = 0.1
    drop_detect_debounce_cycles: int = 6
    enable_fault_release_fallback: bool = True

    # Fragile-object reductions.
    fragile_torque_reduction: float = 0.8
    fragile_step_reduction: float = 0.5

    # Visualization.
    enable_visualization: bool = True
    visualization_backend: str = "TkAgg"

    def __post_init__(self) -> None:
        self._derive_pre_grasp_preset()
        self._derive_active_fingers()
        self._validate_values()
        self._build_or_filter_pre_grasp_pose()
        self._validate_default_object()

    def _derive_pre_grasp_preset(self) -> None:
        if self.pre_grasp_preset is not None:
            return
        self.pre_grasp_preset = _OBJECT_PRE_GRASP_PRESET.get(
            self.default_object,
            "balloon_pinch",
        )

    def _derive_active_fingers(self) -> None:
        if not self.active_fingers:
            self.active_fingers = set(_PRESET_ACTIVE_FINGERS.get(self.pre_grasp_preset, set(TactileSensorId)))

    def _validate_values(self) -> None:
        _validate("sliding_window_size", self.sliding_window_size, greater_equal=3)
        _validate("control_period_s", self.control_period_s, greater_than=0)
        _validate("tactile_sensor_update_period_s", self.tactile_sensor_update_period_s, greater_than=0)
        _validate("tactile_dispatch_period_s", self.tactile_dispatch_period_s, greater_than=0)
        _validate("closing_period_s", self.closing_period_s, greater_than=0)

        _validate("open_speed", self.open_speed, greater_equal=0, less_equal=100)
        _validate("open_torque", self.open_torque, greater_equal=0, less_equal=100)
        _validate("open_wait_s", self.open_wait_s, greater_than=0)
        _validate("pre_grasp_speed", self.pre_grasp_speed, greater_equal=0, less_equal=100)
        _validate("pre_grasp_torque", self.pre_grasp_torque, greater_equal=0, less_equal=100)
        _validate("pre_grasp_wait_s", self.pre_grasp_wait_s, greater_than=0)

        _validate("max_torque", self.max_torque, greater_than=0)
        _validate("thumb_aux_torque", self.thumb_aux_torque, greater_equal=-100, less_equal=100)
        _validate("phase_timeout", self.phase_timeout, greater_than=0)
        _validate("closing_total_contact_threshold_n", self.closing_total_contact_threshold_n, greater_equal=0.0)
        _validate("finger_touch_threshold_n", self.finger_touch_threshold_n, greater_equal=0.0)
        _validate("closing_stall_angle_threshold", self.closing_stall_angle_threshold, greater_than=0)
        _validate("closing_stall_cycles", self.closing_stall_cycles, greater_than=0)

        _validate("variance_baseline", self.variance_baseline, greater_equal=0)
        _validate("variance_threshold", self.variance_threshold, greater_equal=0)
        if self.variance_baseline >= self.variance_threshold:
            raise ValueError("variance_baseline must be < variance_threshold")
        _validate("variance_weight", self.variance_weight, greater_equal=0.0, less_equal=1.0)
        _validate("direction_weight", self.direction_weight, greater_equal=0.0, less_equal=1.0)
        _validate("friction_weight", self.friction_weight, greater_equal=0.0, less_equal=1.0)
        if not math.isclose(
            self.variance_weight + self.direction_weight + self.friction_weight,
            1.0,
            abs_tol=1e-6,
        ):
            raise ValueError("variance_weight + direction_weight + friction_weight must equal 1.0")
        _validate("epsilon", self.epsilon, greater_than=0)
        _validate("slip_detect_debounce_cycles", self.slip_detect_debounce_cycles, greater_than=0)
        _validate("default_friction_coeff", self.default_friction_coeff, greater_than=0)
        _validate("max_normal_force_per_finger", self.max_normal_force_per_finger, greater_than=0)

        if self.adaptive_hold_command_mode not in {"position", "torque"}:
            raise ValueError('adaptive_hold_command_mode must be "position" or "torque"')
        self._validate_force_reference_params()
        self._validate_position_hold_params()
        self._validate_torque_hold_params()
        self._validate_release_params()
        self._validate_safety_params()

        _validate("fragile_torque_reduction", self.fragile_torque_reduction, greater_than=0.0, less_equal=1.0)
        _validate("fragile_step_reduction", self.fragile_step_reduction, greater_than=0.0, less_equal=1.0)

    def _validate_force_reference_params(self) -> None:
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

    def _validate_position_hold_params(self) -> None:
        _validate("delta_theta_limit", self.delta_theta_limit, greater_than=0)
        _validate("contact_snapshot_angle_limit", self.contact_snapshot_angle_limit, greater_than=0)
        _validate("adaptive_hold_move_failure_limit", self.adaptive_hold_move_failure_limit, greater_than=0)
        _validate("near_force_limit_ratio", self.near_force_limit_ratio, greater_than=0.0, less_equal=1.0)
        _validate("near_limit_step_scale", self.near_limit_step_scale, greater_than=0.0, less_equal=1.0)
        _validate("thumb_K_MCP", self.thumb_K_MCP, greater_equal=0.0)
        _validate("thumb_K_PIP", self.thumb_K_PIP, greater_equal=0.0)
        _validate("finger_K_MCP", self.finger_K_MCP, greater_equal=0.0)
        _validate("finger_K_PIP", self.finger_K_PIP, greater_equal=0.0)
        _validate("K_n", self.K_n, greater_equal=0)
        _validate("position_hold_K_p", self.position_hold_K_p, greater_equal=0)
        _validate("position_hold_K_i", self.position_hold_K_i, greater_equal=0)
        _validate("position_hold_K_d", self.position_hold_K_d, greater_equal=0)
        if self.position_hold_I_min > self.position_hold_I_max:
            raise ValueError("position_hold_I_min must be <= position_hold_I_max")
        _validate("direct_slip_risk_deadband", self.direct_slip_risk_deadband, greater_equal=0.0, less_equal=1.0)
        _validate("direct_slip_risk_full", self.direct_slip_risk_full, greater_equal=0.0, less_equal=1.0)
        if self.direct_slip_risk_deadband >= self.direct_slip_risk_full:
            raise ValueError("direct_slip_risk_deadband must be < direct_slip_risk_full")
        _validate("direct_slip_risk_gamma", self.direct_slip_risk_gamma, greater_than=0.0)
        _validate("direct_slip_confirmed_boost_ratio", self.direct_slip_confirmed_boost_ratio, greater_equal=0.0)

    def _validate_torque_hold_params(self) -> None:
        _validate("torque_hold_base_torque", self.torque_hold_base_torque, greater_equal=-100, less_equal=100)
        _validate("torque_hold_K_p", self.torque_hold_K_p, greater_equal=0.0)
        _validate("torque_hold_K_i", self.torque_hold_K_i, greater_equal=0.0)
        _validate("torque_hold_K_d", self.torque_hold_K_d, greater_equal=0.0)
        if self.torque_hold_I_min > self.torque_hold_I_max:
            raise ValueError("torque_hold_I_min must be <= torque_hold_I_max")

    def _validate_release_params(self) -> None:
        _validate("release_hold_time_s", self.release_hold_time_s, greater_than=0)
        _validate("release_open_speed", self.release_open_speed, greater_equal=0, less_equal=100)
        _validate("release_open_torque", self.release_open_torque, greater_equal=0, less_equal=100)
        _validate("release_timeout_s", self.release_timeout_s, greater_than=0)

    def _validate_safety_params(self) -> None:
        _validate("sensor_missing_fault_cycles", self.sensor_missing_fault_cycles, greater_than=0)
        _validate("empty_grasp_angle_threshold", self.empty_grasp_angle_threshold, greater_than=0)
        _validate("drop_detect_force_per_finger_n", self.drop_detect_force_per_finger_n, greater_equal=0.0)
        _validate("drop_detect_debounce_cycles", self.drop_detect_debounce_cycles, greater_than=0)

    def _build_or_filter_pre_grasp_pose(self) -> None:
        if self.pre_grasp_pose:
            filtered = self._filter_passive_dip_joints(self.pre_grasp_pose)
            self.pre_grasp_pose = filtered if filtered else self._build_pre_grasp_pose_from_preset()
            return
        self.pre_grasp_pose = self._build_pre_grasp_pose_from_preset()

    def _validate_default_object(self) -> None:
        if ObjectProfileRegistry.get(self.default_object) is not None:
            return
        supported = ", ".join(sorted(ObjectProfileRegistry.list_all()))
        raise ValueError(f"default_object must be one of: {supported}")

    def _build_pre_grasp_pose_from_preset(self) -> dict[JointId, float]:
        if self.pre_grasp_preset not in _PRE_GRASP_PRESET_DEGREE:
            supported = ", ".join(sorted(_PRE_GRASP_PRESET_DEGREE.keys()))
            raise ValueError(f"pre_grasp_preset must be one of: {supported}")

        degrees_map = _PRE_GRASP_PRESET_DEGREE[self.pre_grasp_preset]
        return {
            joint_id: math.radians(degrees_map.get(joint_id, 0.0))
            for joint_id in _ACTIVE_PRE_GRASP_JOINTS
        }

    @staticmethod
    def _filter_passive_dip_joints(
        pose: dict[JointId, float],
    ) -> dict[JointId, float]:
        return {
            joint_id: angle
            for joint_id, angle in pose.items()
            if joint_id not in _PASSIVE_DIP_JOINTS
        }
