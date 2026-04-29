import time
from unittest.mock import MagicMock
import pytest
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig, GraspState
from xiaoyao.adaptive_grasp.phase_controller import PhaseController, PhaseResult
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.adaptive_grasp.force_planner import ForcePlanner
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
    monkeypatch.setattr("xiaoyao.adaptive_grasp.phase_controller.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = []
    sensor.sum_active_finger_normal_force.return_value = 4.0

    result = controller.run(force_planner=None, is_running=lambda: True)

    assert result.success is True
    assert GraspState.CLOSING_TO_CONTACT in states


def test_calibrate_force_increases_torque_when_below_target(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        torque_adjust_step=5,
        base_holding_force=6.0,
    )
    sensor = MagicMock()
    safety = MagicMock()
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=lambda s: None,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.phase_controller.time.sleep", lambda *_: None)

    sensor.sum_active_finger_normal_force.return_value = 1.0  # below target
    controller.current_torque = 10
    force_planner = ForcePlanner(cfg, None)

    controller._calibrate_force(force_planner)

    assert controller.current_torque > 10


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
    monkeypatch.setattr("xiaoyao.adaptive_grasp.phase_controller.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = []
    sensor.sum_active_finger_normal_force.return_value = 4.0

    result = controller.run(force_planner=None, is_running=lambda: True)

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
    monkeypatch.setattr("xiaoyao.adaptive_grasp.phase_controller.time.sleep", lambda *_: None)

    result = controller.run(force_planner=None, is_running=lambda: True)

    assert result.success is False
    assert states[-1] == GraspState.ERROR
