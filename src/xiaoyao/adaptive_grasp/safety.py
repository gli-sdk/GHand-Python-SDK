import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import logging

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
        self._consecutive_no_data: int = 0
        self._prev_joint_feedback: dict[Any, float] = {}

    @staticmethod
    def _get_angle(joint: Any) -> float:
        if hasattr(joint, "angle"):
            return float(joint.angle)
        if isinstance(joint, dict):
            return float(joint.get("angle", 0.0))
        return 0.0

    def check(
        self,
        tactile_data: Optional[dict],
        joint_feedback: Optional[list],
        state: GraspState,
    ) -> SafetyReport:
        cfg = self.config

        # 传感器故障：数据突变或无数据
        if joint_feedback is not None and len(joint_feedback) >= 1:
            current_angles: dict[Any, float] = {}
            for j in joint_feedback:
                jid = getattr(j, "id", j.get("id") if isinstance(j, dict) else None)
                if jid is not None:
                    current_angles[jid] = self._get_angle(j)
            if self._prev_joint_feedback:
                for jid, angle in current_angles.items():
                    prev = self._prev_joint_feedback.get(jid)
                    if prev is not None and abs(angle - prev) > math.radians(30.0):
                        _logger.error(
                            "Joint angle spike on %s: %.1f°",
                            jid, math.degrees(abs(angle - prev)),
                        )
                        return SafetyReport(SafetyStatus.FAULT, "sensor_fault", f"Joint angle spike on {jid}")
            self._prev_joint_feedback = current_angles

        if tactile_data is None:
            self._consecutive_no_data += 1
            if self._consecutive_no_data >= 3:
                _logger.error("Tactile data missing for %d cycles", self._consecutive_no_data)
                return SafetyReport(SafetyStatus.FAULT, "sensor_fault", "Tactile data missing for 3 cycles")
            return SafetyReport(SafetyStatus.WARN, message="Tactile data missing")
        else:
            self._consecutive_no_data = 0

        total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values()) if tactile_data else 0.0

        # 空抓检测（仅在 CLOSING 阶段）
        if state == GraspState.CLOSING_TO_CONTACT and total_fz < cfg.contact_threshold_z:
            if joint_feedback:
                max_angle = max(
                    (abs(self._get_angle(j)) for j in joint_feedback),
                    default=0.0
                )
                if max_angle > math.radians(10.0):
                    _logger.error("Empty grasp detected: max_angle=%.1f°", math.degrees(max_angle))
                    return SafetyReport(SafetyStatus.FAULT, "empty_grasp", "No contact while joints moved")

        # 物体掉落检测
        if state == GraspState.ADAPTIVE_HOLD:
            if self._last_total_fz >= cfg.contact_threshold_z and total_fz < cfg.contact_threshold_z:
                _logger.error("Object dropped: last_fz=%.2f current_fz=%.2f", self._last_total_fz, total_fz)
                return SafetyReport(SafetyStatus.FAULT, "object_dropped", "Contact lost in adaptive hold")

        self._last_total_fz = total_fz
        return SafetyReport(SafetyStatus.OK)

    def reset(self) -> None:
        self._last_total_fz = 0.0
        self._consecutive_no_data = 0
        self._prev_joint_feedback.clear()
