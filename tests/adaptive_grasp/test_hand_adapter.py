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


def test_ensure_hand_command_port_returns_existing_port_like_object():
    port_like = _PortLikeHand()

    assert ensure_hand_command_port(port_like) is port_like


def test_ensure_hand_command_port_wraps_dex_hand_like_object():
    hand = _FakeDexHand()

    port = ensure_hand_command_port(hand)

    assert isinstance(port, DexHandCommandPort)
    assert port.hand is hand
