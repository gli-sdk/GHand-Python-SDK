import pytest

from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.grasp_sequence import ContactSnapshot
from xiaoyao.adaptive_grasp.object_profile import ObjectProfile
from xiaoyao.adaptive_grasp.tactility import TactileAnalysis
from xiaoyao.adaptive_grasp.torque_hold_planner import TorqueHoldPlanner
from xiaoyao.dexhand import TactileSensorId


def _snapshot(
    *,
    finger_fz: dict[TactileSensorId, float] | None = None,
    total_fz: float = 0.55,
) -> ContactSnapshot:
    return ContactSnapshot(
        joint_angles={},
        finger_fz=finger_fz
        if finger_fz is not None
        else {
            TactileSensorId.THUMB: 0.30,
            TactileSensorId.FOREFINGER: 0.15,
            TactileSensorId.MIDDLE_FINGER: 0.10,
        },
        total_fz=total_fz,
        torque=5,
        reason="force_threshold",
        timestamp_s=1.0,
    )


def _profile(
    *,
    safe_force_min: float = 0.5,
    safe_force_max: float = 3.5,
) -> ObjectProfile:
    return ObjectProfile(
        name="paper_cup_test",
        weight_kg=0.01,
        safe_force_min=safe_force_min,
        safe_force_max=safe_force_max,
        friction_coeff=0.8,
        is_fragile=True,
        material="paper",
    )


def _analysis(
    *,
    slip_risk: float = 0.0,
    slip_confirmed: bool = False,
    finger_fz: dict[TactileSensorId, float] | None = None,
) -> TactileAnalysis:
    forces = finger_fz or {
        TactileSensorId.THUMB: 0.30,
        TactileSensorId.FOREFINGER: 0.15,
        TactileSensorId.MIDDLE_FINGER: 0.10,
    }
    return TactileAnalysis(
        variance=0.0,
        slip_risk=slip_risk,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=slip_confirmed,
        finger_fz=forces,
        total_fz=sum(forces.values()),
    )


def test_torque_hold_planner_initializes_contact_ratios_from_snapshot():
    cfg = AdaptiveGraspConfig(
        active_fingers={
            TactileSensorId.THUMB,
            TactileSensorId.FOREFINGER,
            TactileSensorId.MIDDLE_FINGER,
        },
        torque_hold_min_contact_ratio=0.15,
    )
    planner = TorqueHoldPlanner(cfg, _profile(), _snapshot())

    assert sum(planner.contact_ratios.values()) == pytest.approx(1.0)
    assert planner.contact_ratios[TactileSensorId.THUMB] > planner.contact_ratios[TactileSensorId.FOREFINGER]
    assert planner.contact_ratios[TactileSensorId.FOREFINGER] > planner.contact_ratios[TactileSensorId.MIDDLE_FINGER]
    assert planner.contact_ratios[TactileSensorId.MIDDLE_FINGER] >= 0.15 - 1e-6


def test_torque_hold_planner_uses_uniform_ratios_when_snapshot_force_is_zero():
    cfg = AdaptiveGraspConfig(
        active_fingers={
            TactileSensorId.THUMB,
            TactileSensorId.FOREFINGER,
            TactileSensorId.MIDDLE_FINGER,
        },
    )
    planner = TorqueHoldPlanner(
        cfg,
        _profile(),
        _snapshot(
            finger_fz={
                TactileSensorId.THUMB: 0.0,
                TactileSensorId.FOREFINGER: 0.0,
                TactileSensorId.MIDDLE_FINGER: 0.0,
            },
            total_fz=0.0,
        ),
    )

    assert planner.contact_ratios == {
        TactileSensorId.THUMB: pytest.approx(1 / 3),
        TactileSensorId.FOREFINGER: pytest.approx(1 / 3),
        TactileSensorId.MIDDLE_FINGER: pytest.approx(1 / 3),
    }


def test_torque_hold_planner_initial_force_ref_uses_snapshot_margin_and_profile_bounds():
    cfg = AdaptiveGraspConfig(torque_hold_force_margin_n=0.10)

    planner = TorqueHoldPlanner(
        cfg,
        _profile(safe_force_min=0.5, safe_force_max=3.5),
        _snapshot(total_fz=0.55),
    )

    assert planner.F_ref_total == pytest.approx(0.65)


def test_torque_hold_planner_increases_force_ref_when_slip_risk_high():
    cfg = AdaptiveGraspConfig(
        torque_hold_slip_warning_threshold=0.40,
        torque_hold_slip_gain_n_per_s=0.20,
        torque_hold_max_rise_step_n=0.02,
    )
    planner = TorqueHoldPlanner(cfg, _profile(), _snapshot(total_fz=0.55))
    initial = planner.F_ref_total

    planner.compute(_analysis(slip_risk=0.90), dt=1.0)

    assert planner.F_ref_total == pytest.approx(initial + 0.02)


def test_torque_hold_planner_does_not_repeat_confirmed_boost():
    cfg = AdaptiveGraspConfig(torque_hold_confirmed_boost_n=0.05)
    planner = TorqueHoldPlanner(cfg, _profile(), _snapshot(total_fz=0.55))

    planner.compute(_analysis(slip_risk=0.0, slip_confirmed=True), dt=0.02)
    boosted = planner.F_ref_total
    planner.compute(_analysis(slip_risk=0.0, slip_confirmed=True), dt=0.02)

    assert planner.F_ref_total == pytest.approx(boosted)


def test_torque_hold_planner_continues_slow_rise_when_confirmed_slip_stays_risky():
    cfg = AdaptiveGraspConfig(
        torque_hold_slip_warning_threshold=0.40,
        torque_hold_slip_gain_n_per_s=0.20,
        torque_hold_max_rise_step_n=0.02,
        torque_hold_confirmed_boost_n=0.05,
    )
    planner = TorqueHoldPlanner(cfg, _profile(), _snapshot(total_fz=0.55))

    planner.compute(_analysis(slip_risk=0.90, slip_confirmed=True), dt=1.0)
    first = planner.F_ref_total
    planner.compute(_analysis(slip_risk=0.90, slip_confirmed=True), dt=1.0)

    assert planner.F_ref_total == pytest.approx(first + 0.02)


def test_torque_hold_planner_decays_force_ref_when_stable():
    cfg = AdaptiveGraspConfig(
        torque_hold_stable_threshold=0.20,
        torque_hold_stable_decay_delay_s=0.10,
        torque_hold_decay_rate_n_per_s=0.02,
    )
    planner = TorqueHoldPlanner(cfg, _profile(), _snapshot(total_fz=1.0))
    initial = planner.F_ref_total

    planner.compute(_analysis(slip_risk=0.0), dt=0.10)
    planner.compute(_analysis(slip_risk=0.0), dt=0.10)

    assert planner.F_ref_total < initial
    assert planner.F_ref_total >= planner._minimum_force_ref()


def test_torque_hold_planner_returns_base_torque_when_force_error_zero():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        adaptive_hold_torque=5,
        torque_hold_force_margin_n=0.0,
        torque_hold_K_p=5.0,
        torque_hold_K_i=0.0,
        torque_hold_K_d=0.0,
    )
    planner = TorqueHoldPlanner(
        cfg,
        _profile(safe_force_min=0.0, safe_force_max=3.5),
        _snapshot(finger_fz={TactileSensorId.THUMB: 0.5}, total_fz=0.5),
    )

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 0.5}),
        dt=0.02,
    )

    assert decision.finger_torques == {TactileSensorId.THUMB: pytest.approx(5.0)}


def test_torque_hold_planner_increases_torque_for_low_force_finger():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
        adaptive_hold_torque=5,
        torque_hold_force_margin_n=0.0,
        torque_hold_K_p=5.0,
        torque_hold_K_i=0.0,
        torque_hold_K_d=0.0,
    )
    planner = TorqueHoldPlanner(
        cfg,
        _profile(safe_force_min=0.0, safe_force_max=3.5),
        _snapshot(
            finger_fz={
                TactileSensorId.THUMB: 0.5,
                TactileSensorId.FOREFINGER: 0.5,
            },
            total_fz=1.0,
        ),
    )

    decision = planner.compute(
        _analysis(
            finger_fz={
                TactileSensorId.THUMB: 0.2,
                TactileSensorId.FOREFINGER: 0.5,
            },
        ),
        dt=0.02,
    )

    assert decision.finger_torques[TactileSensorId.THUMB] > 5.0
    assert decision.finger_torques[TactileSensorId.FOREFINGER] == pytest.approx(5.0)
