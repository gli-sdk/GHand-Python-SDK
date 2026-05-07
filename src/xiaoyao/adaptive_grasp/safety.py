import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from xiaoyao.dexhand import TactileSensorId

from .config import AdaptiveGraspConfig
from .states import GraspState

_logger = logging.getLogger("xiaoyao.adaptive_grasp.safety")


class SafetyStatus(Enum):
    OK = "ok"
    WARN = "warn"
    FAULT = "fault"


@dataclass
class SafetyReport:
    status: SafetyStatus
    fault_type: Optional[str] = None
    message: str = ""


class SafetyMonitor:
    def __init__(self, config: AdaptiveGraspConfig):
        self.config = config
        self._last_total_fz: float = 0.0
        self._last_active_finger_fz: dict[Any, float] = {}
        self._last_finger_count: int = 0
        self._consecutive_no_data: int = 0
        self._consecutive_drop_cycles: int = 0
        self._closing_baseline_angles: dict[Any, float] = {}

    def set_closing_baseline(self, joint_feedback: list) -> None:
        self._closing_baseline_angles = {j.id: j.angle for j in joint_feedback}

    def check(
        self,
        tactile_data: Optional[dict],
        joint_feedback: Optional[list],
        state: GraspState,
    ) -> SafetyReport:
        if joint_feedback is None:
            return SafetyReport(SafetyStatus.FAULT, "sensor_fault", "Joint feedback missing")

        if tactile_data is None:
            self._consecutive_no_data += 1
            if self._consecutive_no_data >= 3:
                _logger.error("Tactile data missing for %d cycles", self._consecutive_no_data)
                return SafetyReport(SafetyStatus.FAULT, "sensor_fault", "Tactile data missing for 3 cycles")
            return SafetyReport(SafetyStatus.WARN, message="Tactile data missing")

        self._consecutive_no_data = 0

        active_finger_fz = self._get_active_finger_fz(tactile_data)
        total_fz = sum(active_finger_fz.values())

        if state == GraspState.ADAPTIVE_HOLD:
            drop_report = self._check_object_drop(total_fz, active_finger_fz)
            if drop_report.status == SafetyStatus.FAULT:
                return drop_report

        if state != GraspState.ADAPTIVE_HOLD or not self._is_below_drop_threshold(total_fz):
            self._last_total_fz = total_fz
            self._last_active_finger_fz = active_finger_fz
            self._last_finger_count = len(active_finger_fz)
        return SafetyReport(SafetyStatus.OK)

    def _check_object_drop(self, total_fz: float, active_finger_fz: dict[Any, float]) -> SafetyReport:
        drop_threshold = self._drop_threshold()
        if self._is_below_drop_threshold(total_fz):
            self._consecutive_drop_cycles += 1
            if self._consecutive_drop_cycles >= 3:
                _logger.error(
                    "Object dropped:\n"
                    "  total: last_fz=%.2f current_fz=%.2f threshold=%.2f\n"
                    "  active_fingers:\n%s",
                    self._last_total_fz,
                    total_fz,
                    drop_threshold,
                    self._format_active_finger_fz(active_finger_fz),
                )
                return SafetyReport(SafetyStatus.FAULT, "object_dropped", "Contact lost in adaptive hold")
        else:
            self._consecutive_drop_cycles = 0
        return SafetyReport(SafetyStatus.OK)

    def _drop_threshold(self) -> float:
        active_finger_count = max(len(self.config.active_fingers), 1)
        return active_finger_count * 0.1

    def _is_below_drop_threshold(self, total_fz: float) -> bool:
        return total_fz < self._drop_threshold()

    def _get_active_finger_fz(self, tactile_data: dict) -> dict[Any, float]:
        return {
            finger: abs(tactile_data[finger].get_force_z())
            for finger in self._ordered_active_fingers()
            if finger in tactile_data
        }

    def _ordered_active_fingers(self) -> list[Any]:
        active_fingers = set(self.config.active_fingers)
        known_order = [finger for finger in TactileSensorId if finger in active_fingers]
        remaining = sorted(active_fingers.difference(known_order), key=self._finger_label)
        return known_order + remaining

    def _format_active_finger_fz(self, active_finger_fz: dict[Any, float]) -> str:
        parts = []
        for finger in self._ordered_active_fingers():
            parts.append(
                f"    {self._finger_label(finger)}: "
                f"last_fz={self._last_active_finger_fz.get(finger, 0.0):.2f} "
                f"current_fz={active_finger_fz.get(finger, 0.0):.2f}"
            )
        return "\n".join(parts)

    @staticmethod
    def _finger_label(finger: Any) -> str:
        return str(getattr(finger, "value", finger))

    def is_grasp_empty(
        self,
        joint_feedback: Optional[list],
        state: GraspState,
    ) -> SafetyReport:
        if state != GraspState.CLOSING_TO_CONTACT:
            return SafetyReport(SafetyStatus.OK)
        if not joint_feedback or not self._closing_baseline_angles:
            return SafetyReport(SafetyStatus.OK)

        max_delta = max(
            (abs(j.angle - self._closing_baseline_angles.get(j.id, 0.0)) for j in joint_feedback),
            default=0.0,
        )
        if max_delta > math.radians(30.0):
            _logger.error("Empty grasp detected: max_delta=%.1f deg", math.degrees(max_delta))
            return SafetyReport(SafetyStatus.FAULT, "empty_grasp", "No contact while joints moved")
        return SafetyReport(SafetyStatus.OK)

    def reset(self) -> None:
        self._last_total_fz = 0.0
        self._last_active_finger_fz = {}
        self._last_finger_count = 0
        self._consecutive_no_data = 0
        self._consecutive_drop_cycles = 0
        self._closing_baseline_angles.clear()
