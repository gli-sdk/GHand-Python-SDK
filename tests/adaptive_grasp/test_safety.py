import math
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.safety import SafetyMonitor, SafetyStatus, SafetyReport
from xiaoyao.adaptive_grasp.states import GraspState
from xiaoyao.dexhand import Joint, JointId


def test_sensor_fault_on_joint_feedback_missing():
    cfg = AdaptiveGraspConfig()
    monitor = SafetyMonitor(cfg)
    report = monitor.check(tactile_data=None, joint_feedback=None, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "sensor_fault"


def test_empty_grasp_when_closing_with_no_contact():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)
    monitor.set_closing_baseline([Joint(id=JointId.THUMB_MCP, angle=0.0)])

    joints = [Joint(id=JointId.THUMB_MCP, angle=math.radians(35.0))]
    report = monitor.is_grasp_empty(joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "empty_grasp"


def test_object_dropped_when_contact_lost():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    baseline_joints = [Joint(id=JointId.THUMB_MCP, angle=0.0)]
    tactile_before = {"thumb": type("T", (), {"get_force_z": lambda self: 2.0})()}
    monitor.check(tactile_data=tactile_before, joint_feedback=baseline_joints, state=GraspState.ADAPTIVE_HOLD)

    tactile_after = {"thumb": type("T", (), {"get_force_z": lambda self: 0.0})()}
    report = monitor.check(tactile_data=tactile_after, joint_feedback=baseline_joints, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "object_dropped"


def test_empty_grasp_respects_baseline():
    """验证空抓判断基于相对变化量：baseline 15°，当前 20°，变化仅 5°，不应误判。"""
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    # baseline 15°，当前 20°，变化量 5° < 30° 阈值
    monitor.set_closing_baseline([Joint(id=JointId.THUMB_MCP, angle=math.radians(15.0))])

    tactile = {"thumb": type("T", (), {"get_force_z": lambda self: 0.1})()}
    joints = [Joint(id=JointId.THUMB_MCP, angle=math.radians(20.0))]
    report = monitor.check(tactile_data=tactile, joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.OK

