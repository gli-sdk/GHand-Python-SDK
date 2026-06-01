import json
import logging
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

import matplotlib
import matplotlib.pyplot as plt

from ghand import JointId, TactileSensorId
from .tactility import TactileAnalysis
from .utils import FINGER_TO_MCP_PIP, tactile_force_xyz

_logger = logging.getLogger("adaptive_grasp.visualization")

_PLOT_KEYS = ("fz", "ft", "s_k", "d_k", "r_k", "mcp_deg", "pip_deg")
_PLOT_TITLES = [
    "normal force Fz (N)",
    "tangential force Ft (N)",
    "s_k variance risk",
    "d_k direction risk",
    "r_k friction utilization",
    "MCP angle (deg)",
    "PIP angle (deg)",
]


class TactileVisualizer:
    """Render real-time tactile metrics for the active fingers."""

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
                "fz_ref": deque(maxlen=max_points),
                "ft": deque(maxlen=max_points),
                "s_k": deque(maxlen=max_points),
                "d_k": deque(maxlen=max_points),
                "r_k": deque(maxlen=max_points),
                "mcp_deg": deque(maxlen=max_points),
                "pip_deg": deque(maxlen=max_points),
            }
            for finger in self._active_fingers
        }

        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._detached = False

        self._figsize = (
            figsize_width,
            figsize_height_per_finger * max(len(self._active_fingers), 1),
        )

        self._fig: Optional[Any] = None
        self._axes: Optional[Any] = None
        self._lines: dict[TactileSensorId, dict[str, Any]] = {}
        self._plot_keys = _PLOT_KEYS

    def start(self) -> None:
        if self._running:
            return
        try:
            matplotlib.use(self._backend)
        except Exception as exc:
            _logger.warning(
                "Visualizer backend %s failed: %s, falling back to Agg",
                self._backend,
                exc,
            )
            matplotlib.use("Agg")
        self._running = True
        self._detached = False
        self._initialize_figure()

    def stop(self) -> None:
        """Stop background updates but keep the current figure state intact."""
        self._running = False

    def wait_until_closed(self) -> None:
        """Keep the current process alive until the user closes the window."""
        fig = self._fig
        if fig is None:
            return
        try:
            plt.ioff()
            plt.show(block=True)
        finally:
            figure_number = getattr(fig, "number", None)
            if figure_number is None or not plt.fignum_exists(figure_number):
                self._fig = None

    def poll(self) -> None:
        """Refresh the figure and process GUI events from the caller thread."""
        if self._running:
            self._draw_once()
        if self._fig is not None:
            self._fig.canvas.flush_events()

    def detach_window(self) -> None:
        """Persist a snapshot and show it in a detached viewer process."""
        if self._detached:
            return
        snapshot_path = self._write_snapshot_file()
        self._launch_snapshot_viewer(snapshot_path)
        self._detached = True

    def _write_snapshot_file(self) -> Path:
        snapshot_dir = Path(tempfile.gettempdir()) / "ghand_adaptive_grasp"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / f"snapshot_{int(time.time() * 1000)}.json"

        with self._lock:
            payload = {
                "active_fingers": [finger.value for finger in self._active_fingers],
                "timestamps": list(self._timestamps),
                "data": {
                    finger.value: {
                        key: list(self._data[finger][key])
                        for key in (*_PLOT_KEYS, "fz_ref")
                    }
                    for finger in self._active_fingers
                },
                "figsize": list(self._figsize),
                "titles": _PLOT_TITLES,
            }

        snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
        return snapshot_path

    def _launch_snapshot_viewer(self, snapshot_path: Path) -> None:
        command = [
            sys.executable,
            "-c",
            _snapshot_viewer_script(),
            str(snapshot_path),
            self._backend,
        ]
        kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": False,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        subprocess.Popen(command, **kwargs)

    def update(
        self,
        tactile_data: dict[TactileSensorId, Any],
        analysis: TactileAnalysis,
        joint_angles: Optional[dict[JointId, float]] = None,
        force_refs: Optional[dict[TactileSensorId, float]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        t = timestamp or time.monotonic()
        with self._lock:
            self._timestamps.append(t)
            for finger in self._active_fingers:
                info = tactile_data.get(finger)
                per = analysis.per_finger.get(finger)
                if info is not None and per is not None:
                    fx, fy, _ = tactile_force_xyz(info)
                    ft = math.hypot(fx, fy)
                    self._data[finger]["fz"].append(per.fz)
                    self._data[finger]["fz_ref"].append(
                        force_refs.get(finger) if force_refs is not None else None
                    )
                    self._data[finger]["ft"].append(ft)
                    self._data[finger]["s_k"].append(per.s_k)
                    self._data[finger]["d_k"].append(per.d_k)
                    self._data[finger]["r_k"].append(per.r_k)
                else:
                    for key in ("fz", "fz_ref", "ft", "s_k", "d_k", "r_k"):
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

    def _initialize_figure(self) -> None:
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

        for j, title in enumerate(_PLOT_TITLES):
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
                if key == "fz":
                    (ref_line,) = ax.plot([], [], "r-.", linewidth=1.0)
                    self._lines[finger]["fz_ref"] = ref_line
                ax.grid(True, alpha=0.3)

        for i in range(n):
            self._axes[i, 0].set_xlabel("Time (s)", fontsize=8)

    def _draw_once(self) -> None:
        with self._lock:
            if not self._timestamps or self._fig is None:
                return
            try:
                t_list = list(self._timestamps)
                n = len(self._active_fingers)
                for finger in self._active_fingers:
                    for key in self._plot_keys:
                        self._lines[finger][key].set_data(
                            t_list, list(self._data[finger][key])
                        )
                    self._lines[finger]["fz_ref"].set_data(
                        t_list,
                        list(self._data[finger]["fz_ref"]),
                    )

                for i in range(n):
                    for j in range(7):
                        self._axes[i, j].relim()
                        self._axes[i, j].autoscale_view()

                self._fig.canvas.draw_idle()
            except Exception:
                _logger.exception("Visualizer draw failed")


def _snapshot_viewer_script() -> str:
    return r"""
import json
import sys
from pathlib import Path

import matplotlib

snapshot_path = Path(sys.argv[1])
backend = sys.argv[2]
try:
    matplotlib.use(backend)
except Exception:
    matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
active_fingers = payload["active_fingers"]
timestamps = payload["timestamps"]
data = payload["data"]
titles = payload["titles"]
figsize = payload["figsize"]
plot_keys = ("fz", "ft", "s_k", "d_k", "r_k", "mcp_deg", "pip_deg")

n = max(len(active_fingers), 1)
fig, axes = plt.subplots(n, 7, figsize=figsize, sharex="col")
if n == 1:
    axes = axes.reshape(1, -1)

for j, title in enumerate(titles):
    axes[0, j].set_title(title, fontsize=10)

for i, finger in enumerate(active_fingers):
    axes[i, 0].set_ylabel(str(finger), rotation=0, ha="right", va="center", fontsize=9)
    finger_data = data[finger]
    for j, key in enumerate(plot_keys):
        ax = axes[i, j]
        ax.plot(timestamps, finger_data[key], linewidth=1.2)
        if key == "fz":
            ax.plot(timestamps, finger_data.get("fz_ref", []), "r-.", linewidth=1.0)
        ax.grid(True, alpha=0.3)

for i in range(n):
    axes[i, 0].set_xlabel("Time (s)", fontsize=8)
    for j in range(7):
        axes[i, j].relim()
        axes[i, j].autoscale_view()

plt.show(block=True)
"""
