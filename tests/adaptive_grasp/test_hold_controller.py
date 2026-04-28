import time
from unittest.mock import MagicMock
import pytest
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.force_planner import ForceDecision
from xiaoyao.adaptive_grasp.hold_controller import HoldController, HoldResult, HoldStepResult
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.adaptive_grasp.tactility import TactileAnalysis
from xiaoyao.adaptive_grasp.safety import SafetyReport, SafetyStatus
from xiaoyao.dexhand import CtrlMode, JointId, TactileSensorId


class _MockHand:
    def __init__(self):
        self.calls = []

    def move_joints(self, joints, mode=None):
        self.calls.append({"mode": mode, "joints": list(joints)})
        return True


def test_hold_step_sends_position_payload_with_config_limits(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        position_speed_limit=17,
        position_torque_limit=29,
        variance_threshold=0.1,
        max_normal_force_per_finger=1.0,
    )
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.5, slip_risk=1.0, direction_distance=0.0,
        friction_utilization=0.0, slip_confirmed=True,
        finger_fz={}, total_fz=0.4,
    )
    force_planner = MagicMock()
    force_planner.compute.return_value = {}
    visualizer = None
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = HoldController(
        hand, sensor, safety, tactile, force_planner, visualizer,
        joint_builder, cfg, current_torque=10, get_time=time.monotonic,
    )

    result = controller.run_step(current_time=0.0)

    assert result.result == HoldResult.CONTINUE
    assert len(hand.calls) == 1
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    for joint in hand.calls[0]["joints"]:
        assert joint.speed == cfg.position_speed_limit
        assert 0 <= joint.torque <= cfg.position_torque_limit


def test_hold_step_fault_triggers_release():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(enable_fault_release_fallback=True)
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.FAULT)
    tactile = MagicMock()
    force_planner = None
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, force_planner, None,
        joint_builder, cfg, current_torque=10, get_time=time.monotonic,
    )

    result = controller.run_step(current_time=0.0)

    assert result.result == HoldResult.FAULT_RELEASE


def test_hold_step_fault_without_fallback_triggers_error():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(enable_fault_release_fallback=False)
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.FAULT)
    tactile = MagicMock()
    force_planner = None
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, force_planner, None,
        joint_builder, cfg, current_torque=10, get_time=time.monotonic,
    )

    result = controller.run_step(current_time=0.0)

    assert result.result == HoldResult.ERROR


def test_hold_step_error_after_consecutive_failures():
    hand = _MockHand()
    hand.move_joints = lambda *args, **kwargs: False
    cfg = AdaptiveGraspConfig(control_period_s=0.01)
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.0, slip_risk=0.0, direction_distance=0.0,
        friction_utilization=0.0, slip_confirmed=False,
        finger_fz={}, total_fz=0.0,
    )
    force_planner = None
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, force_planner, None,
        joint_builder, cfg, current_torque=10, get_time=time.monotonic,
    )

    assert controller.run_step(0.0).result == HoldResult.CONTINUE
    assert controller.run_step(0.0).result == HoldResult.CONTINUE
    assert controller.run_step(0.0).result == HoldResult.ERROR


def test_hold_step_reports_updated_torque_from_force_decision():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig()
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
    )
    force_planner = MagicMock()
    force_planner.compute.return_value = {
        TactileSensorId.THUMB: ForceDecision(
            control_u=0.0,
            next_torque=23,
            target_angles={JointId.THUMB_PIP: 0.1},
            is_fragile_mode=False,
        ),
    }
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, force_planner, None,
        joint_builder, cfg, current_torque=10, get_time=time.monotonic,
    )

    result = controller.run_step(current_time=0.0)

    assert result.result == HoldResult.CONTINUE
    assert result.current_torque == 23
