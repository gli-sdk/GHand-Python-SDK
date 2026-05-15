import math
from unittest.mock import MagicMock
import pytest
from adaptive_grasp import AdaptiveGraspConfig
from adaptive_grasp.force_reference_planner import ForceReferenceDecision
from adaptive_grasp.adaptive_hold_loop import HoldController, HoldResult, HoldStepResult
from adaptive_grasp.joint_builder import JointCommandBuilder
from adaptive_grasp.position_hold_planner import ForceDecision
from adaptive_grasp.tactility import TactileAnalysis
from adaptive_grasp.torque_hold_planner import TorqueHoldDecision
from adaptive_grasp.safety import SafetyReport, SafetyStatus
from xiaoyao.dexhand import CtrlMode, Joint, JointId, TactileSensorId


class _MockHand:
    def __init__(self):
        self.calls = []

    def move_joints(self, joints, mode=None):
        self.calls.append({"mode": mode, "joints": list(joints)})
        return True


def test_hold_step_sends_position_payload_from_hold_decision(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        slip_variance_threshold=0.1,
        max_normal_force_per_finger_n=1.0,
    )
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = []
    sensor.sample_time_s = None
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.5, slip_risk=1.0, direction_distance=0.0,
        friction_utilization=0.0, slip_confirmed=True,
        finger_fz={}, total_fz=0.4,
    )
    visualizer = None
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    position_hold_planner = MagicMock()
    position_hold_planner.compute.return_value = {
        TactileSensorId.THUMB: ForceDecision(
            control_u=0.0,
            next_torque=29,
            target_angles={},
            is_fragile_mode=False,
            next_speed=17,
        ),
    }
    force_reference_planner = MagicMock()
    force_reference_planner.compute.return_value = ForceReferenceDecision(
        force_refs={TactileSensorId.THUMB: 0.5},
        contact_ratios={TactileSensorId.THUMB: 1.0},
        F_ref_total=0.5,
    )
    controller = HoldController(
        hand, sensor, safety, tactile, visualizer,
        joint_builder, cfg, current_torque=10,
        force_reference_planner=force_reference_planner,
        position_hold_planner=position_hold_planner,
    )

    result = controller.run_step(current_time=0.0)

    assert result.result == HoldResult.CONTINUE
    assert len(hand.calls) == 1
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    for joint in hand.calls[0]["joints"]:
        assert joint.speed == 17
        assert joint.torque == 29


def test_hold_step_fault_triggers_release():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(enable_fault_release_fallback=True)
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.FAULT)
    tactile = MagicMock()
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
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
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
    )

    result = controller.run_step(current_time=0.0)

    assert result.result == HoldResult.ERROR


def test_hold_step_error_after_consecutive_failures():
    hand = _MockHand()
    hand.move_joints = lambda *args, **kwargs: False
    cfg = AdaptiveGraspConfig(control_period_s=0.01)
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = []
    sensor.sample_time_s = None
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.0, slip_risk=0.0, direction_distance=0.0,
        friction_utilization=0.0, slip_confirmed=False,
        finger_fz={}, total_fz=0.0,
    )
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
    )

    assert controller.run_step(0.0).result == HoldResult.CONTINUE
    assert controller.run_step(0.0).result == HoldResult.CONTINUE
    assert controller.run_step(0.0).result == HoldResult.ERROR


def test_hold_step_error_uses_configured_move_failure_limit():
    hand = _MockHand()
    hand.move_joints = lambda *args, **kwargs: False
    cfg = AdaptiveGraspConfig(
        adaptive_hold_move_failure_limit=2,
        control_period_s=0.01,
    )
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = []
    sensor.sample_time_s = None
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.0, slip_risk=0.0, direction_distance=0.0,
        friction_utilization=0.0, slip_confirmed=False,
        finger_fz={}, total_fz=0.0,
    )
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
    )

    assert controller.run_step(0.0).result == HoldResult.CONTINUE
    assert controller.run_step(0.0).result == HoldResult.ERROR


def test_hold_step_can_send_torque_payload_to_active_mcp_pip_joints():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        hold_command_mode="torque",
        torque_hold_base_torque=20,
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
    )
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = []
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={},
        total_fz=0.0,
    )
    joint_builder = JointCommandBuilder(
        cfg,
        (JointId.THUMB_PIP, JointId.THUMB_MCP, JointId.FF_PIP, JointId.FF_MCP),
    )
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
    )

    result = controller.run_step(current_time=0.0)

    joint_map = {joint.id: joint for joint in hand.calls[0]["joints"]}
    assert result.result == HoldResult.CONTINUE
    assert result.current_torque == 20
    assert hand.calls[0]["mode"] == CtrlMode.TORQUE
    for joint_id in (JointId.THUMB_PIP, JointId.THUMB_MCP, JointId.FF_PIP, JointId.FF_MCP):
        assert joint_map[joint_id].torque == 20


def test_torque_hold_loop_uses_torque_hold_planner_per_finger_torques():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        hold_command_mode="torque",
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FOREFINGER},
        control_period_s=0.02,
    )
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = []
    sensor.sample_time_s = 10.0
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    analysis = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={},
        total_fz=0.0,
    )
    tactile = MagicMock()
    tactile.update.return_value = analysis
    force_reference_planner = MagicMock()
    force_reference = ForceReferenceDecision(
        force_refs={TactileSensorId.THUMB: 0.5, TactileSensorId.FOREFINGER: 0.5},
        contact_ratios={TactileSensorId.THUMB: 0.5, TactileSensorId.FOREFINGER: 0.5},
        F_ref_total=1.0,
    )
    force_reference_planner.compute.return_value = force_reference
    torque_hold_planner = MagicMock()
    decision = TorqueHoldDecision(
        finger_torques={
            TactileSensorId.THUMB: 6.2,
            TactileSensorId.FOREFINGER: 8.1,
        },
        force_refs={},
        contact_ratios={},
        F_ref_total=1.0,
    )
    torque_hold_planner.compute.return_value = decision
    joint_builder = JointCommandBuilder(
        cfg,
        (JointId.THUMB_PIP, JointId.THUMB_MCP, JointId.FF_PIP, JointId.FF_MCP),
    )
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
        torque_hold_planner=torque_hold_planner,
        force_reference_planner=force_reference_planner,
    )

    result = controller.run_step(current_time=0.0)

    joint_map = {joint.id: joint for joint in hand.calls[0]["joints"]}
    force_reference_planner.compute.assert_called_once_with(
        analysis,
        dt=cfg.control_period_s,
    )
    torque_hold_planner.compute.assert_called_once_with(
        analysis,
        force_reference,
        dt=cfg.control_period_s,
    )
    assert result.result == HoldResult.CONTINUE
    assert result.torque_hold_decision is decision
    assert result.current_torque == 8
    assert hand.calls[0]["mode"] == CtrlMode.TORQUE
    assert joint_map[JointId.THUMB_PIP].torque == 6
    assert joint_map[JointId.THUMB_MCP].torque == 6
    assert joint_map[JointId.FF_PIP].torque == 8
    assert joint_map[JointId.FF_MCP].torque == 8


def test_position_hold_loop_uses_position_hold_planner_with_force_reference():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        hold_command_mode="position",
        active_fingers={TactileSensorId.THUMB},
        control_period_s=0.02,
    )
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = [Joint(id=JointId.THUMB_PIP, angle=0.10)]
    sensor.sample_time_s = 10.0
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    analysis = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
    )
    tactile = MagicMock()
    tactile.update.return_value = analysis
    force_reference_planner = MagicMock()
    force_reference = ForceReferenceDecision(
        force_refs={TactileSensorId.THUMB: 0.7},
        contact_ratios={TactileSensorId.THUMB: 1.0},
        F_ref_total=0.7,
    )
    force_reference_planner.compute.return_value = force_reference
    position_hold_planner = MagicMock()
    decisions = {
        TactileSensorId.THUMB: ForceDecision(
            control_u=0.1,
            next_torque=23,
            next_speed=7,
            target_angles={JointId.THUMB_PIP: 0.12},
            is_fragile_mode=False,
        )
    }
    position_hold_planner.compute.return_value = decisions
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
        force_reference_planner=force_reference_planner,
        position_hold_planner=position_hold_planner,
    )

    result = controller.run_step(current_time=0.0)

    joint_map = {joint.id: joint for joint in hand.calls[0]["joints"]}
    force_reference_planner.compute.assert_called_once_with(
        analysis,
        dt=cfg.control_period_s,
    )
    position_hold_planner.compute.assert_called_once_with(
        analysis,
        {JointId.THUMB_PIP: 0.10},
        force_reference,
        dt=cfg.control_period_s,
    )
    assert result.force_decisions == decisions
    assert result.current_torque == 23
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    assert joint_map[JointId.THUMB_PIP].angle == pytest.approx(0.12)
    assert joint_map[JointId.THUMB_PIP].speed == 7


def test_hold_loop_notifies_observer_with_force_reference():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        hold_command_mode="position",
        active_fingers={TactileSensorId.THUMB},
        control_period_s=0.02,
    )
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = [Joint(id=JointId.THUMB_PIP, angle=0.10)]
    sensor.sample_time_s = 10.0
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    analysis = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
    )
    tactile = MagicMock()
    tactile.update.return_value = analysis
    observer = MagicMock()
    force_reference_planner = MagicMock()
    force_reference = ForceReferenceDecision(
        force_refs={TactileSensorId.THUMB: 0.7},
        contact_ratios={TactileSensorId.THUMB: 1.0},
        F_ref_total=0.7,
    )
    force_reference_planner.compute.return_value = force_reference
    position_hold_planner = MagicMock()
    position_hold_planner.compute.return_value = {
        TactileSensorId.THUMB: ForceDecision(
            control_u=0.0,
            next_torque=23,
            target_angles={JointId.THUMB_PIP: 0.10},
            is_fragile_mode=False,
        )
    }
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
        force_reference_planner=force_reference_planner,
        position_hold_planner=position_hold_planner,
        observer=observer,
    )

    controller.run_step(current_time=0.0)

    observer.on_hold_step.assert_called_once_with(
        tactile_data=sensor.tactile_data,
        analysis=analysis,
        current_angles={JointId.THUMB_PIP: 0.10},
        current_time=0.0,
        force_refs={TactileSensorId.THUMB: 0.7},
    )


def test_hold_step_uses_contact_snapshot_when_joint_feedback_missing():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig()
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = None
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={},
        total_fz=0.0,
    )
    contact_angles = {
        JointId.THUMB_PIP: 0.12,
        JointId.FF_PIP: 0.34,
    }
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
        contact_joint_angles=contact_angles,
    )

    result = controller.run_step(current_time=0.0)

    joint_map = {joint.id: joint for joint in hand.calls[0]["joints"]}
    assert result.result == HoldResult.CONTINUE
    assert joint_map[JointId.THUMB_PIP].angle == pytest.approx(0.12)
    assert joint_map[JointId.FF_PIP].angle == pytest.approx(0.34)


def test_position_hold_clamps_target_angles_to_contact_snapshot_window():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig()
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = [
        Joint(id=JointId.THUMB_PIP, angle=0.20),
        Joint(id=JointId.FF_PIP, angle=0.40),
    ]
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=True,
        finger_fz={},
        total_fz=0.0,
    )
    force_reference_planner = MagicMock()
    force_reference_planner.compute.return_value = ForceReferenceDecision(
        force_refs={TactileSensorId.THUMB: 0.5},
        contact_ratios={TactileSensorId.THUMB: 1.0},
        F_ref_total=0.5,
    )
    position_hold_planner = MagicMock()
    position_hold_planner.compute.return_value = {
        TactileSensorId.THUMB: ForceDecision(
            control_u=0.0,
            next_torque=23,
            target_angles={
                JointId.THUMB_PIP: 0.20 + math.radians(10),
                JointId.FF_PIP: 0.40 - math.radians(10),
            },
            is_fragile_mode=False,
            next_speed=17,
        ),
    }
    contact_angles = {
        JointId.THUMB_PIP: 0.20,
        JointId.FF_PIP: 0.40,
    }
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
        contact_joint_angles=contact_angles,
        force_reference_planner=force_reference_planner,
        position_hold_planner=position_hold_planner,
    )

    result = controller.run_step(current_time=0.0)

    joint_map = {joint.id: joint for joint in hand.calls[0]["joints"]}
    assert result.result == HoldResult.CONTINUE
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    assert joint_map[JointId.THUMB_PIP].angle == pytest.approx(0.20 + math.radians(10))
    assert joint_map[JointId.FF_PIP].angle == pytest.approx(0.40 - math.radians(10))


def test_position_hold_clamps_target_angles_to_configured_contact_snapshot_window():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        contact_angle_guard_margin_rad=math.radians(5),
    )
    sensor = MagicMock()
    sensor.tactile_data = {}
    sensor.joint_feedback = [
        Joint(id=JointId.THUMB_PIP, angle=0.20),
        Joint(id=JointId.FF_PIP, angle=0.40),
    ]
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.0,
        slip_risk=0.0,
        direction_distance=0.0,
        friction_utilization=0.0,
        slip_confirmed=True,
        finger_fz={},
        total_fz=0.0,
    )
    force_reference_planner = MagicMock()
    force_reference_planner.compute.return_value = ForceReferenceDecision(
        force_refs={TactileSensorId.THUMB: 0.5},
        contact_ratios={TactileSensorId.THUMB: 1.0},
        F_ref_total=0.5,
    )
    position_hold_planner = MagicMock()
    position_hold_planner.compute.return_value = {
        TactileSensorId.THUMB: ForceDecision(
            control_u=0.0,
            next_torque=23,
            target_angles={
                JointId.THUMB_PIP: 0.20 + math.radians(10),
                JointId.FF_PIP: 0.40 - math.radians(10),
            },
            is_fragile_mode=False,
            next_speed=17,
        ),
    }
    contact_angles = {
        JointId.THUMB_PIP: 0.20,
        JointId.FF_PIP: 0.40,
    }
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = HoldController(
        hand, sensor, safety, tactile, None,
        joint_builder, cfg, current_torque=10,
        contact_joint_angles=contact_angles,
        force_reference_planner=force_reference_planner,
        position_hold_planner=position_hold_planner,
    )

    result = controller.run_step(current_time=0.0)

    joint_map = {joint.id: joint for joint in hand.calls[0]["joints"]}
    assert result.result == HoldResult.CONTINUE
    assert joint_map[JointId.THUMB_PIP].angle == pytest.approx(0.20 + math.radians(5))
    assert joint_map[JointId.FF_PIP].angle == pytest.approx(0.40 - math.radians(5))

