import math
import threading
import time
from collections import deque
from typing import Mapping

from xiaoyao.dexhand import CtrlMode, DexHand, Joint, JointId, TactileSensorId

from .config import AdaptiveGraspConfig
from .states import GraspState


class AdaptiveGrasper:
    _TORQUE_JOINTS = (
        JointId.THUMB_PIP,
        JointId.THUMB_MCP,
        JointId.FF_PIP,
        JointId.FF_MCP,
        JointId.MF_PIP,
        JointId.MF_MCP,
        JointId.RF_PIP,
        JointId.RF_MCP,
        JointId.LF_PIP,
        JointId.LF_MCP,
    )

    def __init__(self, hand: DexHand, config: AdaptiveGraspConfig | None = None):
        self.hand = hand
        self.config = config or AdaptiveGraspConfig()

        self.state = GraspState.IDLE
        self.current_torque = int(self._clamp_torque(self.config.base_torque))

        self._running = False
        self._control_thread: threading.Thread | None = None
        self._tactile_windows = {
            finger: deque(maxlen=self.config.sliding_window_size) for finger in TactileSensorId
        }

    def grasp(self) -> bool:
        try:
            self._running = True
            if not self._phase_open():
                self._running = False
                return False
            if not self._phase_pre_grasp():
                self._running = False
                return False
            if not self._phase_closing():
                self._running = False
                return False

            self._start_adaptive_control()
            return True
        except Exception:
            self.state = GraspState.ERROR
            self._running = False
            return False

    def release(self) -> bool:
        self._running = False
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)

        self.state = GraspState.RELEASING
        joints = self._build_position_joints(self._get_open_pose())
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)

        self.state = GraspState.COMPLETED if ok else GraspState.ERROR
        return ok

    def stop(self) -> None:
        self._running = False
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)
        self.hand.stop()
        self.state = GraspState.STOPPED

    def get_state(self) -> GraspState:
        return self.state

    def _phase_open(self) -> bool:
        self.state = GraspState.OPENING
        joints = self._build_position_joints(self._get_open_pose(),speed = 20,torque=20)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(2)
        return ok

    def _phase_pre_grasp(self) -> bool:
        self.state = GraspState.PRE_GRASPING
        joints = self._build_position_joints(self.config.pre_grasp_pose,speed=20,torque=20)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(2)
        return ok

    def _phase_closing(self) -> bool:
        self.state = GraspState.CLOSING
        start = time.time()
        torque = int(self._clamp_torque(self.config.base_torque))
        self.current_torque = torque

        while self._running:
            if (time.time() - start) > self.config.phase_timeout:
                return False

            joints = self._build_torque_joints(self.current_torque)
            if not self.hand.move_joints(joints, mode=CtrlMode.TORQUE):
                return False

            tactile_data = self._safe_get_tactile_data()
            if tactile_data:
                total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
                if total_fz >= self.config.contact_threshold_z:
                    return True

            time.sleep(self.config.control_period_s)

        return False

    def _start_adaptive_control(self) -> None:
        self.state = GraspState.ADAPTIVE_HOLDING
        self._control_thread = threading.Thread(target=self._adaptive_control_loop, daemon=True)
        self._control_thread.start()

    def _adaptive_control_loop(self) -> None:
        while self._running:
            self._run_control_step()
            time.sleep(self.config.control_period_s)

    def _run_control_step(self) -> bool:
        tactile_data = self._safe_get_tactile_data()
        if not tactile_data:
            return False

        for finger, info in tactile_data.items():
            ft = math.sqrt(info.get_force_x() ** 2 + info.get_force_y() ** 2)
            if finger in self._tactile_windows:
                self._tactile_windows[finger].append(ft)

        variance = self._calculate_variance()
        finger_fz = {finger: abs(info.get_force_z()) for finger, info in tactile_data.items()}
        next_torque = self._calculate_next_torque(finger_fz=finger_fz, variance=variance)

        if next_torque == self.current_torque:
            return True

        joints = self._build_torque_joints(next_torque)
        ok = self.hand.move_joints(joints, mode=CtrlMode.TORQUE)
        if ok:
            self.current_torque = next_torque
        return ok

    def _safe_get_tactile_data(self):
        try:
            return self.hand.get_tactile_data()
        except Exception:
            return None

    def _build_torque_joints(self, torque: int) -> list[Joint]:
        return [Joint(id=joint_id, torque=torque) for joint_id in self._TORQUE_JOINTS]

    def _build_position_joints(
        self,
        joint_angles: dict[JointId, float],
        speed: int = 100,
        torque: int = 100,
        speed_overrides: Mapping[JointId, int] | None = None,
        torque_overrides: Mapping[JointId, int] | None = None,
    ) -> list[Joint]:
        joints: list[Joint] = []
        speed_overrides = speed_overrides or {}
        torque_overrides = torque_overrides or {}
        for joint_id, angle in joint_angles.items():
            joint_speed = int(speed_overrides.get(joint_id, speed))
            joint_torque = int(torque_overrides.get(joint_id, torque))
            joints.append(Joint(id=joint_id, angle=angle, speed=joint_speed, torque=joint_torque))
        return joints

    def _calculate_variance(self) -> float:
        values = []
        for window in self._tactile_windows.values():
            if len(window) < 3:
                continue
            mean = sum(window) / len(window)
            var = sum((item - mean) ** 2 for item in window) / len(window)
            values.append(var)
        return max(values) if values else 0.0

    def _calculate_torque_from_slip(self, finger_fz: dict[TactileSensorId, float], variance: float) -> int:
        if not finger_fz:
            return self.current_torque
        if any(fz >= self.config.max_normal_force_per_finger for fz in finger_fz.values()):
            return self.current_torque

        if variance >= self.config.variance_threshold:
            target = self.current_torque + self.config.torque_adjust_step
            return int(round(self._clamp_torque(target)))

        return self.current_torque

    def _calculate_next_torque(self, finger_fz: dict[TactileSensorId, float], variance: float) -> int:
        if not finger_fz:
            return self.current_torque

        safety_limit = self.config.max_normal_force_per_finger * self.config.ext_safety_margin_ratio
        if any(fz >= safety_limit for fz in finger_fz.values()):
            return self.current_torque

        torque_from_slip = self._calculate_torque_from_slip(finger_fz=finger_fz, variance=variance)
        if not self.config.enable_phase4_ext:
            return torque_from_slip

        max_fz = max(finger_fz.values()) if finger_fz else 0.0
        load_ratio = max(0.0, min(1.0, max_fz / self.config.max_normal_force_per_finger))
        torque_ext = self.config.base_torque + (
            (self.config.max_torque - self.config.base_torque) * load_ratio * self.config.load_gain
        )
        torque_target = max(float(torque_from_slip), float(torque_ext))

        alpha = self.config.ext_smoothing_alpha
        torque_next = alpha * torque_target + (1.0 - alpha) * float(self.current_torque)
        return int(round(self._clamp_torque(torque_next)))

    def _clamp_torque(self, value: float) -> float:
        upper = min(100.0, float(self.config.max_torque))
        lower = -100.0
        if upper < lower:
            upper = lower
        return max(lower, min(upper, float(value)))

    def _get_open_pose(self) -> dict[JointId, float]:
        return {
            JointId.THUMB_PIP: math.radians(0),
            JointId.THUMB_MCP: math.radians(0),
            JointId.THUMB_SWING: math.radians(0),
            JointId.THUMB_ROTATION: math.radians(0),
            JointId.FF_PIP: math.radians(0),
            JointId.FF_MCP: math.radians(0),
            JointId.FF_SWING: math.radians(0),
            JointId.MF_PIP: math.radians(0),
            JointId.MF_MCP: math.radians(0),
            JointId.RF_PIP: math.radians(0),
            JointId.RF_MCP: math.radians(0),
            JointId.LF_PIP: math.radians(0),
            JointId.LF_MCP: math.radians(0),
        }
