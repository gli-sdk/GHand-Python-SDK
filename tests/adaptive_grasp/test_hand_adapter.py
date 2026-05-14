import pytest

from xiaoyao.adaptive_grasp.hand_adapter import DexHandCommandPort, ensure_hand_command_port
from xiaoyao.dexhand import CtrlMode, Joint, JointId


class _FakeDexHand:
    def __init__(self):
        self.move_calls = []
        self.stop_calls = 0

    def move_joints(self, joints, *, mode):
        self.move_calls.append((joints, mode))
        return True

    def stop(self):
        self.stop_calls += 1

    def subscribe(self, callback):
        return 1


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


class _CommandOnlyHand:
    def move_joints(self, joints, mode):
        return False

    def stop(self):
        pass


class _GetHandInfoDexHandLike:
    def move_joints(self, joints, *, mode):
        return True

    def stop(self):
        pass

    def get_hand_info(self):
        return None


def test_dex_hand_command_port_delegates_move_joints_and_stop():
    hand = _FakeDexHand()
    port = DexHandCommandPort(hand)
    joints = [Joint(id=JointId.THUMB_PIP, angle=0.1)]

    assert port.move_joints(joints, CtrlMode.POSITION) is True
    port.stop()

    assert hand.move_calls == [(joints, CtrlMode.POSITION)]
    assert hand.stop_calls == 1


def test_dex_hand_command_port_configures_subscription_periods():
    hand = _FakeDexHand()
    hand._sub_manager = _FakeSubscriptionManager()
    port = DexHandCommandPort(hand)

    port.configure_subscription_periods(recv_period_s=0.01, dispatch_period_s=0.02)

    assert hand._sub_manager.calls == [
        {"recv_period_s": 0.01, "dispatch_period_s": 0.02}
    ]


def test_dex_hand_command_port_ignores_missing_subscription_manager():
    hand = _FakeDexHand()
    port = DexHandCommandPort(hand)

    port.configure_subscription_periods(recv_period_s=0.01, dispatch_period_s=0.02)


def test_dex_hand_command_port_waits_for_motion_completion(monkeypatch):
    hand = _FakeDexHand()
    calls = []

    def fake_wait_for_completion(wait_hand):
        calls.append(wait_hand)
        return True

    monkeypatch.setattr(
        "xiaoyao.adaptive_grasp.hand_adapter.wait_for_completion",
        fake_wait_for_completion,
    )
    port = DexHandCommandPort(hand)

    assert port.wait_for_motion_completion() is True
    assert calls == [hand]


def test_ensure_hand_command_port_returns_existing_port_like_object():
    port_like = _PortLikeHand()

    assert ensure_hand_command_port(port_like) is port_like


def test_ensure_hand_command_port_prefers_complete_port_over_dexhand_like_shape():
    port_like = _SubscribingPortLikeHand()

    assert ensure_hand_command_port(port_like) is port_like


def test_ensure_hand_command_port_rejects_command_only_port():
    with pytest.raises(TypeError, match="wait_for_motion_completion"):
        ensure_hand_command_port(_CommandOnlyHand())


def test_ensure_hand_command_port_returns_existing_dex_hand_command_port():
    existing_port = DexHandCommandPort(_FakeDexHand())

    assert ensure_hand_command_port(existing_port) is existing_port


def test_ensure_hand_command_port_wraps_dex_hand_like_object():
    hand = _FakeDexHand()

    port = ensure_hand_command_port(hand)

    assert isinstance(port, DexHandCommandPort)
    assert port.hand is hand


def test_ensure_hand_command_port_wraps_get_hand_info_dex_hand_like_object():
    hand = _GetHandInfoDexHandLike()

    port = ensure_hand_command_port(hand)

    assert isinstance(port, DexHandCommandPort)
    assert port.hand is hand


def test_hand_ports_export_from_adaptive_grasp_package():
    from xiaoyao.adaptive_grasp import (
        DexHandCommandPort as ExportedDexHandCommandPort,
        GraspSequenceHandPort,
        HandCommandPort,
        SensorFrameSource,
        SubscriptionPeriodConfigurator,
        ensure_hand_command_port as exported_ensure_hand_command_port,
    )

    assert ExportedDexHandCommandPort is DexHandCommandPort
    assert exported_ensure_hand_command_port is ensure_hand_command_port
    assert HandCommandPort.__name__ == "HandCommandPort"
    assert GraspSequenceHandPort.__name__ == "GraspSequenceHandPort"
    assert SubscriptionPeriodConfigurator.__name__ == "SubscriptionPeriodConfigurator"
    assert SensorFrameSource.__name__ == "SensorFrameSource"
