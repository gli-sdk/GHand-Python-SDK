import math
from dataclasses import dataclass, field
from enum import Enum

from .grasp_presets import (
    PASSIVE_DIP_JOINTS,
    build_pre_grasp_pose_from_preset,
    resolve_active_fingers,
)
from .object_profile import ObjectProfileRegistry
from ghand import JointId, TactileSensorId


class HoldCommandMode(Enum):
    POSITION = "position"
    STIFF_POSITION = "stiff_position"


def _validate_range(
    name: str,
    value: int | float,
    *,
    greater_than: int | float | None = None,
    greater_than_or_equal_to: int | float | None = None,
    less_than: int | float | None = None,
    less_than_or_equal_to: int | float | None = None,
) -> None:
    if greater_than is not None and value <= greater_than:
        raise ValueError(f"{name} must be > {greater_than}")
    if (greater_than_or_equal_to is not None
            and value < greater_than_or_equal_to):
        raise ValueError(f"{name} must be >= {greater_than_or_equal_to}")
    if less_than is not None and value >= less_than:
        raise ValueError(f"{name} must be < {less_than}")
    if less_than_or_equal_to is not None and value > less_than_or_equal_to:
        raise ValueError(f"{name} must be <= {less_than_or_equal_to}")


@dataclass
class AdaptiveGraspConfig:
    """Configuration entry point for the adaptive grasp SDK."""

    # Object and pre-grasp pose.
    pre_grasp_preset: str  # Named pre-grasp pose preset; callers must provide it explicitly.
    default_object: str = "balloon"  # Object profile name used when no object is selected by the caller.
    pre_grasp_pose: dict[JointId, float] = field(
        default_factory=dict
    )  # JointCommand target pose in degrees before closing.
    active_fingers: set[TactileSensorId] = field(
        default_factory=set
    )  # Fingers used for contact, tactile analysis, and hold control.
    # Open, pre-grasp, and closing-to-contact phases.
    open_speed: int = 100  # Speed command used when opening the hand.
    open_torque: int = 100  # Torque/current limit used when opening the hand.
    pre_grasp_speed: int = 80  # Speed command used when moving to the pre-grasp pose.
    pre_grasp_torque: int = 80  # Torque/current limit used when moving to the pre-grasp pose.
    closing_total_contact_threshold_n: float = 0.2  # Total normal force threshold for ending the closing phase.
    finger_touch_threshold_n: float = 0.1  # Per-finger normal force threshold for considering a finger in contact.

    max_torque: int = 80  # Maximum torque/current limit used during adaptive closing.
    thumb_aux_torque: int = 3  # Auxiliary thumb torque/current offset used during closing.
    phase_timeout: float = 10.0  # Default timeout for high-level grasp phases.
    control_period_s: float = 0.02  # Main adaptive hold loop period.
    closing_period_s: float = 0.2  # Polling period during the closing-to-contact phase.
    closing_stall_angle_threshold: float = 0.5  # Minimum angle change in degrees used to detect stalled closing.
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
    hold_command_mode: HoldCommandMode = HoldCommandMode.POSITION  # Adaptive hold command mode.
    force_reference_margin_n: float = 0.10  # Extra normal-force margin added to the initial contact force reference.
    force_reference_slip_warning_threshold: float = 0.40  # Slip-risk level where the force reference starts increasing.
    force_reference_stable_threshold: float = 0.20  # Slip-risk level below which the force reference may decay.
    force_reference_slip_gain_n_per_s: float = 0.20  # Force-reference rise gain per second when slip risk is high.
    force_reference_max_rise_step_n: float = 0.02  # Maximum force-reference increase per control cycle.
    force_reference_confirmed_boost_n: float = 0.05  # Immediate force-reference boost when slip is confirmed.
    force_reference_decay_rate_n_per_s: float = 0.02  # Force-reference decay rate while the grasp is stable.
    force_reference_stable_decay_delay_s: float = 1.0  # Stable duration required before force-reference decay starts.
    force_reference_min_contact_ratio: float = 0.15  # Minimum share assigned to each active contacting finger.

    # Position hold mode.
    enable_position_hold_force_control: bool = True  # Enables direct force-based position correction; false keeps control_u at zero.
    position_hold_max_step_deg: float = 4.0  # Maximum total JointCommand-angle correction in degrees per control cycle.
    position_hold_contact_angle_guard_margin_deg: float = 20.0  # Allowed angle margin in degrees around the contact snapshot during hold.
    position_hold_move_failure_limit: int = 3  # Consecutive failed hold moves allowed before fault handling.
    position_hold_force_limit_slowdown_ratio: float = 0.9  # Fraction of the normal-force limit where step slowdown begins.
    position_hold_force_limit_slowdown_step_scale: float = 0.8  # Step scaling applied when any active finger is near the force limit.
    thumb_tmc_fe_step_ratio: float = 0.7  # Thumb TMC flexion/extension share of the total position-hold angle correction.
    thumb_mcp_step_ratio: float = 0.3  # Thumb MCP share of the total position-hold angle correction.
    finger_mcp_step_ratio: float = 0.5  # Non-thumb MCP share of the total position-hold angle correction.
    finger_pip_step_ratio: float = 0.5  # Non-thumb PIP share of the total position-hold angle correction.
    position_hold_slip_risk_deadband: float = 0.25  # Slip-risk level below which direct position correction is zero.
    position_hold_slip_risk_full: float = 0.85  # Slip-risk level that maps to the maximum direct position correction.
    position_hold_slip_risk_gamma: float = 1.5  # Nonlinear shaping exponent for slip-risk position correction.
    position_hold_confirmed_slip_boost_ratio: float = 0.5  # Extra correction ratio applied when slip is confirmed.
    position_hold_normal_force_release_gain: float = 0.1  # Release gain used when normal force exceeds the per-finger limit.

    # Stiff position hold mode
    stiff_position_hold_speed: int = 90  # Default speed command for stiff_position hold mode.
    stiff_position_hold_torque: int = 90  # Default torque/current command for stiff_position hold mode.
    stiff_position_step_deg: float = 0.2  # Default incremental angle step in degrees for stiff_position hold mode.
    stiff_position_max_delta_deg: float = 5.0  # Default max angle delta from contact in degrees for stiff_position hold mode.
    stiff_position_force_drop_ratio: float = 0.5  # Ratio drop in total normal force that triggers contact-loss guard in stiff_position mode.

    # Release phase.
    release_hold_time_s: float = 20.0  # Duration to keep adaptive hold before automatic release in the demo sequence.
    release_open_speed: int = 80  # Speed command used during release opening.
    release_open_torque: int = 80  # Torque/current limit used during release opening.
    release_timeout_s: float = 5.0  # Timeout for the release phase.

    # Safety policy.
    sensor_missing_fault_cycles: int = 3  # Consecutive missing tactile frames allowed before a sensor fault.
    empty_grasp_angle_threshold: float = 30.0  # Closing angle threshold in degrees used to detect an empty grasp.
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
        pre_grasp_preset = self._required_pre_grasp_preset()
        self._derive_active_fingers(pre_grasp_preset)
        self._validate_values()
        self._resolve_pre_grasp_pose(pre_grasp_preset)
        self._validate_default_object()

    def _required_pre_grasp_preset(self) -> str:
        if not self.pre_grasp_preset:
            raise ValueError("pre_grasp_preset is required")
        return self.pre_grasp_preset

    def _derive_active_fingers(self, pre_grasp_preset: str) -> None:
        self.active_fingers = resolve_active_fingers(
            pre_grasp_preset,
            self.active_fingers,
        )

    def _validate_values(self) -> None:
        self._validate_motion_params()
        self._validate_tactile_timing_params()
        self._validate_slip_analysis_params()
        self._validate_hold_command_mode()
        self._validate_force_reference_params()
        self._validate_position_hold_params()
        self._validate_stiff_position_hold_params()
        self._validate_release_params()
        self._validate_safety_params()
        self._validate_fragile_object_params()

    def _validate_motion_params(self) -> None:
        _validate_range(
            "open_speed",
            self.open_speed,
            greater_than_or_equal_to=0,
            less_than_or_equal_to=100,
        )
        _validate_range(
            "open_torque",
            self.open_torque,
            greater_than_or_equal_to=0,
            less_than_or_equal_to=100,
        )
        _validate_range(
            "pre_grasp_speed",
            self.pre_grasp_speed,
            greater_than_or_equal_to=0,
            less_than_or_equal_to=100,
        )
        _validate_range(
            "pre_grasp_torque",
            self.pre_grasp_torque,
            greater_than_or_equal_to=0,
            less_than_or_equal_to=100,
        )

        _validate_range("max_torque", self.max_torque, greater_than=0)
        _validate_range(
            "thumb_aux_torque",
            self.thumb_aux_torque,
            greater_than_or_equal_to=-100,
            less_than_or_equal_to=100,
        )
        _validate_range("phase_timeout", self.phase_timeout, greater_than=0)
        _validate_range(
            "closing_total_contact_threshold_n",
            self.closing_total_contact_threshold_n,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "finger_touch_threshold_n",
            self.finger_touch_threshold_n,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "closing_stall_angle_threshold",
            self.closing_stall_angle_threshold,
            greater_than=0,
        )
        _validate_range(
            "closing_stall_cycles",
            self.closing_stall_cycles,
            greater_than=0,
        )

    def _validate_tactile_timing_params(self) -> None:
        _validate_range(
            "control_period_s",
            self.control_period_s,
            greater_than=0,
        )
        _validate_range(
            "tactile_sensor_update_period_s",
            self.tactile_sensor_update_period_s,
            greater_than=0,
        )
        _validate_range(
            "tactile_dispatch_period_s",
            self.tactile_dispatch_period_s,
            greater_than=0,
        )
        _validate_range(
            "closing_period_s",
            self.closing_period_s,
            greater_than=0,
        )

    def _validate_slip_analysis_params(self) -> None:
        _validate_range(
            "tactile_slip_window_size",
            self.tactile_slip_window_size,
            greater_than_or_equal_to=3,
        )
        _validate_range(
            "tactile_lowpass_alpha",
            self.tactile_lowpass_alpha,
            greater_than=0.0,
            less_than_or_equal_to=1.0,
        )
        _validate_range(
            "slip_variance_baseline",
            self.slip_variance_baseline,
            greater_than_or_equal_to=0,
        )
        _validate_range(
            "slip_variance_threshold",
            self.slip_variance_threshold,
            greater_than_or_equal_to=0,
        )
        if self.slip_variance_baseline >= self.slip_variance_threshold:
            raise ValueError(
                "slip_variance_baseline must be < slip_variance_threshold")
        _validate_range(
            "slip_variance_weight",
            self.slip_variance_weight,
            greater_than_or_equal_to=0.0,
            less_than_or_equal_to=1.0,
        )
        _validate_range(
            "slip_direction_weight",
            self.slip_direction_weight,
            greater_than_or_equal_to=0.0,
            less_than_or_equal_to=1.0,
        )
        _validate_range(
            "slip_friction_weight",
            self.slip_friction_weight,
            greater_than_or_equal_to=0.0,
            less_than_or_equal_to=1.0,
        )
        if not math.isclose(
                self.slip_variance_weight + self.slip_direction_weight +
                self.slip_friction_weight,
                1.0,
                abs_tol=1e-6,
        ):
            raise ValueError(
                "slip_variance_weight + slip_direction_weight + slip_friction_weight must equal 1.0"
            )
        _validate_range("numeric_epsilon", self.numeric_epsilon, greater_than=0)
        _validate_range(
            "slip_detect_debounce_cycles",
            self.slip_detect_debounce_cycles,
            greater_than=0,
        )
        _validate_range(
            "default_friction_coeff",
            self.default_friction_coeff,
            greater_than=0,
        )
        _validate_range(
            "max_normal_force_per_finger_n",
            self.max_normal_force_per_finger_n,
            greater_than=0,
        )

    def _validate_hold_command_mode(self) -> None:
        if not isinstance(self.hold_command_mode, HoldCommandMode):
            raise ValueError(
                "hold_command_mode must be HoldCommandMode.POSITION, "
                "or HoldCommandMode.STIFF_POSITION"
            )

    def _validate_fragile_object_params(self) -> None:
        _validate_range(
            "fragile_torque_reduction",
            self.fragile_torque_reduction,
            greater_than=0.0,
            less_than_or_equal_to=1.0,
        )
        _validate_range(
            "fragile_step_reduction",
            self.fragile_step_reduction,
            greater_than=0.0,
            less_than_or_equal_to=1.0,
        )

    def _validate_force_reference_params(self) -> None:
        _validate_range(
            "force_reference_margin_n",
            self.force_reference_margin_n,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "force_reference_slip_warning_threshold",
            self.force_reference_slip_warning_threshold,
            greater_than_or_equal_to=0.0,
            less_than_or_equal_to=1.0,
        )
        _validate_range(
            "force_reference_stable_threshold",
            self.force_reference_stable_threshold,
            greater_than_or_equal_to=0.0,
            less_than_or_equal_to=1.0,
        )
        _validate_range(
            "force_reference_slip_gain_n_per_s",
            self.force_reference_slip_gain_n_per_s,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "force_reference_max_rise_step_n",
            self.force_reference_max_rise_step_n,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "force_reference_confirmed_boost_n",
            self.force_reference_confirmed_boost_n,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "force_reference_decay_rate_n_per_s",
            self.force_reference_decay_rate_n_per_s,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "force_reference_stable_decay_delay_s",
            self.force_reference_stable_decay_delay_s,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "force_reference_min_contact_ratio",
            self.force_reference_min_contact_ratio,
            greater_than_or_equal_to=0.0,
            less_than_or_equal_to=1.0,
        )
        if (self.force_reference_min_contact_ratio *
                len(self.active_fingers) > 1.0):
            raise ValueError(
                "force_reference_min_contact_ratio * active_finger_count must be <= 1.0"
            )

    def _validate_position_hold_params(self) -> None:
        if not isinstance(self.enable_position_hold_force_control, bool):
            raise ValueError("enable_position_hold_force_control must be bool")
        _validate_range(
            "position_hold_max_step_deg",
            self.position_hold_max_step_deg,
            greater_than=0,
        )
        _validate_range(
            "position_hold_contact_angle_guard_margin_deg",
            self.position_hold_contact_angle_guard_margin_deg,
            greater_than=0,
        )
        _validate_range(
            "position_hold_move_failure_limit",
            self.position_hold_move_failure_limit,
            greater_than=0,
        )
        _validate_range(
            "position_hold_force_limit_slowdown_ratio",
            self.position_hold_force_limit_slowdown_ratio,
            greater_than=0.0,
            less_than_or_equal_to=1.0,
        )
        _validate_range(
            "position_hold_force_limit_slowdown_step_scale",
            self.position_hold_force_limit_slowdown_step_scale,
            greater_than=0.0,
            less_than_or_equal_to=1.0,
        )
        _validate_range(
            "thumb_tmc_fe_step_ratio",
            self.thumb_tmc_fe_step_ratio,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "thumb_mcp_step_ratio",
            self.thumb_mcp_step_ratio,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "finger_mcp_step_ratio",
            self.finger_mcp_step_ratio,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "finger_pip_step_ratio",
            self.finger_pip_step_ratio,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "position_hold_normal_force_release_gain",
            self.position_hold_normal_force_release_gain,
            greater_than_or_equal_to=0,
        )
        _validate_range(
            "position_hold_slip_risk_deadband",
            self.position_hold_slip_risk_deadband,
            greater_than_or_equal_to=0.0,
            less_than_or_equal_to=1.0,
        )
        _validate_range(
            "position_hold_slip_risk_full",
            self.position_hold_slip_risk_full,
            greater_than_or_equal_to=0.0,
            less_than_or_equal_to=1.0,
        )
        if (self.position_hold_slip_risk_deadband >=
                self.position_hold_slip_risk_full):
            raise ValueError(
                "position_hold_slip_risk_deadband must be < position_hold_slip_risk_full")
        _validate_range(
            "position_hold_slip_risk_gamma",
            self.position_hold_slip_risk_gamma,
            greater_than=0.0,
        )
        _validate_range(
            "position_hold_confirmed_slip_boost_ratio",
            self.position_hold_confirmed_slip_boost_ratio,
            greater_than_or_equal_to=0.0,
        )

    def _validate_stiff_position_hold_params(self) -> None:
        _validate_range(
            "stiff_position_hold_speed",
            self.stiff_position_hold_speed,
            greater_than_or_equal_to=0,
            less_than_or_equal_to=100,
        )
        _validate_range(
            "stiff_position_hold_torque",
            self.stiff_position_hold_torque,
            greater_than_or_equal_to=0,
            less_than_or_equal_to=100,
        )
        _validate_range(
            "stiff_position_step_deg",
            self.stiff_position_step_deg,
            greater_than=0,
        )
        _validate_range(
            "stiff_position_max_delta_deg",
            self.stiff_position_max_delta_deg,
            greater_than=0,
        )
        _validate_range(
            "stiff_position_force_drop_ratio",
            self.stiff_position_force_drop_ratio,
            greater_than=0.0,
            less_than=1.0,
        )

    def _validate_release_params(self) -> None:
        _validate_range(
            "release_hold_time_s",
            self.release_hold_time_s,
            greater_than=0,
        )
        _validate_range(
            "release_open_speed",
            self.release_open_speed,
            greater_than_or_equal_to=0,
            less_than_or_equal_to=100,
        )
        _validate_range(
            "release_open_torque",
            self.release_open_torque,
            greater_than_or_equal_to=0,
            less_than_or_equal_to=100,
        )
        _validate_range(
            "release_timeout_s",
            self.release_timeout_s,
            greater_than=0,
        )

    def _validate_safety_params(self) -> None:
        _validate_range(
            "sensor_missing_fault_cycles",
            self.sensor_missing_fault_cycles,
            greater_than=0,
        )
        _validate_range(
            "empty_grasp_angle_threshold",
            self.empty_grasp_angle_threshold,
            greater_than=0,
        )
        _validate_range(
            "drop_detect_force_per_finger_n",
            self.drop_detect_force_per_finger_n,
            greater_than_or_equal_to=0.0,
        )
        _validate_range(
            "drop_detect_debounce_cycles",
            self.drop_detect_debounce_cycles,
            greater_than=0,
        )

    def _resolve_pre_grasp_pose(self, pre_grasp_preset: str) -> None:
        if self.pre_grasp_pose:
            passive_joints = sorted(
                joint_id.name
                for joint_id in self.pre_grasp_pose
                if joint_id in PASSIVE_DIP_JOINTS
            )
            if passive_joints:
                joints = ", ".join(passive_joints)
                raise ValueError(
                    f"pre_grasp_pose cannot include passive DIP joints: {joints}"
                )
            return

        self.pre_grasp_pose = build_pre_grasp_pose_from_preset(
            pre_grasp_preset)

    def _validate_default_object(self) -> None:
        if ObjectProfileRegistry.get(self.default_object) is not None:
            return
        supported = ", ".join(sorted(ObjectProfileRegistry.list_all()))
        raise ValueError(f"default_object must be one of: {supported}")
