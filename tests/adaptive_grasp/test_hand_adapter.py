import pytest

from adaptive_grasp.hand_adapter import (
    GHandCommandPort,
    ensure_hand_command_port,
)
from ghand import CtrlMode, JointCommand, JointId


class _FakeGHandCtrlMode:
    def __init__(self, value):
        self.value = value


class _FakeGHandJointCommand:
    def __init__(self, *, id, angle, speed, torque):
        self.id = id
        self.angle = angle
        self.speed = speed
        self.torque = torque


class _FakeSubscriptionManager:
    def __init__(self):
        self.calls = []

    def configure_periods(self, **kwargs):
        self.calls.append(kwargs)


class _PortLikeHand:
    def move_joints(self, joints, mode):
        return False

    def stop(self):
        pass

    def wait_for_motion_completion(self):
        return True


class _SubscribingPortLikeHand(_PortLikeHand):
    def subscribe(self, callback):
        return 1

    @property
    def is_ghand(self) -> bool:
        return True


class _CommandOnlyHand:
    def move_joints(self, joints, mode):
        return False

    def stop(self):
        pass


class _NotAHand:
    pass


class _FakeGHand:
    JointCommand = _FakeGHandJointCommand
    CtrlMode = _FakeGHandCtrlMode
    is_ghand = True

    def __init__(self):
        self.move_calls = []
        self.stop_calls = 0

    def move_joints(self, joints, mode):
        self.move_calls.append((joints, mode))
        return True

    def stop(self):
        self.stop_calls += 1

    def get_hand_info(self):
        return None


def test_ghand_command_port_converts_radian_joint_commands_to_degrees():
    hand = _FakeGHand()
    port = GHandCommandPort(hand)
    joints = [
        JointCommand(id=JointId.THUMB_PIP, angle=1.5707963267948966, speed=20, torque=30)
    ]

    assert port.move_joints(joints, CtrlMode.POSITION) is True

    sent_joints, sent_mode = hand.move_calls[0]
    assert sent_mode.value == CtrlMode.POSITION.value
    assert sent_joints[0].id == JointId.THUMB_PIP
    assert sent_joints[0].angle == pytest.approx(90.0)
    assert sent_joints[0].speed == 20
    assert sent_joints[0].torque == 30


def test_ghand_command_port_delegates_stop():
    hand = _FakeGHand()
    port = GHandCommandPort(hand)

    port.stop()

    assert hand.stop_calls == 1


def test_ghand_command_port_configures_subscription_periods_on_hand():
    hand = _FakeGHand()
    hand._sub_manager = _FakeSubscriptionManager()
    port = GHandCommandPort(hand)

    port.configure_subscription_periods(recv_period_s=0.01, dispatch_period_s=0.02)

    assert hand._sub_manager.calls == [
        {"recv_period_s": 0.01, "dispatch_period_s": 0.02}
    ]


def test_ghand_command_port_configures_subscription_periods_on_comm():
    hand = _FakeGHand()
    hand._comm = type("Comm", (), {"_sub_manager": _FakeSubscriptionManager()})()
    port = GHandCommandPort(hand)

    port.configure_subscription_periods(recv_period_s=0.01, dispatch_period_s=0.02)

    assert hand._comm._sub_manager.calls == [
        {"recv_period_s": 0.01, "dispatch_period_s": 0.02}
    ]


def test_ghand_command_port_ignores_missing_subscription_manager():
    hand = _FakeGHand()
    port = GHandCommandPort(hand)

    port.configure_subscription_periods(recv_period_s=0.01, dispatch_period_s=0.02)


def test_ghand_command_port_waits_for_motion_completion(monkeypatch):
    hand = _FakeGHand()
    calls = []

    def fake_wait_for_completion(wait_hand):
        calls.append(wait_hand)
        return True

    monkeypatch.setattr(
        "adaptive_grasp.hand_adapter._wait_for_completion",
        fake_wait_for_completion,
    )
    port = GHandCommandPort(hand)

    assert port.wait_for_motion_completion() is True
    assert calls == [hand]


def test_ensure_hand_command_port_returns_existing_port_like_object():
    port_like = _PortLikeHand()

    assert ensure_hand_command_port(port_like) is port_like


def test_ensure_hand_command_port_prefers_complete_port_over_ghand_like_shape():
    port_like = _SubscribingPortLikeHand()

    assert ensure_hand_command_port(port_like) is port_like


def test_ensure_hand_command_port_accepts_command_only_port():
    command_only = _CommandOnlyHand()

    assert ensure_hand_command_port(command_only) is command_only


def test_ensure_hand_command_port_rejects_invalid_object():
    with pytest.raises(TypeError, match="hand port"):
        ensure_hand_command_port(_NotAHand())


def test_ensure_hand_command_port_returns_existing_ghand_command_port():
    existing_port = GHandCommandPort(_FakeGHand())

    assert ensure_hand_command_port(existing_port) is existing_port


def test_ensure_hand_command_port_wraps_ghand_like_object():
    hand = _FakeGHand()

    port = ensure_hand_command_port(hand)

    assert isinstance(port, GHandCommandPort)
    assert port.hand is hand


def test_hand_ports_export_from_adaptive_grasp_package():
    from adaptive_grasp import (
        GHandCommandPort as ExportedGHandCommandPort,
        GraspSequenceHandPort,
        HandCommandPort,
        SensorFrameSource,
        SubscriptionPeriodConfigurator,
        ensure_hand_command_port as exported_ensure_hand_command_port,
    )

    assert ExportedGHandCommandPort is GHandCommandPort
    assert exported_ensure_hand_command_port is ensure_hand_command_port
    assert HandCommandPort.__name__ == "HandCommandPort"
    assert GraspSequenceHandPort.__name__ == "GraspSequenceHandPort"
    assert SubscriptionPeriodConfigurator.__name__ == "SubscriptionPeriodConfigurator"
    assert SensorFrameSource.__name__ == "SensorFrameSource"
