import logging
import math
import threading
import time
from collections import deque
from typing import Any, Optional

import matplotlib
import matplotlib.pyplot as plt

from xiaoyao.dexhand import JointId, TactileInfo, TactileSensorId
from .tactility import TactileAnalysis
from .utils import FINGER_TO_MCP_PIP

_logger = logging.getLogger("xiaoyao.adaptive_grasp.visualization")


class TactileVisualizer:
    """实时绘制活动手指触觉指标的可视化工具。

    布局为 n×7 子图（n = 活动手指数）：
      第1列 法向力 | 第2列 切向力 | 第3列 方差 | 第4列 方向一致性 | 第5列 摩擦利用率
      第6列 MCP 角度 | 第7列 PIP 角度
    横轴为时间，纵轴为对应数值。
    """

    def __init__(
        self,
        active_fingers: set[TactileSensorId],
        max_points: int = 300,
        update_interval: float = 0.01,
        figsize_width: float = 16,
        figsize_height_per_finger: float = 2.5,
        backend: str = "TkAgg",
    ):
        self._active_fingers = list(active_fingers)
        self._max_points = max_points
        self._update_interval = update_interval
        self._backend = backend

        self._timestamps: deque[float] = deque(maxlen=max_points)
        self._data: dict[TactileSensorId, dict[str, deque[Optional[float]]]] = {
            finger: {
                "fz": deque(maxlen=max_points),
                "ft": deque(maxlen=max_points),
                "variance": deque(maxlen=max_points),
                "direction": deque(maxlen=max_points),
                "friction": deque(maxlen=max_points),
                "mcp_deg": deque(maxlen=max_points),
                "pip_deg": deque(maxlen=max_points),
            }
            for finger in self._active_fingers
        }

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._figsize = (
            figsize_width,
            figsize_height_per_finger * max(len(self._active_fingers), 1),
        )

        # matplotlib 对象在 start() 中初始化
        self._fig: Optional[Any] = None
        self._axes: Optional[Any] = None
        self._lines: dict[TactileSensorId, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def start(self) -> None:
        """启动后台绘图线程。"""
        if self._running:
            return
        try:
            matplotlib.use(self._backend)
        except Exception as exc:
            _logger.warning("Visualizer backend %s failed: %s, falling back to Agg", self._backend, exc)
            matplotlib.use("Agg")
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止绘图线程并关闭窗口。"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=20.0)
        if self._fig is not None:
            plt.close(self._fig)
            self._fig = None

    # ------------------------------------------------------------------
    # 数据更新（由外部控制循环调用）
    # ------------------------------------------------------------------
    def update(
        self,
        tactile_data: dict[TactileSensorId, Any],
        analysis: TactileAnalysis,
        joint_angles: Optional[dict[JointId, float]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """推送最新触觉数据与分析结果，加入缓存队列。"""
        t = timestamp or time.monotonic()
        with self._lock:
            self._timestamps.append(t)
            for finger in self._active_fingers:
                info = tactile_data.get(finger)
                per = analysis.per_finger.get(finger)
                if info is not None and per is not None:
                    fx = info.get_force_x()
                    fy = info.get_force_y()
                    ft = math.hypot(fx, fy)
                    self._data[finger]["fz"].append(per.fz)
                    self._data[finger]["ft"].append(ft)
                    self._data[finger]["variance"].append(per.variance)
                    self._data[finger]["direction"].append(per.d_k)
                    self._data[finger]["friction"].append(per.r_k)
                else:
                    for key in ("fz", "ft", "variance", "direction", "friction"):
                        self._data[finger][key].append(None)

                mcp_id, pip_id = FINGER_TO_MCP_PIP[finger]
                if joint_angles is not None:
                    mcp_angle = joint_angles.get(mcp_id)
                    pip_angle = joint_angles.get(pip_id)
                    self._data[finger]["mcp_deg"].append(
                        math.degrees(mcp_angle) if mcp_angle is not None else None
                    )
                    self._data[finger]["pip_deg"].append(
                        math.degrees(pip_angle) if pip_angle is not None else None
                    )
                else:
                    self._data[finger]["mcp_deg"].append(None)
                    self._data[finger]["pip_deg"].append(None)

    # ------------------------------------------------------------------
    # 内部绘图线程
    # ------------------------------------------------------------------
    def _run(self) -> None:
        plt.ion()
        n = len(self._active_fingers)
        try:
            self._fig, self._axes = plt.subplots(
                n, 7, figsize=self._figsize, sharex="col"
            )
        except Exception:
            _logger.exception("Visualizer backend failed during startup")
            self._running = False
            return
        if n == 1:
            self._axes = self._axes.reshape(1, -1)

        _PLOT_KEYS = ("fz", "ft", "variance", "direction", "friction", "mcp_deg", "pip_deg")
        titles = [
            "normal force Fz (N)", "tangential force Ft (N)", "Ft Variance",
            "Ft direction consistency", "tangential force Friction",
            "MCP angle (deg)", "PIP angle (deg)",
        ]
        for j, title in enumerate(titles):
            self._axes[0, j].set_title(title, fontsize=10)

        for i, finger in enumerate(self._active_fingers):
            self._axes[i, 0].set_ylabel(
                str(finger.value), rotation=0, ha="right", va="center", fontsize=9
            )
            self._lines[finger] = {}
            for j, key in enumerate(_PLOT_KEYS):
                ax = self._axes[i, j]
                (line,) = ax.plot([], [], linewidth=1.2)
                self._lines[finger][key] = line
                ax.grid(True, alpha=0.3)

        # 统一横轴标签
        for i in range(n):
            self._axes[i, 0].set_xlabel("Time (s)", fontsize=8)

        while self._running:
            with self._lock:
                if self._timestamps and self._fig is not None:
                    try:
                        t_list = list(self._timestamps)
                        for finger in self._active_fingers:
                            for key in _PLOT_KEYS:
                                self._lines[finger][key].set_data(
                                    t_list, list(self._data[finger][key]),
                                )

                        for i in range(n):
                            for j in range(7):
                                self._axes[i, j].relim()
                                self._axes[i, j].autoscale_view()

                        self._fig.canvas.draw_idle()
                        self._fig.canvas.flush_events()
                    except Exception:
                        _logger.exception("Visualizer draw failed")

            time.sleep(self._update_interval)

        plt.ioff()
        if self._fig is not None:
            plt.close(self._fig)
