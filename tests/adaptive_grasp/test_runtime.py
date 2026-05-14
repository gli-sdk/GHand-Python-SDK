from dataclasses import dataclass

import pytest

from xiaoyao.adaptive_grasp.adaptive_hold_loop import HoldResult, HoldStepResult
from xiaoyao.adaptive_grasp.runtime import AdaptiveGraspRuntime, GraspState


@dataclass
class _SensorStub:
    tactile_data: object = None
    age_s: float = 0.0

    def data_age_s(self, current_time: float) -> float:
        return self.age_s + current_time


def test_reset_for_grasp_clears_transient_state_and_starts_idle():
    runtime = AdaptiveGraspRuntime(
        state=GraspState.ADAPTIVE_HOLD,
        running=False,
        current_torque=42,
        object_profile=object(),
        adaptive_hold_started_at=1.0,
        last_contact_snapshot=object(),
        last_tactile_analysis=object(),
        last_safety_report=object(),
        last_force_decisions={"thumb": object()},
        last_torque_hold_decision=object(),
        last_tactile_data_age_s=0.2,
        last_control_step_start_s=2.0,
        last_control_cycle_s=0.03,
        last_control_cycle_jitter_s=0.01,
    )

    runtime.reset_for_grasp()

    assert runtime.running is True
    assert runtime.state == GraspState.IDLE
    assert runtime.current_torque == 0
    assert runtime.object_profile is None
    assert runtime.adaptive_hold_started_at is None
    assert runtime.last_contact_snapshot is None
    assert runtime.last_tactile_analysis is None
    assert runtime.last_safety_report is None
    assert runtime.last_force_decisions is None
    assert runtime.last_torque_hold_decision is None
    assert runtime.last_tactile_data_age_s is None
    assert runtime.last_control_step_start_s is None
    assert runtime.last_control_cycle_s is None
    assert runtime.last_control_cycle_jitter_s is None


def test_update_control_cycle_timing_records_cycle_and_jitter():
    runtime = AdaptiveGraspRuntime()

    runtime.update_control_cycle_timing(10.0, control_period_s=0.02)
    runtime.update_control_cycle_timing(10.03, control_period_s=0.02)

    assert runtime.last_control_step_start_s == 10.03
    assert runtime.last_control_cycle_s == pytest.approx(0.03)
    assert runtime.last_control_cycle_jitter_s == pytest.approx(0.01)


def test_record_hold_step_stores_step_outputs_torque_and_data_age():
    runtime = AdaptiveGraspRuntime(current_torque=3)
    tactile_analysis = object()
    safety_report = object()
    force_decisions = {"index": object()}
    torque_hold_decision = object()
    sensor = _SensorStub(tactile_data={"index": object()}, age_s=0.1)
    step = HoldStepResult(
        result=HoldResult.CONTINUE,
        tactile_analysis=tactile_analysis,
        safety_report=safety_report,
        force_decisions=force_decisions,
        torque_hold_decision=torque_hold_decision,
        current_torque=7,
    )

    runtime.record_hold_step(step, sensor, 12.0)

    assert runtime.last_tactile_analysis is tactile_analysis
    assert runtime.last_safety_report is safety_report
    assert runtime.last_force_decisions is force_decisions
    assert runtime.last_torque_hold_decision is torque_hold_decision
    assert runtime.current_torque == 7
    assert runtime.last_tactile_data_age_s == 12.1


def test_record_hold_step_clears_data_age_when_tactile_data_missing():
    runtime = AdaptiveGraspRuntime()
    sensor = _SensorStub(tactile_data=None, age_s=0.1)
    step = HoldStepResult(result=HoldResult.CONTINUE)

    runtime.record_hold_step(step, sensor, 12.0)

    assert runtime.last_tactile_data_age_s is None


def test_grasp_state_is_exported_from_runtime_and_package():
    from xiaoyao.adaptive_grasp import GraspState as PackageGraspState

    assert PackageGraspState is GraspState
