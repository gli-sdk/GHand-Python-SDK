import logging
import time
from typing import Any, Optional

from ghand import JointData, TactileInfo, TactileSensorId
from ghand.comm.ethercat_comm import EthercatComm
from .utils import active_finger_normal_forces, normal_force_z, normalize_joint_id

_logger = logging.getLogger("ghand.sensor")
_DEFAULT_FINGER_TOUCH_THRESHOLD_N = 0.1


class SensorClient:
    """统一封装灵巧手传感器数据的订阅、提取与缓存。

    通过 ``hand.subscribe()`` 后台接收统一的 ``DeviceData``，缓存触觉数据和关节反馈，
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
    def _on_data(self, data: Any) -> None:
        if not (hasattr(data, "tactile") and hasattr(data, "joints")):
            raise TypeError(
                "SensorClient subscription callback expects ghand.DeviceData; "
                "legacy TPDO parsing is not supported."
            )

        tactile = getattr(data, "tactile", None)
        if tactile is None:
            self._latest_tactile_data = None
        else:
            self._latest_tactile_data = {
                TactileSensorId(finger): info
                for finger, info in tactile.items()
                if TactileSensorId(finger) in self._active_fingers
            }
        self._last_sample_time_s = self._get_monotonic_time()

        self._latest_joint_feedback = [
            JointData(
                id=normalize_joint_id(joint_data.id),
                state=joint_data.state,
                error=joint_data.error,
                angle=joint_data.angle,
                speed=joint_data.speed,
                torque=joint_data.torque,
            )
            for joint_data in getattr(data, "joints", ())
        ]
