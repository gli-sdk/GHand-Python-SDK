# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

from ..types import TactileSensorId, CtrlMode, JointCommand


@dataclass(frozen=True)
class SensorFrame:
    tactile_data: Optional[dict[TactileSensorId, Any]] = None
    joint_feedback: Optional[list[Any]] = None
    sample_time_s: Optional[float] = None
    total_normal_force: float = 0.0
    touch_flags: Optional[dict[TactileSensorId, bool]] = None


def read_sensor_frame(sensor: "SensorFrameSource") -> SensorFrame:
    snapshot = getattr(sensor, "snapshot", None)
    if callable(snapshot):
        return snapshot()
    return SensorFrame(
        tactile_data=sensor.tactile_data,
        joint_feedback=sensor.joint_feedback,
        sample_time_s=sensor.sample_time_s,
        total_normal_force=sensor.sum_active_finger_normal_force(),
        touch_flags=sensor.active_finger_touch_flag(),
    )


@runtime_checkable
class HandCommandPort(Protocol):
    def move_joints(self, joints: list[JointCommand], mode: CtrlMode) -> bool:
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
    def joint_feedback(self) -> Optional[list[JointCommand]]:
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
