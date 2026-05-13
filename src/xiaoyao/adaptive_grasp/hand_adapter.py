from typing import Any

from xiaoyao.dexhand import CtrlMode, Joint

from .ports import HandCommandPort


class DexHandCommandPort:
    def __init__(self, hand: Any):
        self.hand = hand

    def move_joints(self, joints: list[Joint], mode: CtrlMode) -> bool:
        return self.hand.move_joints(joints, mode=mode)

    def stop(self) -> None:
        self.hand.stop()

    def configure_subscription_periods(
        self,
        *,
        recv_period_s: float,
        dispatch_period_s: float,
    ) -> None:
        sub_manager = getattr(self.hand, "_sub_manager", None)
        configure_periods = getattr(sub_manager, "configure_periods", None)
        if configure_periods is None:
            return
        configure_periods(
            recv_period_s=recv_period_s,
            dispatch_period_s=dispatch_period_s,
        )


def ensure_hand_command_port(hand: Any) -> HandCommandPort:
    if isinstance(hand, DexHandCommandPort):
        return hand
    if (
        hasattr(hand, "move_joints")
        and hasattr(hand, "stop")
        and not hasattr(hand, "subscribe")
    ):
        return hand
    return DexHandCommandPort(hand)
