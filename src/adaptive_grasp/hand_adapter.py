import math
from typing import Any

from ghand import CtrlMode, JointCommand
from ghand.gestures import _wait_for_completion

from .ports import GraspSequenceHandPort


class GHandCommandPort:
    def __init__(self, hand: Any):
        self.hand = hand

    def move_joints(self, joints: list[JointCommand], mode: CtrlMode) -> bool:
        joint_command_cls = _ghand_attr("JointCommand", self.hand)
        ctrl_mode = _map_ghand_ctrl_mode(mode, self.hand)
        commands = [
            joint_command_cls(
                id=joint.id,
                angle=math.degrees(joint.angle),
                speed=joint.speed,
                torque=joint.torque,
            )
            for joint in joints
        ]
        return self.hand.move_joints(commands, mode=ctrl_mode)

    def stop(self) -> None:
        self.hand.stop()

    def wait_for_motion_completion(self) -> bool:
        return _wait_for_completion(self.hand)

    def configure_subscription_periods(
        self,
        *,
        recv_period_s: float,
        dispatch_period_s: float,
    ) -> None:
        sub_manager = getattr(self.hand, "_sub_manager", None)
        if sub_manager is None:
            sub_manager = getattr(getattr(self.hand, "_comm", None), "_sub_manager", None)
        configure_periods = getattr(sub_manager, "configure_periods", None)
        if configure_periods is None:
            return
        configure_periods(
            recv_period_s=recv_period_s,
            dispatch_period_s=dispatch_period_s,
        )


def ensure_hand_command_port(hand: Any) -> GraspSequenceHandPort:
    if isinstance(hand, GHandCommandPort):
        return hand

    is_ghand_like = hand.__class__.__name__ == "GHand" or getattr(hand, "is_ghand", False)
    has_command_methods = hasattr(hand, "move_joints") and hasattr(hand, "stop")
    has_motion_completion = hasattr(hand, "wait_for_motion_completion")

    if has_command_methods and (has_motion_completion or not is_ghand_like):
        return hand
    if is_ghand_like and has_command_methods:
        return GHandCommandPort(hand)
    raise TypeError(
        "hand port must provide move_joints()/stop() or be a GHand-like object"
    )


def _ghand_attr(name: str, hand: Any | None = None) -> Any:
    if hand is not None and hasattr(hand, name):
        return getattr(hand, name)
    try:
        import ghand
    except ImportError as exc:
        raise RuntimeError(
            "GHandCommandPort requires the ghand package. "
            "Install with `python -m pip install -e .` to pull project dependencies."
        ) from exc
    return getattr(ghand, name)


def _map_ghand_ctrl_mode(mode: CtrlMode, hand: Any | None = None) -> Any:
    ghand_ctrl_mode = _ghand_attr("CtrlMode", hand)
    return ghand_ctrl_mode(mode.value)
