from typing import Any, Optional, Protocol, runtime_checkable

from xiaoyao.dexhand import CtrlMode, Joint, TactileSensorId


@runtime_checkable
class HandCommandPort(Protocol):
    def move_joints(self, joints: list[Joint], mode: CtrlMode) -> bool:
        ...

    def stop(self) -> None:
        ...


@runtime_checkable
class SubscriptionPeriodConfigurator(Protocol):
    def configure_subscription_periods(
        self,
        *,
        recv_period_s: float,
        dispatch_period_s: float,
    ) -> None:
        ...


@runtime_checkable
class SensorFrameSource(Protocol):
    def start(self) -> None:
        ...

    def stop(self, clear_joint_feedback: bool = False) -> None:
        ...

    def reset(self) -> None:
        ...

    @property
    def tactile_data(self) -> Optional[dict[TactileSensorId, Any]]:
        ...

    @property
    def joint_feedback(self) -> Optional[list[Joint]]:
        ...

    @property
    def sample_time_s(self) -> Optional[float]:
        ...

    def data_age_s(self, current_time: float) -> Optional[float]:
        ...

    def sum_active_finger_normal_force(self) -> float:
        ...

    def active_finger_touch_flag(self) -> dict[TactileSensorId, bool]:
        ...
