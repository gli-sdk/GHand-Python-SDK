import math
import pytest
from adaptive_grasp.config import AdaptiveGraspConfig
from adaptive_grasp.safety import SafetyMonitor, SafetyStatus, SafetyReport
from adaptive_grasp.runtime import GraspState
from ghand import JointCommand, JointId, TactileSensorId


def test_sensor_fault_on_joint_feedback_missing():
    cfg = AdaptiveGraspConfig()
    monitor = SafetyMonitor(cfg)
    report = monitor.check(tactile_data=None, joint_feedback=None, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "sensor_fault"


def test_empty_grasp_when_closing_with_no_contact():
    cfg = AdaptiveGraspConfig(closing_total_contact_threshold_n=1.0)
    monitor = SafetyMonitor(cfg)
    monitor.set_closing_baseline([JointCommand(id=JointId.THUMB_MCP, angle=0.0)])

    joints = [JointCommand(id=JointId.THUMB_MCP, angle=math.radians(35.0))]
    report = monitor.is_grasp_empty(joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "empty_grasp"


def test_tactile_missing_fault_cycles_are_configurable():
    cfg = AdaptiveGraspConfig(sensor_missing_fault_cycles=2)
    monitor = SafetyMonitor(cfg)
    joints = [JointCommand(id=JointId.THUMB_MCP, angle=0.0)]

    report = monitor.check(tactile_data=None, joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.WARN

    report = monitor.check(tactile_data=None, joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "sensor_fault"


def test_empty_grasp_angle_threshold_is_configurable():
    cfg = AdaptiveGraspConfig(empty_grasp_angle_threshold=math.radians(10.0))
    monitor = SafetyMonitor(cfg)
    monitor.set_closing_baseline([JointCommand(id=JointId.THUMB_MCP, angle=0.0)])

    joints = [JointCommand(id=JointId.THUMB_MCP, angle=math.radians(11.0))]
    report = monitor.is_grasp_empty(joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)

    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "empty_grasp"


def _touch(fz):
    return type("T", (), {"get_force_z": lambda self, fz=fz: fz})()


def _tactile_data(*fz_values):
    fingers = (
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
        TactileSensorId.RF,
        TactileSensorId.LF,
    )
    return {finger: _touch(fz) for finger, fz in zip(fingers, fz_values)}


def test_object_dropped_after_three_low_force_cycles(caplog):
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FF},
        closing_total_contact_threshold_n=1.0,
        drop_detect_debounce_cycles=3,
    )
    monitor = SafetyMonitor(cfg)

    baseline_joints = [JointCommand(id=JointId.THUMB_MCP, angle=0.0)]
    tactile_before = _tactile_data(2.0)
    monitor.check(tactile_data=tactile_before, joint_feedback=baseline_joints, state=GraspState.ADAPTIVE_HOLD)

    low_force = _tactile_data(0.19)
    report = monitor.check(tactile_data=low_force, joint_feedback=baseline_joints, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.OK

    report = monitor.check(tactile_data=low_force, joint_feedback=baseline_joints, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.OK

    report = monitor.check(tactile_data=low_force, joint_feedback=baseline_joints, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "object_dropped"
    assert "Object dropped" in caplog.text


def test_object_dropped_logs_active_finger_last_and_current_fz(caplog):
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FF},
        closing_total_contact_threshold_n=1.0,
        drop_detect_debounce_cycles=3,
    )
    monitor = SafetyMonitor(cfg)
    joints = [JointCommand(id=JointId.THUMB_MCP, angle=0.0)]

    monitor.check(
        tactile_data={
            TactileSensorId.THUMB: _touch(0.20),
            TactileSensorId.FF: _touch(0.15),
            TactileSensorId.MF: _touch(8.00),
        },
        joint_feedback=joints,
        state=GraspState.ADAPTIVE_HOLD,
    )

    low_force = {
        TactileSensorId.THUMB: _touch(0.00),
        TactileSensorId.FF: _touch(0.00),
        TactileSensorId.MF: _touch(8.00),
    }
    monitor.check(tactile_data=low_force, joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)
    monitor.check(tactile_data=low_force, joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)
    report = monitor.check(tactile_data=low_force, joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)

    assert report.status == SafetyStatus.FAULT
    assert (
        "Object dropped:\n"
        "  total: last_fz=0.35 current_fz=0.00 threshold=0.20\n"
        "  active_fingers:\n"
        "    thumb: last_fz=0.20 current_fz=0.00\n"
        "    forefinger: last_fz=0.15 current_fz=0.00"
    ) in caplog.text
    assert "middle_finger" not in caplog.text


def test_object_drop_counter_resets_when_force_recovers():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FF},
        closing_total_contact_threshold_n=1.0,
        drop_detect_debounce_cycles=3,
    )
    monitor = SafetyMonitor(cfg)
    joints = [JointCommand(id=JointId.THUMB_MCP, angle=0.0)]

    monitor.check(tactile_data=_tactile_data(2.0), joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)
    monitor.check(tactile_data=_tactile_data(0.19), joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)
    monitor.check(tactile_data=_tactile_data(0.21), joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)

    monitor.check(tactile_data=_tactile_data(0.19), joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)
    report = monitor.check(tactile_data=_tactile_data(0.19), joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.OK


def test_object_drop_threshold_is_configurable():
    cfg = AdaptiveGraspConfig(
        active_fingers={TactileSensorId.THUMB, TactileSensorId.FF},
        drop_detect_force_per_finger_n=0.2,
        drop_detect_debounce_cycles=1,
    )
    monitor = SafetyMonitor(cfg)
    joints = [JointCommand(id=JointId.THUMB_MCP, angle=0.0)]

    monitor.check(tactile_data=_tactile_data(1.0), joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)
    report = monitor.check(tactile_data=_tactile_data(0.39), joint_feedback=joints, state=GraspState.ADAPTIVE_HOLD)

    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "object_dropped"


def test_empty_grasp_respects_baseline():
    """验证空抓判断基于相对变化量：baseline 15°，当前 20°，变化仅 5°，不应误判。"""
    cfg = AdaptiveGraspConfig(closing_total_contact_threshold_n=1.0)
    monitor = SafetyMonitor(cfg)

    # baseline 15°，当前 20°，变化量 5° < 30° 阈值
    monitor.set_closing_baseline([JointCommand(id=JointId.THUMB_MCP, angle=math.radians(15.0))])

    tactile = {"thumb": type("T", (), {"get_force_z": lambda self: 0.1})()}
    joints = [JointCommand(id=JointId.THUMB_MCP, angle=math.radians(20.0))]
    report = monitor.is_grasp_empty(joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.OK
