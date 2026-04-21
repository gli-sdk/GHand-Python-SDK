import math
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.safety import SafetyMonitor, SafetyStatus, SafetyReport
from xiaoyao.adaptive_grasp.states import GraspState
from xiaoyao.dexhand import JointId


def test_sensor_fault_on_data_spike():
    cfg = AdaptiveGraspConfig()
    monitor = SafetyMonitor(cfg)

    # 模拟角度跳变 > 30°
    joints = [{"id": JointId.THUMB_MCP, "angle": 0.0}, {"id": JointId.THUMB_MCP, "angle": math.radians(35.0)}]
    report = monitor.check(tactile_data=None, joint_feedback=joints, state=GraspState.CLOSING)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "sensor_fault"


def test_empty_grasp_when_closing_with_no_contact():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    tactile = {  # 总法向力 < threshold
        "thumb": type("T", (), {"get_force_z": lambda self: 0.1})(),
    }
    # joint 动作角度大于阈值
    joints = [{"id": JointId.THUMB_MCP, "angle": math.radians(20.0)}]
    report = monitor.check(tactile_data=tactile, joint_feedback=joints, state=GraspState.CLOSING)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "empty_grasp"


def test_object_dropped_when_contact_lost():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    # 第一次有接触
    tactile_before = {"thumb": type("T", (), {"get_force_z": lambda self: 2.0})()}
    monitor.check(tactile_data=tactile_before, joint_feedback=None, state=GraspState.ADAPTIVE_HOLDING)

    # 第二次无接触
    tactile_after = {"thumb": type("T", (), {"get_force_z": lambda self: 0.0})()}
    report = monitor.check(tactile_data=tactile_after, joint_feedback=None, state=GraspState.ADAPTIVE_HOLDING)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "object_dropped"
