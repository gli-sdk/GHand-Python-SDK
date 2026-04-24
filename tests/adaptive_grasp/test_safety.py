import math
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.safety import SafetyMonitor, SafetyStatus, SafetyReport
from xiaoyao.adaptive_grasp.states import GraspState
from xiaoyao.dexhand import Joint, JointId


def test_sensor_fault_on_data_spike():
    cfg = AdaptiveGraspConfig()
    monitor = SafetyMonitor(cfg)

    # 先建立基线
    baseline = [Joint(id=JointId.THUMB_MCP, angle=0.0)]
    monitor.check(tactile_data={"thumb": type("T", (), {"get_force_z": lambda self: 2.0})()}, joint_feedback=baseline, state=GraspState.CLOSING_TO_CONTACT)

    # 模拟同一关节角度跳变 > 30°
    spike = [Joint(id=JointId.THUMB_MCP, angle=math.radians(35.0))]
    report = monitor.check(tactile_data={"thumb": type("T", (), {"get_force_z": lambda self: 2.0})()}, joint_feedback=spike, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "sensor_fault"


def test_empty_grasp_when_closing_with_no_contact():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    # 设置 CLOSING 启动时的 baseline（0°）
    monitor.set_closing_baseline([Joint(id=JointId.THUMB_MCP, angle=0.0)])

    tactile = {  # 总法向力 < threshold
        "thumb": type("T", (), {"get_force_z": lambda self: 0.1})(),
    }
    # 关节从 0° 运动到 20°，变化量 20° > 10° 阈值
    joints = [Joint(id=JointId.THUMB_MCP, angle=math.radians(20.0))]
    report = monitor.check(tactile_data=tactile, joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "empty_grasp"


def test_object_dropped_when_contact_lost():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    # 第一次有接触
    tactile_before = {"thumb": type("T", (), {"get_force_z": lambda self: 2.0})()}
    monitor.check(tactile_data=tactile_before, joint_feedback=None, state=GraspState.ADAPTIVE_HOLD)

    # 第二次无接触
    tactile_after = {"thumb": type("T", (), {"get_force_z": lambda self: 0.0})()}
    report = monitor.check(tactile_data=tactile_after, joint_feedback=None, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "object_dropped"


def test_sensor_fault_with_joint_objects():
    cfg = AdaptiveGraspConfig()
    monitor = SafetyMonitor(cfg)

    # 先建立基线
    baseline = [Joint(id=JointId.THUMB_MCP, angle=0.0)]
    monitor.check(tactile_data={"thumb": type("T", (), {"get_force_z": lambda self: 2.0})()}, joint_feedback=baseline, state=GraspState.CLOSING_TO_CONTACT)

    # 同一关节角度跳变 > 30°
    spike = [Joint(id=JointId.THUMB_MCP, angle=math.radians(35.0))]
    report = monitor.check(tactile_data={"thumb": type("T", (), {"get_force_z": lambda self: 2.0})()}, joint_feedback=spike, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "sensor_fault"


def test_empty_grasp_with_joint_objects():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    # 设置 CLOSING 启动 baseline 为 0°
    monitor.set_closing_baseline([Joint(id=JointId.THUMB_MCP, angle=0.0)])

    tactile = {"thumb": type("T", (), {"get_force_z": lambda self: 0.1})()}
    joints = [Joint(id=JointId.THUMB_MCP, angle=math.radians(20.0))]
    report = monitor.check(tactile_data=tactile, joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "empty_grasp"


def test_empty_grasp_respects_baseline():
    """验证空抓判断基于相对变化量：baseline 15°，当前 20°，变化仅 5°，不应误判。"""
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    # baseline 15°，当前 20°，变化量 5° < 10° 阈值
    monitor.set_closing_baseline([Joint(id=JointId.THUMB_MCP, angle=math.radians(15.0))])

    tactile = {"thumb": type("T", (), {"get_force_z": lambda self: 0.1})()}
    joints = [Joint(id=JointId.THUMB_MCP, angle=math.radians(20.0))]
    report = monitor.check(tactile_data=tactile, joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.OK
