import time
import inspect
from unittest.mock import MagicMock
import pytest
from adaptive_grasp import AdaptiveGraspConfig, GraspState
from adaptive_grasp.grasp_sequence import PhaseController, PhaseResult
from adaptive_grasp.joint_builder import JointCommandBuilder
from adaptive_grasp.object_profile import ObjectProfile
from ghand import CtrlMode, JointId
from ghand import JointCommand, TactileSensorId


class _MockHand:
    def __init__(self):
        self.calls = []
        self.wait_calls = 0

    def move_joints(self, joints, mode=None):
        self.calls.append({"mode": mode, "joints": list(joints)})
        return True

    def stop(self):
        return None

    def wait_for_motion_completion(self):
        self.wait_calls += 1
        return True


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
        closing_total_contact_threshold_n=0.5,
        phase_timeout=10.0,
        control_period_s=0.001,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    states = []
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=states.append,
    )
    monkeypatch.setattr("adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FF: _FakeTactileInfo(0.0, 0.0, 2.0),
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
        closing_total_contact_threshold_n=0.5,
        phase_timeout=10.0,
        control_period_s=0.001,
    )
    profile = ObjectProfile(
        name="test_object",
        weight_kg=0.1,
        safe_force_min=1.0,
        safe_force_max=5.0,
        friction_coeff=0.8,
        is_fragile=False,
        material="test",
        position_hold_torque=30,
        position_hold_speed=30,
        phase_closing_torque=4,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=lambda _state: None,
        object_profile=profile,
    )
    monkeypatch.setattr("adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FF: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = []
    sensor.sum_active_finger_normal_force.return_value = 4.0

    result = controller.run(is_running=lambda: True)

    assert result.success is True
    closing_call = next(call for call in hand.calls if call["mode"] == CtrlMode.TORQUE)
    torque_by_joint = {JointCommand.id: JointCommand.torque for JointCommand in closing_call["joints"]}
    assert torque_by_joint[JointId.THUMB_PIP] == 4
    assert torque_by_joint[JointId.FF_PIP] == 4
    assert result.final_torque == 4


def test_phase_closing_records_contact_joint_snapshot_by_force(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        closing_total_contact_threshold_n=0.5,
        phase_timeout=10.0,
        control_period_s=0.001,
    )
    profile = ObjectProfile(
        name="test_object",
        weight_kg=0.1,
        safe_force_min=1.0,
        safe_force_max=5.0,
        friction_coeff=0.8,
        is_fragile=False,
        material="test",
        position_hold_torque=30,
        position_hold_speed=30,
        phase_closing_torque=12,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, lambda: 10.0,
        on_state_change=lambda _state: None,
        object_profile=profile,
    )
    monkeypatch.setattr("adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FF: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = [
        JointCommand(id=JointId.THUMB_PIP, angle=0.11),
        JointCommand(id=JointId.THUMB_MCP, angle=0.22),
        JointCommand(id=JointId.FF_PIP, angle=0.33),
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
        closing_total_contact_threshold_n=0.5,
        phase_timeout=10.0,
        control_period_s=0.001,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, lambda: 10.0,
        on_state_change=lambda _state: None,
    )
    monkeypatch.setattr("adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 1.2),
        TactileSensorId.FF: _FakeTactileInfo(0.0, 0.0, -0.8),
    }
    sensor.joint_feedback = [JointCommand(id=JointId.THUMB_PIP, angle=0.11)]
    sensor.sum_active_finger_normal_force.return_value = 2.0

    result = controller.run(is_running=lambda: True)

    assert result.contact_snapshot is not None
    assert result.contact_snapshot.finger_fz == {
        TactileSensorId.THUMB: pytest.approx(1.2),
        TactileSensorId.FF: pytest.approx(0.8),
    }


def test_phase_open_and_pre_grasp(monkeypatch):
    hand = _MockHand()
    sleep_calls = []
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        open_speed=11,
        open_torque=12,
        open_wait_s=1.5,
        pre_grasp_speed=21,
        pre_grasp_torque=22,
        pre_grasp_wait_s=2.5,
    )
    sensor = MagicMock()
    safety = MagicMock()
    from adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.OK)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    states = []
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=states.append,
    )
    monkeypatch.setattr(
        "adaptive_grasp.grasp_sequence.time.sleep",
        lambda duration: sleep_calls.append(duration),
    )

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FF: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = []
    sensor.sum_active_finger_normal_force.return_value = 4.0

    result = controller.run(is_running=lambda: True)

    assert isinstance(result, PhaseResult)
    assert result.success is True
    assert len(hand.calls) == 3
    assert hand.wait_calls == 2
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    assert hand.calls[1]["mode"] == CtrlMode.POSITION
    assert hand.calls[2]["mode"] == CtrlMode.TORQUE
    assert {JointCommand.speed for JointCommand in hand.calls[0]["joints"]} == {11}
    assert {JointCommand.torque for JointCommand in hand.calls[0]["joints"]} == {12}
    assert {JointCommand.speed for JointCommand in hand.calls[1]["joints"]} == {21}
    assert {JointCommand.torque for JointCommand in hand.calls[1]["joints"]} == {22}
    assert sleep_calls[:2] == [0.02, 0.02]


def test_execute_position_phase_signature_has_no_unused_wait_s():
    parameters = inspect.signature(PhaseController._execute_position_phase).parameters

    assert "wait_s" not in parameters


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
    monkeypatch.setattr("adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

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
    from adaptive_grasp.safety import SafetyStatus
    safety.is_grasp_empty.return_value = MagicMock(status=SafetyStatus.FAULT)
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    states = []
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=states.append,
    )
    monkeypatch.setattr("adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 0.0),
        TactileSensorId.FF: _FakeTactileInfo(0.0, 0.0, 0.0),
    }
    sensor.joint_feedback = [JointCommand(id=JointId.THUMB_MCP, angle=0.0)]
    sensor.sum_active_finger_normal_force.return_value = 0.0

    result = controller.run(is_running=lambda: True)

    assert result.success is False
    assert result.should_release is True
