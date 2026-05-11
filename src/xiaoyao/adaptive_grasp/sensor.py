import logging
import time
from typing import Any, Optional

from xiaoyao.dexhand import DexHand, Joint, JointId, State, ErrorCode, TactileInfo, TactileSensorId
from xiaoyao.data import Tpdo

_logger = logging.getLogger("xiaoyao.sensor")
_DEFAULT_TOUCH_DETECT_FORCE_THRESHOLD_N = 0.1


class SensorClient:
    """统一封装灵巧手传感器数据的订阅、提取与缓存。

    通过 ``hand.subscribe()`` 后台接收 Tpdo，解析后缓存触觉数据和关节反馈，
    供控制器或其它模块以只读方式安全访问。
    """

    def __init__(
        self,
        hand: DexHand,
        active_fingers: Optional[set[TactileSensorId]] = None,
        touch_detect_force_threshold_n: float = _DEFAULT_TOUCH_DETECT_FORCE_THRESHOLD_N,
        get_monotonic_time: Optional[Any] = None,
    ):
        self._hand = hand
        self._touch_detect_force_threshold_n = touch_detect_force_threshold_n
        self._active_fingers = active_fingers or {
            TactileSensorId.THUMB,
            TactileSensorId.FOREFINGER,
            TactileSensorId.MIDDLE_FINGER,
            TactileSensorId.RING_FINGER,
            TactileSensorId.LITTLE_FINGER,
        }
        self._latest_tactile_data: Optional[dict[TactileSensorId, Any]] = None
        self._latest_joint_feedback: Optional[list[Joint]] = None
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
    def joint_feedback(self) -> Optional[list[Joint]]:
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
        return sum(
            abs(info.get_force_z())
            for finger, info in self._latest_tactile_data.items()
            if finger in self._active_fingers
        )
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
                and abs(info.get_force_z()) >= self._touch_detect_force_threshold_n
            )
        return touch_flag

    # ------------------------------------------------------------------
    # 内部回调
    # ------------------------------------------------------------------
    def _on_data(self, tpdo: Tpdo) -> None:
        tactile_data = {
            TactileSensorId.THUMB: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 0)),
                resultant_force=tpdo.thumb_tactile.resultant_force,
                distributed_force=tpdo.thumb_tactile.sample_force,
            ),
            TactileSensorId.FOREFINGER: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 1)),
                resultant_force=tpdo.ff_tactile.resultant_force,
                distributed_force=tpdo.ff_tactile.sample_force,
            ),
            TactileSensorId.MIDDLE_FINGER: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 2)),
                resultant_force=tpdo.mf_tactile.resultant_force,
                distributed_force=tpdo.mf_tactile.sample_force,
            ),
            TactileSensorId.RING_FINGER: TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << 3)),
                resultant_force=tpdo.rf_tactile.resultant_force,
                distributed_force=tpdo.rf_tactile.sample_force,
            ),
            TactileSensorId.LITTLE_FINGER: TactileInfo(
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

        joint_mappings = [
            (JointId.THUMB_DIP, tpdo.th_dip),
            (JointId.THUMB_PIP, tpdo.th_pip),
            (JointId.THUMB_MCP, tpdo.th_mcp),
            (JointId.THUMB_SWING, tpdo.th_swing),
            (JointId.THUMB_ROTATION, tpdo.th_rot),
            (JointId.FF_DIP, tpdo.ff_dip),
            (JointId.FF_PIP, tpdo.ff_pip),
            (JointId.FF_MCP, tpdo.ff_mcp),
            (JointId.FF_SWING, tpdo.ff_swing),
            (JointId.MF_DIP, tpdo.mf_dip),
            (JointId.MF_PIP, tpdo.mf_pip),
            (JointId.MF_MCP, tpdo.mf_mcp),
            (JointId.RF_DIP, tpdo.rf_dip),
            (JointId.RF_PIP, tpdo.rf_pip),
            (JointId.RF_MCP, tpdo.rf_mcp),
            (JointId.LF_DIP, tpdo.lf_dip),
            (JointId.LF_PIP, tpdo.lf_pip),
            (JointId.LF_MCP, tpdo.lf_mcp),
        ]
        joints: list[Joint] = []
        for joint_id, joint_tpdo in joint_mappings:
            joints.append(
                Joint(
                    id=joint_id,
                    angle=joint_tpdo.angle,
                    speed=joint_tpdo.speed,
                    torque=joint_tpdo.torque,
                    state=State(joint_tpdo.state),
                    error=ErrorCode(joint_tpdo.error),
                )
            )
        self._latest_joint_feedback = joints
