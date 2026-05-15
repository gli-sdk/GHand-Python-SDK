from typing import Any

from xiaoyao.dexhand import CtrlMode, Joint
from xiaoyao.gestures import _wait_for_completion as wait_for_completion

from .ports import GraspSequenceHandPort


class DexHandCommandPort:
    def __init__(self, hand: Any):
        self.hand = hand

    def move_joints(self, joints: list[Joint], mode: CtrlMode) -> bool:
        return self.hand.move_joints(joints, mode=mode)

    def stop(self) -> None:
        self.hand.stop()

    def wait_for_motion_completion(self) -> bool:
        return wait_for_completion(self.hand)

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


def ensure_hand_command_port(hand: Any) -> GraspSequenceHandPort:
    if isinstance(hand, DexHandCommandPort):
        return hand

    is_dex_hand_like = hasattr(hand, "subscribe") or hasattr(hand, "get_hand_info")
    has_command_methods = hasattr(hand, "move_joints") and hasattr(hand, "stop")
    has_motion_completion = hasattr(hand, "wait_for_motion_completion")

    if has_command_methods and has_motion_completion:
        return hand
    if is_dex_hand_like:
        return DexHandCommandPort(hand)
    if has_command_methods:
        raise TypeError(
            "hand port must provide wait_for_motion_completion() or be a "
            "DexHand-like object with get_hand_info()"
        )
    raise TypeError(
        "hand port must provide move_joints()/stop() or be a DexHand-like object"
    )
