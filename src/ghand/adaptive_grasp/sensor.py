# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from typing import Any, Optional

from ..types import TactileSensorId, JointData, TactileData
from .ports import SensorFrame
from .utils import active_finger_normal_forces, normal_force_z, normalize_joint_id

_logger = logging.getLogger("ghand.sensor")
_DEFAULT_FINGER_TOUCH_THRESHOLD_N = 0.1


class SensorClient:
    """Caches subscribed tactile and joint feedback data for grasp control."""

    def __init__(
        self,
        hand: Any,
        active_fingers: Optional[set[TactileSensorId]] = None,
        finger_touch_threshold_n: float = _DEFAULT_FINGER_TOUCH_THRESHOLD_N,
        get_monotonic_time: Optional[Any] = None,
    ):
        self._hand = hand
        self._finger_touch_threshold_n = finger_touch_threshold_n
        self._active_fingers = active_fingers or {
            TactileSensorId.THUMB,
            TactileSensorId.FF,
            TactileSensorId.MF,
            TactileSensorId.RF,
            TactileSensorId.LF,
        }
        self._frame = self._make_frame(None, None, None)
        self._sub_id: Optional[int] = None
        self._get_monotonic_time = get_monotonic_time or time.monotonic

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start subscribing sensor data and clear stale caches."""
        self._frame = self._make_frame(None, None, self._frame.sample_time_s)
        self._sub_id = self._hand.subscribe(self._on_data)

    def stop(self, clear_joint_feedback: bool = False) -> None:
        """Stop subscription and optionally clear cached joint feedback."""
        if self._sub_id is not None:
            try:
                self._hand.unsubscribe(self._sub_id)
            except Exception:
                _logger.exception("Failed to unsubscribe sensor data")
            self._sub_id = None
        joint_feedback = None if clear_joint_feedback else self._frame.joint_feedback
        self._frame = self._make_frame(None, joint_feedback, self._frame.sample_time_s)

    def reset(self) -> None:
        """Clear cached sensor data and timestamps."""
        self._frame = self._make_frame(None, None, None)

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------
    @property
    def tactile_data(self) -> Optional[dict[TactileSensorId, Any]]:
        return self._frame.tactile_data

    @property
    def joint_feedback(self) -> Optional[list[JointData]]:
        return self._frame.joint_feedback

    @property
    def sample_time_s(self) -> Optional[float]:
        return self._frame.sample_time_s

    def snapshot(self) -> SensorFrame:
        return self._frame

    def data_age_s(self, current_time: float) -> Optional[float]:
        sample_time_s = self._frame.sample_time_s
        if sample_time_s is None:
            return None
        return current_time - sample_time_s

    def sum_active_finger_normal_force(self) -> float:
        return self._frame.total_normal_force

    def active_finger_touch_flag(self) -> dict[TactileSensorId, bool]:
        return dict(self._frame.touch_flags or {})

    def _make_frame(
        self,
        tactile_data: Optional[dict[TactileSensorId, Any]],
        joint_feedback: Optional[list[JointData]],
        sample_time_s: Optional[float],
    ) -> SensorFrame:
        normal_forces = active_finger_normal_forces(
            tactile_data or {}, self._active_fingers
        )
        touch_flags = {
            finger: (
                (info := (tactile_data or {}).get(finger)) is not None
                and info.state
                and normal_force_z(info) >= self._finger_touch_threshold_n
            )
            for finger in self._active_fingers
        }
        return SensorFrame(
            tactile_data=tactile_data,
            joint_feedback=joint_feedback,
            sample_time_s=sample_time_s,
            total_normal_force=sum(normal_forces.values()),
            touch_flags=touch_flags,
        )

    # ------------------------------------------------------------------
    # Internal callback
    # ------------------------------------------------------------------
    def _on_data(self, data: Any) -> None:
        if not (hasattr(data, "tactile") and hasattr(data, "joints")):
            raise TypeError(
                "SensorClient subscription callback expects ghand.DeviceData; "
                "legacy TPDO parsing is not supported."
            )

        tactile = getattr(data, "tactile", None)
        if tactile is None:
            tactile_data = None
        else:
            tactile_data = {
                TactileSensorId(finger): info
                for finger, info in tactile.items()
                if TactileSensorId(finger) in self._active_fingers
            }
        sample_time_s = self._get_monotonic_time()
        joint_feedback = [
            JointData(
                id=normalize_joint_id(joint_data.id),
                state=joint_data.state,
                error=joint_data.error,
                angle=joint_data.angle,
                velocity=joint_data.velocity,
                current=joint_data.current,
            )
            for joint_data in getattr(data, "joints", ())
        ]
        self._frame = self._make_frame(tactile_data, joint_feedback, sample_time_s)
