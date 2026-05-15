import pytest

from adaptive_grasp.config import AdaptiveGraspConfig
from adaptive_grasp.force_reference_planner import ForceReferencePlanner
from adaptive_grasp.grasp_sequence import ContactSnapshot
from adaptive_grasp.object_profile import ObjectProfile
from adaptive_grasp.tactility import PerFingerAnalysis, TactileAnalysis
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
        position_hold_torque=5,
        position_hold_speed=5,
    )


def _analysis(
    *,
    slip_risk: float = 0.0,
    slip_confirmed: bool = False,
    finger_fz: dict[TactileSensorId, float] | None = None,
    per_finger_slip_risk: dict[TactileSensorId, float] | None = None,
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
        per_finger={
            finger: PerFingerAnalysis(
                variance=0.0,
                s_k=0.0,
                d_k=0.0,
                r_k=0.0,
                s_total=risk,
                slip_confirmed=False,
                fz=forces.get(finger, 0.0),
                fz_filtered=forces.get(finger, 0.0),
            )
            for finger, risk in (per_finger_slip_risk or {}).items()
        },
    )


def _three_finger_config(**overrides) -> AdaptiveGraspConfig:
    return AdaptiveGraspConfig(
        active_fingers={
            TactileSensorId.THUMB,
            TactileSensorId.FOREFINGER,
            TactileSensorId.MIDDLE_FINGER,
        },
        **overrides,
    )


def test_force_reference_initializes_contact_ratios_from_snapshot():
    cfg = _three_finger_config(force_ref_min_contact_ratio=0.15)
    planner = ForceReferencePlanner(cfg, _profile(), _snapshot())

    assert sum(planner.contact_ratios.values()) == pytest.approx(1.0)
    assert planner.contact_ratios[TactileSensorId.THUMB] > planner.contact_ratios[TactileSensorId.FOREFINGER]
    assert planner.contact_ratios[TactileSensorId.FOREFINGER] > planner.contact_ratios[TactileSensorId.MIDDLE_FINGER]
    assert planner.contact_ratios[TactileSensorId.MIDDLE_FINGER] >= 0.15 - 1e-6


def test_force_reference_uses_uniform_ratios_when_snapshot_force_is_zero():
    cfg = _three_finger_config()
    planner = ForceReferencePlanner(
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


def test_force_reference_initial_force_uses_snapshot_margin_and_profile_bounds():
    cfg = _three_finger_config(force_ref_margin_n=0.10)
    planner = ForceReferencePlanner(
        cfg,
        _profile(safe_force_min=0.5, safe_force_max=3.5),
        _snapshot(total_fz=0.55),
    )

    assert planner.F_ref_total == pytest.approx(0.65)


def test_force_reference_compute_returns_per_finger_refs():
    cfg = _three_finger_config(force_ref_margin_n=0.0)
    planner = ForceReferencePlanner(cfg, _profile(), _snapshot(total_fz=0.55))

    decision = planner.compute(_analysis(), dt=0.02)

    assert decision.F_ref_total == pytest.approx(0.55)
    assert decision.force_refs[TactileSensorId.THUMB] == pytest.approx(0.30)
    assert decision.force_refs[TactileSensorId.FOREFINGER] == pytest.approx(0.15)
    assert decision.force_refs[TactileSensorId.MIDDLE_FINGER] == pytest.approx(0.10)


def test_force_reference_increases_force_when_slip_risk_is_high():
    cfg = _three_finger_config(
        force_ref_slip_warning_threshold=0.40,
        force_ref_slip_gain_n_per_s=0.20,
        force_ref_max_rise_step_n=0.02,
    )
    planner = ForceReferencePlanner(cfg, _profile(), _snapshot(total_fz=0.55))
    initial = planner.F_ref_total

    planner.compute(_analysis(slip_risk=0.90), dt=1.0)

    assert planner.F_ref_total == pytest.approx(initial + 0.02)


def test_force_reference_increases_only_high_risk_finger_ref():
    cfg = _three_finger_config(
        force_ref_slip_warning_threshold=0.40,
        force_ref_slip_gain_n_per_s=0.20,
        force_ref_max_rise_step_n=0.02,
        force_ref_stable_threshold=0.20,
        force_ref_stable_decay_delay_s=999.0,
    )
    planner = ForceReferencePlanner(cfg, _profile(), _snapshot(total_fz=0.55))
    initial = planner.compute(_analysis(), dt=0.02).force_refs

    decision = planner.compute(
        _analysis(
            slip_risk=0.90,
            per_finger_slip_risk={
                TactileSensorId.THUMB: 0.90,
                TactileSensorId.FOREFINGER: 0.0,
                TactileSensorId.MIDDLE_FINGER: 0.0,
            },
        ),
        dt=1.0,
    )

    assert decision.force_refs[TactileSensorId.THUMB] == pytest.approx(
        initial[TactileSensorId.THUMB] + 0.02
    )
    assert decision.force_refs[TactileSensorId.FOREFINGER] == pytest.approx(
        initial[TactileSensorId.FOREFINGER]
    )
    assert decision.force_refs[TactileSensorId.MIDDLE_FINGER] == pytest.approx(
        initial[TactileSensorId.MIDDLE_FINGER]
    )
    assert decision.F_ref_total == pytest.approx(sum(decision.force_refs.values()))


def test_force_reference_does_not_repeat_confirmed_boost():
    cfg = _three_finger_config(force_ref_confirmed_boost_n=0.05)
    planner = ForceReferencePlanner(cfg, _profile(), _snapshot(total_fz=0.55))

    planner.compute(_analysis(slip_confirmed=True), dt=0.02)
    boosted = planner.F_ref_total
    planner.compute(_analysis(slip_confirmed=True), dt=0.02)

    assert planner.F_ref_total == pytest.approx(boosted)


def test_force_reference_decays_when_stable_after_delay():
    cfg = _three_finger_config(
        force_ref_stable_threshold=0.20,
        force_ref_stable_decay_delay_s=0.10,
        force_ref_decay_rate_n_per_s=0.02,
    )
    planner = ForceReferencePlanner(cfg, _profile(), _snapshot(total_fz=1.0))
    initial = planner.F_ref_total

    planner.compute(_analysis(slip_risk=0.0), dt=0.10)
    planner.compute(_analysis(slip_risk=0.0), dt=0.10)

    assert planner.F_ref_total < initial
    assert planner.F_ref_total >= planner.minimum_force_ref()


def test_force_reference_clamps_to_profile_safe_force_max():
    cfg = _three_finger_config(
        force_ref_slip_warning_threshold=0.40,
        force_ref_slip_gain_n_per_s=10.0,
        force_ref_max_rise_step_n=10.0,
    )
    planner = ForceReferencePlanner(
        cfg,
        _profile(safe_force_min=0.5, safe_force_max=0.7),
        _snapshot(total_fz=0.65),
    )

    decision = planner.compute(_analysis(slip_risk=1.0), dt=1.0)

    assert decision.F_ref_total == pytest.approx(0.7)
