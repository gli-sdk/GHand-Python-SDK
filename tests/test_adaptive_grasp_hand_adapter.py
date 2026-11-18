"""Exercise the adaptive port against the real SDK API with an offline transport."""

from types import SimpleNamespace

import pytest

from ghand import CommType, GHand, HandControlMode, JointCommand, JointId, ProductType
from ghand.adaptive_grasp.config import AdaptiveGraspConfig
from ghand.adaptive_grasp.grasp_sequence import PhaseController
from ghand.adaptive_grasp.hand_adapter import GHandCommandPort, ensure_hand_command_port
from ghand.adaptive_grasp.joint_builder import JointCommandBuilder


@pytest.fixture
def sdk_hand(monkeypatch):
    calls = []
    transport = SimpleNamespace(
        move_joints=lambda commands, mode: calls.append((commands, mode)) or True,
        disconnect=lambda: True,
    )
    monkeypatch.setattr(GHand, "_create_comm", lambda self, comm: transport)
    hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)
    yield hand, calls
    hand.close()


@pytest.mark.parametrize("mode", [HandControlMode.POSITION, HandControlMode.CURRENT])
def test_sdk_adapter_preserves_requested_mode_and_command(sdk_hand, mode):
    hand, calls = sdk_hand
    port = ensure_hand_command_port(hand)
    assert isinstance(port, GHandCommandPort)
    current = -12 if mode == HandControlMode.CURRENT else 12
    command = JointCommand(id=JointId.FF_MCP, angle=22, velocity=15, current=current)

    assert port.move_joints([command], mode=mode)

    assert len(calls) == 1
    commands, sent_mode = calls[0]
    assert sent_mode == mode
    assert len(commands) == 1
    assert commands[0].id == command.id
    assert commands[0].angle == command.angle
    assert commands[0].velocity == command.velocity
    assert commands[0].current == current
    assert commands[0].control_mode.value == mode.value


def test_sdk_transport_rejection_is_returned(sdk_hand):
    hand, _ = sdk_hand
    hand._comm.move_joints = lambda commands, mode: False
    assert ensure_hand_command_port(hand).move_joints(
        [JointCommand(id=JointId.FF_MCP, angle=22, velocity=15, current=12)],
        mode=HandControlMode.POSITION,
    ) is False


def test_open_phase_reaches_real_sdk_api_without_keyword_error(sdk_hand):
    hand, calls = sdk_hand
    config = AdaptiveGraspConfig(pre_grasp_preset="five_finger_grasp")
    builder = JointCommandBuilder(config, (JointId.FF_MCP,))
    sensor = SimpleNamespace(joint_feedback=[
        SimpleNamespace(id=joint_id, angle=angle)
        for joint_id, angle in builder.open_pose().items()
    ])
    controller = PhaseController(
        hand_port=ensure_hand_command_port(hand), sensor=sensor,
        safety=None, joint_builder=builder, config=config,
        get_time=lambda: 0.0, on_state_change=lambda state: None,
    )

    assert controller._phase_open()
    assert len(calls) == 1
    assert calls[0][1] == HandControlMode.POSITION


def test_existing_command_port_keeps_its_mode_interface():
    calls = []
    port = SimpleNamespace(
        move_joints=lambda commands, mode: calls.append((commands, mode)) or True,
        stop=lambda: None,
    )
    assert ensure_hand_command_port(port) is port
    assert port.move_joints([], mode=HandControlMode.CURRENT)
    assert calls == [([], HandControlMode.CURRENT)]
