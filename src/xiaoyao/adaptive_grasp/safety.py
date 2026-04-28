import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

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
        cfg = self.config

        if joint_feedback is None:
            return SafetyReport(SafetyStatus.FAULT, "sensor_fault", "Joint feedback missing")

        if tactile_data is None:
            self._consecutive_no_data += 1
            if self._consecutive_no_data >= 3:
                _logger.error("Tactile data missing for %d cycles", self._consecutive_no_data)
                return SafetyReport(SafetyStatus.FAULT, "sensor_fault", "Tactile data missing for 3 cycles")
            return SafetyReport(SafetyStatus.WARN, message="Tactile data missing")

        self._consecutive_no_data = 0

        current_finger_count = len(tactile_data)
        total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())

        if state == GraspState.ADAPTIVE_HOLD:
            contact_was_present = self._last_total_fz >= cfg.contact_threshold_z
            contact_is_lost = total_fz < cfg.contact_threshold_z
            finger_data_not_reduced = current_finger_count >= self._last_finger_count
            if contact_was_present and contact_is_lost and finger_data_not_reduced:
                self._consecutive_drop_cycles += 1
                if self._consecutive_drop_cycles >= cfg.drop_detect_debounce_cycles:
                    _logger.error("Object dropped: last_fz=%.2f current_fz=%.2f", self._last_total_fz, total_fz)
                    return SafetyReport(SafetyStatus.FAULT, "object_dropped", "Contact lost in adaptive hold")
            else:
                self._consecutive_drop_cycles = 0

        self._last_total_fz = total_fz
        self._last_finger_count = current_finger_count
        return SafetyReport(SafetyStatus.OK)

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
        self._last_finger_count = 0
        self._consecutive_no_data = 0
        self._consecutive_drop_cycles = 0
        self._closing_baseline_angles.clear()
