import math
from dataclasses import dataclass, field
from typing import Optional

from .grasp_presets import (
    build_or_filter_pre_grasp_pose,
    resolve_active_fingers,
    resolve_pre_grasp_preset,
)
from .object_profile import ObjectProfileRegistry
from ghand import JointId, TactileSensorId


@dataclass
class PerFingerPidConfig:
    """Optional per-finger overrides for the position-hold PID."""

    K_p: Optional[float] = None  # Per-finger proportional gain override.
    K_i: Optional[float] = None  # Per-finger integral gain override.
    K_d: Optional[float] = None  # Per-finger derivative gain override.
    I_min: Optional[float] = None  # Per-finger integral lower clamp override.
    I_max: Optional[float] = None  # Per-finger integral upper clamp override.


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
    default_object: str = "balloon"  # Object profile name used when no object is selected by the caller.
    pre_grasp_preset: Optional[str] = None  # Named pre-grasp pose preset; derived from default_object when omitted.
    pre_grasp_pose: dict[JointId, float] = field(default_factory=dict)  # JointCommand target pose in radians before closing.
    active_fingers: set[TactileSensorId] = field(default_factory=set)  # Fingers used for contact, tactile analysis, and hold control.
    per_finger_pid: dict[TactileSensorId, PerFingerPidConfig] = field(default_factory=dict)  # Optional per-finger PID overrides.

    # Open, pre-grasp, and closing-to-contact phases.
    open_speed: int = 50  # Speed command used when opening the hand.
    open_torque: int = 50  # Torque/current limit used when opening the hand.
    pre_grasp_speed: int = 75  # Speed command used when moving to the pre-grasp pose.
    pre_grasp_torque: int = 75  # Torque/current limit used when moving to the pre-grasp pose.
    closing_total_contact_threshold_n: float = 0.2  # Total normal force threshold for ending the closing phase.
    finger_touch_threshold_n: float = 0.1  # Per-finger normal force threshold for considering a finger in contact.

    max_torque: int = 80  # Maximum torque/current limit used during adaptive closing.
    thumb_aux_torque: int = 3  # Auxiliary thumb torque/current offset used during closing.
    phase_timeout: float = 10.0  # Default timeout for high-level grasp phases.
    control_period_s: float = 0.02  # Main adaptive hold loop period.
    closing_period_s: float = 0.2  # Polling period during the closing-to-contact phase.
    closing_stall_angle_threshold: float = math.radians(0.5)  # Minimum angle change used to detect stalled closing.
    closing_stall_cycles: int = 5  # Consecutive low-motion cycles required before declaring closing stalled.

    # Tactile subscription timing.
    tactile_sensor_update_period_s: float = 0.02  # Hardware tactile sampling period.
    tactile_dispatch_period_s: float = 0.02  # Tactile frame dispatch period used by the adaptive loop.

    # Tactile slip analysis.
    tactile_slip_window_size: int = 10  # Number of recent tangential-force samples used for slip analysis.
    tactile_lowpass_alpha: float = 0.3  # Low-pass smoothing factor for tactile force and slip-risk signals.
    max_normal_force_per_finger_n: float = 25.0  # Fallback per-finger normal-force limit when no object profile is present.
    slip_variance_threshold: float = 0.003  # Tangential-force variance that maps to full variance slip risk.
    slip_variance_baseline: float = 0.00001  # Tangential-force variance treated as zero variance slip risk.
    slip_variance_weight: float = 0.2  # Weight of the variance slip feature in the fused slip risk.
    slip_direction_weight: float = 0.3  # Weight of the direction-change slip feature in the fused slip risk.
    slip_friction_weight: float = 0.5  # Weight of the friction-utilization slip feature in the fused slip risk.
    numeric_epsilon: float = 1e-6  # Small positive value used to avoid divide-by-zero.
    slip_detect_debounce_cycles: int = 3  # Consecutive slip-risk cycles required to confirm slip.
    default_friction_coeff: float = 0.7  # Default contact friction coefficient used before caller calibration.

    # Shared force-reference planner.
    hold_command_mode: str = "position"  # Adaptive hold command mode: "position" or internal "torque".
    force_ref_margin_n: float = 0.10  # Extra normal-force margin added to the initial contact force reference.
    force_ref_slip_warning_threshold: float = 0.40  # Slip-risk level where the force reference starts increasing.
    force_ref_stable_threshold: float = 0.20  # Slip-risk level below which the force reference may decay.
    force_ref_slip_gain_n_per_s: float = 0.20  # Force-reference rise gain per second when slip risk is high.
    force_ref_max_rise_step_n: float = 0.02  # Maximum force-reference increase per control cycle.
    force_ref_confirmed_boost_n: float = 0.05  # Immediate force-reference boost when slip is confirmed.
    force_ref_decay_rate_n_per_s: float = 0.02  # Force-reference decay rate while the grasp is stable.
    force_ref_stable_decay_delay_s: float = 1.0  # Stable duration required before force-reference decay starts.
    force_ref_min_contact_ratio: float = 0.15  # Minimum share assigned to each active contacting finger.

    # Position hold mode.
    enable_position_hold_force_control: bool = True  # Enables direct force-based position correction; false keeps control_u at zero.
    position_hold_max_step_rad: float = math.radians(4)  # Maximum total JointCommand-angle correction per control cycle.
    contact_angle_guard_margin_rad: float = math.radians(20)  # Allowed angle margin around the contact snapshot during hold.
    adaptive_hold_move_failure_limit: int = 3  # Consecutive failed hold moves allowed before fault handling.
    force_limit_slowdown_ratio: float = 0.9  # Fraction of the normal-force limit where step slowdown begins.
    force_limit_slowdown_step_scale: float = 0.8  # Step scaling applied when any active finger is near the force limit.
    thumb_mcp_step_ratio: float = 0.7  # Thumb MCP share of the total position-hold angle correction.
    thumb_pip_step_ratio: float = 0.3  # Thumb PIP share of the total position-hold angle correction.
    finger_mcp_step_ratio: float = 0.5  # Non-thumb MCP share of the total position-hold angle correction.
    finger_pip_step_ratio: float = 0.5  # Non-thumb PIP share of the total position-hold angle correction.
    position_hold_K_p: float = 0.08  # Proportional gain for closed-loop position hold.
    position_hold_K_i: float = 0.02  # Integral gain for closed-loop position hold.
    position_hold_K_d: float = 0.0  # Derivative gain for closed-loop position hold.
    position_hold_I_min: float = -1.0  # Integral lower clamp for closed-loop position hold.
    position_hold_I_max: float = 1.0  # Integral upper clamp for closed-loop position hold.
    direct_slip_risk_deadband: float = 0.25  # Slip-risk level below which direct position correction is zero.
    direct_slip_risk_full: float = 0.85  # Slip-risk level that maps to the maximum direct position correction.
    direct_slip_risk_gamma: float = 1.5  # Nonlinear shaping exponent for slip-risk position correction.
    direct_slip_confirmed_boost_ratio: float = 0.5  # Extra correction ratio applied when slip is confirmed.
    normal_force_release_gain: float = 0.1  # Release gain used when normal force exceeds the per-finger limit.

    # Torque hold mode.
    torque_hold_base_torque: int = 5  # Base torque/current command for the internal torque-hold mode.
    torque_hold_K_p: float = 8.0  # Proportional gain for the internal torque-hold mode.
    torque_hold_K_i: float = 0.2  # Integral gain for the internal torque-hold mode.
    torque_hold_K_d: float = 0.0  # Derivative gain for the internal torque-hold mode.
    torque_hold_I_min: float = -2.0  # Integral lower clamp for the internal torque-hold mode.
    torque_hold_I_max: float = 2.0  # Integral upper clamp for the internal torque-hold mode.

    # Release phase.
    release_hold_time_s: float = 20.0  # Duration to keep adaptive hold before automatic release in the demo sequence.
    release_open_speed: int = 80  # Speed command used during release opening.
    release_open_torque: int = 80  # Torque/current limit used during release opening.
    release_timeout_s: float = 5.0  # Timeout for the release phase.

    # Safety policy.
    sensor_missing_fault_cycles: int = 3  # Consecutive missing tactile frames allowed before a sensor fault.
    empty_grasp_angle_threshold: float = math.radians(30.0)  # Closing angle threshold used to detect an empty grasp.
    drop_detect_force_per_finger_n: float = 0.1  # Per-finger force threshold below which drop detection may trigger.
    drop_detect_debounce_cycles: int = 6  # Consecutive low-force cycles required to confirm a drop.
    enable_fault_release_fallback: bool = True  # Releases the hand automatically when recoverable safety faults occur.

    # Fragile-object reductions.
    fragile_torque_reduction: float = 0.8  # Torque scaling applied for fragile object profiles.
    fragile_step_reduction: float = 0.5  # Position correction scaling applied for fragile object profiles.

    # Visualization.
    enable_visualization: bool = True  # Enables internal diagnostic visualization.
    visualization_backend: str = "TkAgg"  # Matplotlib backend used by internal visualization.

    def __post_init__(self) -> None:
        self._derive_pre_grasp_preset()
        self._derive_active_fingers()
        self._validate_values()
        self._build_or_filter_pre_grasp_pose()
        self._validate_default_object()

    def _derive_pre_grasp_preset(self) -> None:
        self.pre_grasp_preset = resolve_pre_grasp_preset(
            self.default_object,
            self.pre_grasp_preset,
        )

    def _derive_active_fingers(self) -> None:
        self.active_fingers = resolve_active_fingers(
            self.pre_grasp_preset,
            self.active_fingers,
        )

    def _validate_values(self) -> None:
        _validate("tactile_slip_window_size", self.tactile_slip_window_size, greater_equal=3)
        _validate("tactile_lowpass_alpha", self.tactile_lowpass_alpha, greater_than=0.0, less_equal=1.0)
        _validate("control_period_s", self.control_period_s, greater_than=0)
        _validate("tactile_sensor_update_period_s", self.tactile_sensor_update_period_s, greater_than=0)
        _validate("tactile_dispatch_period_s", self.tactile_dispatch_period_s, greater_than=0)
        _validate("closing_period_s", self.closing_period_s, greater_than=0)

        _validate("open_speed", self.open_speed, greater_equal=0, less_equal=100)
        _validate("open_torque", self.open_torque, greater_equal=0, less_equal=100)
        _validate("pre_grasp_speed", self.pre_grasp_speed, greater_equal=0, less_equal=100)
        _validate("pre_grasp_torque", self.pre_grasp_torque, greater_equal=0, less_equal=100)

        _validate("max_torque", self.max_torque, greater_than=0)
        _validate("thumb_aux_torque", self.thumb_aux_torque, greater_equal=-100, less_equal=100)
        _validate("phase_timeout", self.phase_timeout, greater_than=0)
        _validate("closing_total_contact_threshold_n", self.closing_total_contact_threshold_n, greater_equal=0.0)
        _validate("finger_touch_threshold_n", self.finger_touch_threshold_n, greater_equal=0.0)
        _validate("closing_stall_angle_threshold", self.closing_stall_angle_threshold, greater_than=0)
        _validate("closing_stall_cycles", self.closing_stall_cycles, greater_than=0)

        _validate("slip_variance_baseline", self.slip_variance_baseline, greater_equal=0)
        _validate("slip_variance_threshold", self.slip_variance_threshold, greater_equal=0)
        if self.slip_variance_baseline >= self.slip_variance_threshold:
            raise ValueError("slip_variance_baseline must be < slip_variance_threshold")
        _validate("slip_variance_weight", self.slip_variance_weight, greater_equal=0.0, less_equal=1.0)
        _validate("slip_direction_weight", self.slip_direction_weight, greater_equal=0.0, less_equal=1.0)
        _validate("slip_friction_weight", self.slip_friction_weight, greater_equal=0.0, less_equal=1.0)
        if not math.isclose(
            self.slip_variance_weight + self.slip_direction_weight + self.slip_friction_weight,
            1.0,
            abs_tol=1e-6,
        ):
            raise ValueError(
                "slip_variance_weight + slip_direction_weight + slip_friction_weight must equal 1.0"
            )
        _validate("numeric_epsilon", self.numeric_epsilon, greater_than=0)
        _validate("slip_detect_debounce_cycles", self.slip_detect_debounce_cycles, greater_than=0)
        _validate("default_friction_coeff", self.default_friction_coeff, greater_than=0)
        _validate("max_normal_force_per_finger_n", self.max_normal_force_per_finger_n, greater_than=0)

        if self.hold_command_mode not in {"position", "torque"}:
            raise ValueError('hold_command_mode must be "position" or "torque"')
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
        if not isinstance(self.enable_position_hold_force_control, bool):
            raise ValueError("enable_position_hold_force_control must be bool")
        _validate("position_hold_max_step_rad", self.position_hold_max_step_rad, greater_than=0)
        _validate("contact_angle_guard_margin_rad", self.contact_angle_guard_margin_rad, greater_than=0)
        _validate("adaptive_hold_move_failure_limit", self.adaptive_hold_move_failure_limit, greater_than=0)
        _validate("force_limit_slowdown_ratio", self.force_limit_slowdown_ratio, greater_than=0.0, less_equal=1.0)
        _validate(
            "force_limit_slowdown_step_scale",
            self.force_limit_slowdown_step_scale,
            greater_than=0.0,
            less_equal=1.0,
        )
        _validate("thumb_mcp_step_ratio", self.thumb_mcp_step_ratio, greater_equal=0.0)
        _validate("thumb_pip_step_ratio", self.thumb_pip_step_ratio, greater_equal=0.0)
        _validate("finger_mcp_step_ratio", self.finger_mcp_step_ratio, greater_equal=0.0)
        _validate("finger_pip_step_ratio", self.finger_pip_step_ratio, greater_equal=0.0)
        _validate("normal_force_release_gain", self.normal_force_release_gain, greater_equal=0)
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
        self.pre_grasp_pose = build_or_filter_pre_grasp_pose(
            self.pre_grasp_preset,
            self.pre_grasp_pose,
        )

    def _validate_default_object(self) -> None:
        if ObjectProfileRegistry.get(self.default_object) is not None:
            return
        supported = ", ".join(sorted(ObjectProfileRegistry.list_all()))
        raise ValueError(f"default_object must be one of: {supported}")
