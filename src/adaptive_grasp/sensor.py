import logging
import math
import time
from typing import Any, Optional

from ghand import ErrorCode, JointData, State, TactileInfo, TactileSensorId
from .utils import active_finger_normal_forces, normal_force_z

_logger = logging.getLogger("ghand.sensor")
_DEFAULT_FINGER_TOUCH_THRESHOLD_N = 0.1


class SensorClient:
    """统一封装灵巧手传感器数据的订阅、提取与缓存。

    通过 ``hand.subscribe()`` 后台接收 Tpdo，解析后缓存触觉数据和关节反馈，
    供控制器或其它模块以只读方式安全访问。
    """

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
        self._latest_tactile_data: Optional[dict[TactileSensorId, Any]] = None
        self._latest_joint_feedback: Optional[list[JointData]] = None
        self._last_sample_time_s: Optional[float] = None
        self._sub_id: Optional[int] = None
        self._get_monotonic_time = get_monotonic_time or time.monotonic

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def start(self) -> None:
        """开始订阅传感器数据并清空旧缓存。"""
        self._latest_tactile_data = None
        self._latest_joint_feedback = None
        self._sub_id = self._hand.subscribe(self._on_data)

    def stop(self, clear_joint_feedback: bool = False) -> None:
        """取消订阅，默认保留关节反馈缓存供后续阶段读取。"""
        if self._sub_id is not None:
            try:
                self._hand.unsubscribe(self._sub_id)
            except Exception:
                _logger.exception("Failed to unsubscribe sensor data")
            self._sub_id = None
        self._latest_tactile_data = None
        if clear_joint_feedback:
            self._latest_joint_feedback = None

    def reset(self) -> None:
        """清空所有缓存与时间戳。"""
        self._latest_tactile_data = None
        self._latest_joint_feedback = None
        self._last_sample_time_s = None

    # ------------------------------------------------------------------
    # 数据访问
    # ------------------------------------------------------------------
    @property
    def tactile_data(self) -> Optional[dict[TactileSensorId, Any]]:
        return self._latest_tactile_data

    @property
    def joint_feedback(self) -> Optional[list[JointData]]:
        return self._latest_joint_feedback

    @property
    def sample_time_s(self) -> Optional[float]:
        return self._last_sample_time_s

    def data_age_s(self, current_time: float) -> Optional[float]:
        if self._last_sample_time_s is None:
            return None
        return current_time - self._last_sample_time_s

    def sum_active_finger_normal_force(self) -> float:
        if self._latest_tactile_data is None:
            return 0.0
        normal_forces = active_finger_normal_forces(
            self._latest_tactile_data,
            self._active_fingers,
        )
        return sum(normal_forces.values())
    def active_finger_touch_flag(self) -> dict[TactileSensorId, bool]:
        # 判断活动手指是否都接触
        if self._latest_tactile_data is None:
            return {finger: False for finger in self._active_fingers}

        touch_flag: dict[TactileSensorId, bool] = {}
        for finger in self._active_fingers:
            info = self._latest_tactile_data.get(finger)
            touch_flag[finger] = (
                info is not None
                and info.state
                and normal_force_z(info) >= self._finger_touch_threshold_n
            )
        return touch_flag

    # ------------------------------------------------------------------
    # 内部回调
    # ------------------------------------------------------------------
    def _on_data(self, tpdo: Any) -> None:
        tactile_data = {
            TactileSensorId.THUMB: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 0)),
                resultant_force=tpdo.thumb_tactile.resultant_force,
                distributed_force=tpdo.thumb_tactile.sample_force,
            ),
            TactileSensorId.FF: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 1)),
                resultant_force=tpdo.ff_tactile.resultant_force,
                distributed_force=tpdo.ff_tactile.sample_force,
            ),
            TactileSensorId.MF: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 2)),
                resultant_force=tpdo.mf_tactile.resultant_force,
                distributed_force=tpdo.mf_tactile.sample_force,
            ),
            TactileSensorId.RF: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 3)),
                resultant_force=tpdo.rf_tactile.resultant_force,
                distributed_force=tpdo.rf_tactile.sample_force,
            ),
            TactileSensorId.LF: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 4)),
                resultant_force=tpdo.lf_tactile.resultant_force,
                distributed_force=tpdo.lf_tactile.sample_force,
            ),
        }
        self._latest_tactile_data = {
            finger: info
            for finger, info in tactile_data.items()
            if finger in self._active_fingers
        }
        self._last_sample_time_s = self._get_monotonic_time()


        joint_mappings = list(tpdo.joints.items())

        joints: list[JointData] = []
        for joint_id, joint_tpdo in joint_mappings:
            joints.append(
                JointData(
                    id=joint_id,
                    state=State(joint_tpdo.state),
                    error=ErrorCode(joint_tpdo.error),
                    angle=math.radians(joint_tpdo.angle),
                    speed=joint_tpdo.speed,
                    torque=joint_tpdo.torque,
                )
            )
        self._latest_joint_feedback = joints
