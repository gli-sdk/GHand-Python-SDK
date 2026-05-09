import time
from unittest.mock import MagicMock
import pytest
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig, GraspState
from xiaoyao.adaptive_grasp.grasp_sequence import PhaseController, PhaseResult
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.dexhand import CtrlMode, JointId
from xiaoyao.dexhand import Joint, TactileSensorId


class _MockHand:
    def __init__(self):
        self.calls = []

    def move_joints(self, joints, mode=None):
        self.calls.append({"mode": mode, "joints": list(joints)})
        return True

    def stop(self):
        return None


class _FailingHand(_MockHand):
    def move_joints(self, joints, mode=None):
        self.calls.append({"mode": mode, "joints": list(joints)})
        return False


class _FakeTactileInfo:
    def __init__(self, fx: float, fy: float, fz: float, state: bool = True):
        self._fx = fx
        self._fy = fy
        self._fz = fz
        self.state = state

    def get_force_x(self) -> float:
        return self._fx

    def get_force_y(self) -> float:
        return self._fy

    def get_force_z(self) -> float:
        return self._fz

def test_phase_closing_contact_by_force(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        contact_threshold_z=0.5,
        phase_timeout=10.0,
        control_period_s=0.001,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from xiaoyao.adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    states = []
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=states.append,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = []
    sensor.sum_active_finger_normal_force.return_value = 4.0

    result = controller.run(is_running=lambda: True)

    assert result.success is True
    assert GraspState.CLOSING_TO_CONTACT in states


def test_phase_closing_uses_phase_closing_torque(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        base_torque=30,
        phase_closing_torque=4,
        contact_threshold_z=0.5,
        phase_timeout=10.0,
        control_period_s=0.001,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from xiaoyao.adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=lambda _state: None,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = []
    sensor.sum_active_finger_normal_force.return_value = 4.0

    result = controller.run(is_running=lambda: True)

    assert result.success is True
    closing_call = next(call for call in hand.calls if call["mode"] == CtrlMode.TORQUE)
    torque_by_joint = {joint.id: joint.torque for joint in closing_call["joints"]}
    assert torque_by_joint[JointId.THUMB_PIP] == 4
    assert torque_by_joint[JointId.FF_PIP] == 4
    assert result.final_torque == 4


def test_phase_closing_records_contact_joint_snapshot_by_force(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        contact_threshold_z=0.5,
        phase_timeout=10.0,
        control_period_s=0.001,
        phase_closing_torque=12,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from xiaoyao.adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, lambda: 10.0,
        on_state_change=lambda _state: None,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = [
        Joint(id=JointId.THUMB_PIP, angle=0.11),
        Joint(id=JointId.THUMB_MCP, angle=0.22),
        Joint(id=JointId.FF_PIP, angle=0.33),
    ]
    sensor.sum_active_finger_normal_force.return_value = 4.0

    result = controller.run(is_running=lambda: True)

    assert result.contact_snapshot is not None
    assert result.contact_snapshot.reason == "force_threshold"
    assert result.contact_snapshot.total_fz == pytest.approx(4.0)
    assert result.contact_snapshot.torque == 12
    assert result.contact_snapshot.timestamp_s == pytest.approx(10.0)
    assert result.contact_snapshot.joint_angles == {
        JointId.THUMB_PIP: pytest.approx(0.11),
        JointId.FF_PIP: pytest.approx(0.33),
    }


def test_phase_closing_records_contact_finger_force_snapshot_by_force(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        contact_threshold_z=0.5,
        phase_timeout=10.0,
        control_period_s=0.001,
        base_torque=12,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from xiaoyao.adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, lambda: 10.0,
        on_state_change=lambda _state: None,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 1.2),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, -0.8),
    }
    sensor.joint_feedback = [Joint(id=JointId.THUMB_PIP, angle=0.11)]
    sensor.sum_active_finger_normal_force.return_value = 2.0

    result = controller.run(is_running=lambda: True)

    assert result.contact_snapshot is not None
    assert result.contact_snapshot.finger_fz == {
        TactileSensorId.THUMB: pytest.approx(1.2),
        TactileSensorId.FOREFINGER: pytest.approx(0.8),
    }


def test_phase_open_and_pre_grasp(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(pre_grasp_preset="two_finger_pinch")
    sensor = MagicMock()
    safety = MagicMock()
    from xiaoyao.adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    states = []
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=states.append,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = []
    sensor.sum_active_finger_normal_force.return_value = 4.0

    result = controller.run(is_running=lambda: True)

    assert isinstance(result, PhaseResult)
    assert result.success is True
    assert len(hand.calls) == 3
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    assert hand.calls[1]["mode"] == CtrlMode.POSITION
    assert hand.calls[2]["mode"] == CtrlMode.TORQUE


def test_phase_failure_sets_error_state(monkeypatch):
    hand = _FailingHand()
    cfg = AdaptiveGraspConfig(pre_grasp_preset="two_finger_pinch")
    sensor = MagicMock()
    safety = MagicMock()
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    states = []
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=states.append,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    result = controller.run(is_running=lambda: True)

    assert result.success is False
    assert states[-1] == GraspState.ERROR


def test_phase_closing_empty_grasp_requests_release(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        phase_timeout=10.0,
        control_period_s=0.001,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from xiaoyao.adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.FAULT)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    states = []
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=states.append,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 0.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 0.0),
    }
    sensor.joint_feedback = [Joint(id=JointId.THUMB_MCP, angle=0.0)]
    sensor.sum_active_finger_normal_force.return_value = 0.0

    result = controller.run(is_running=lambda: True)

    assert result.success is False
    assert result.should_release is True
