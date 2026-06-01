import pytest

from adaptive_grasp.config import AdaptiveGraspConfig
from adaptive_grasp.force_reference_planner import ForceReferenceDecision
from adaptive_grasp.tactility import TactileAnalysis
from adaptive_grasp.torque_hold_planner import TorqueHoldPlanner
from ghand import TactileSensorId


def _analysis(
    *,
    finger_fz: dict[TactileSensorId, float] | None = None,
) -> TactileAnalysis:
    forces = finger_fz or {
        TactileSensorId.THUMB: 0.5,
        TactileSensorId.FF: 0.5,
    }
    return TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz=forces,
        total_fz=sum(forces.values()),
    )


def _reference(
    *,
    force_refs: dict[TactileSensorId, float] | None = None,
) -> ForceReferenceDecision:
    refs = force_refs or {
        TactileSensorId.THUMB: 0.5,
        TactileSensorId.FF: 0.5,
    }
    return ForceReferenceDecision(
        force_refs=refs,
        contact_ratios={finger: 1.0 / len(refs) for finger in refs},
        F_ref_total=sum(refs.values()),
    )


def test_torque_hold_planner_returns_base_torque_when_force_error_zero():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        torque_hold_base_torque=5,
        torque_hold_K_p=5.0,
        torque_hold_K_i=0.0,
        torque_hold_K_d=0.0,
    )
    planner = TorqueHoldPlanner(cfg)

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 0.5}),
        _reference(force_refs={TactileSensorId.THUMB: 0.5}),
        dt=0.02,
    )

    assert decision.finger_torques == {TactileSensorId.THUMB: pytest.approx(5.0)}
    assert decision.force_refs == {TactileSensorId.THUMB: pytest.approx(0.5)}
    assert decision.F_ref_total == pytest.approx(0.5)


def test_torque_hold_planner_increases_torque_for_low_force_finger():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FF},
        torque_hold_base_torque=5,
        torque_hold_K_p=5.0,
        torque_hold_K_i=0.0,
        torque_hold_K_d=0.0,
    )
    planner = TorqueHoldPlanner(cfg)

    decision = planner.compute(
        _analysis(
            finger_fz={
                TactileSensorId.THUMB: 0.2,
                TactileSensorId.FF: 0.5,
            },
        ),
        _reference(
            force_refs={
                TactileSensorId.THUMB: 0.5,
                TactileSensorId.FF: 0.5,
            },
        ),
        dt=0.02,
    )

    assert decision.finger_torques[TactileSensorId.THUMB] > 5.0
    assert decision.finger_torques[TactileSensorId.FF] == pytest.approx(5.0)


def test_torque_hold_planner_can_command_negative_torque_for_high_force_finger():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        torque_hold_base_torque=5,
        torque_hold_K_p=5.0,
        torque_hold_K_i=0.0,
        torque_hold_K_d=0.0,
    )
    planner = TorqueHoldPlanner(cfg)

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 4.0}),
        _reference(force_refs={TactileSensorId.THUMB: 0.5}),
        dt=0.02,
    )

    assert decision.finger_torques[TactileSensorId.THUMB] < 0.0


def test_torque_hold_planner_clips_torque_to_config_max():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB},
        torque_hold_base_torque=5,
        max_torque=8,
        torque_hold_K_p=100.0,
        torque_hold_K_i=0.0,
        torque_hold_K_d=0.0,
    )
    planner = TorqueHoldPlanner(cfg)

    decision = planner.compute(
        _analysis(finger_fz={TactileSensorId.THUMB: 0.0}),
        _reference(force_refs={TactileSensorId.THUMB: 1.0}),
        dt=0.02,
    )

    assert decision.finger_torques[TactileSensorId.THUMB] == pytest.approx(8.0)
