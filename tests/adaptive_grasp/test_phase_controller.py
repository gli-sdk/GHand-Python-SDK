import time
from unittest.mock import MagicMock
import pytest
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig, GraspState
from xiaoyao.adaptive_grasp.phase_controller import PhaseController, PhaseResult
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.dexhand import CtrlMode, JointId


class _MockHand:
    def __init__(self):
        self.calls = []

    def move_joints(self, joints, mode=None):
        self.calls.append({"mode": mode, "joints": list(joints)})
        return True

    def stop(self):
        return None


def test_phase_open_and_pre_grasp(monkeypatch):
    hand = _MockHand()
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

    assert isinstance(result, PhaseResult)
    assert result.success is True
    assert len(hand.calls) == 2
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    assert hand.calls[1]["mode"] == CtrlMode.POSITION
