import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from xiaoyao.dexhand import JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .states import GraspState


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

    def check(
        self,
        tactile_data: Optional[dict],
        joint_feedback: Optional[list],
        state: GraspState,
    ) -> SafetyReport:
        cfg = self.config

        # 传感器故障：数据突变或无数据
        if joint_feedback is not None and len(joint_feedback) >= 2:
            # 检查相邻两次反馈是否有跳变 > 30°
            for i in range(len(joint_feedback) - 1):
                a1 = joint_feedback[i].get("angle", 0.0)
                a2 = joint_feedback[i + 1].get("angle", 0.0)
                if abs(a2 - a1) > math.radians(30.0):
                    return SafetyReport(SafetyStatus.FAULT, "sensor_fault", "Joint angle spike detected")

        if tactile_data is None:
            self._consecutive_no_data += 1
            if self._consecutive_no_data >= 3:
                return SafetyReport(SafetyStatus.FAULT, "sensor_fault", "Tactile data missing for 3 cycles")
            return SafetyReport(SafetyStatus.WARN, message="Tactile data missing")
        else:
            self._consecutive_no_data = 0

        total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values()) if tactile_data else 0.0

        # 空抓检测（仅在 CLOSING 阶段）
        if state == GraspState.CLOSING and total_fz < cfg.contact_threshold_z:
            if joint_feedback:
                max_angle = max(
                    (abs(j.get("angle", 0.0)) for j in joint_feedback if "angle" in j),
                    default=0.0
                )
                if max_angle > math.radians(10.0):
                    return SafetyReport(SafetyStatus.FAULT, "empty_grasp", "No contact while joints moved")

        # 物体掉落检测
        if state == GraspState.ADAPTIVE_HOLDING:
            if self._last_total_fz >= cfg.contact_threshold_z and total_fz < cfg.contact_threshold_z:
                return SafetyReport(SafetyStatus.FAULT, "object_dropped", "Contact lost in adaptive hold")

        self._last_total_fz = total_fz
        return SafetyReport(SafetyStatus.OK)

    def reset(self) -> None:
        self._last_total_fz = 0.0
        self._consecutive_no_data = 0
