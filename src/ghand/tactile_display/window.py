# SPDX-FileCopyrightText: 2026 GLITech
# SPDX-License-Identifier: Apache-2.0
"""Reusable tactile display; device ownership stays with the caller."""

from collections import deque
import math
import threading
import time
from typing import Any

from PySide6.QtCore import QRectF, QSize, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import (QAbstractButton, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QSplitter, QVBoxLayout, QWidget)

from ghand.types import TactileSensorId
from .widgets import FingerMapWidget, ForcePlots, HandOverviewWidget

_FINGERS = tuple(TactileSensorId)
_COUNTS = {TactileSensorId.THUMB: 38, TactileSensorId.FF: 31, TactileSensorId.MF: 31,
           TactileSensorId.RF: 31, TactileSensorId.LF: 31}
_INVALID = (math.nan, math.nan, math.nan)


class _TactileDataStore:
    """Copy callback data and retain bounded 60-second resultant history."""

    def __init__(self, point_counts=None) -> None:  # type: ignore[no-untyped-def]
        self._counts = point_counts or _COUNTS
        self._lock = threading.Lock()
        self._pending, self._history = deque(maxlen=3100), deque(maxlen=3100)
        self._distributed = {}
        self._generation = 0
        self.dropped_samples = 0

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def reset(self) -> int:
        with self._lock:
            self._generation += 1
            self._pending.clear(); self._history.clear(); self._distributed.clear()
            self.dropped_samples = 0
            return self._generation

    def invalidate(self) -> int:
        with self._lock:
            self._generation += 1
            self._pending.clear(); self._distributed.clear()
            return self._generation

    def ingest(self, tactile, generation: int, timestamp: float | None = None) -> bool:  # type: ignore[no-untyped-def]
        timestamp = time.monotonic() if timestamp is None else timestamp
        resultants = {finger: _INVALID for finger in _FINGERS}
        distributed = {}
        for key, info in (tactile or {}).items():
            try:
                finger = TactileSensorId(key)
            except (TypeError, ValueError):
                continue
            if not getattr(info, "state", False):
                continue
            force = self._force3(getattr(info, "resultant_force", None))
            if force is not None:
                resultants[finger] = force
            values = getattr(info, "distributed_force", None)
            expected = self._counts.get(finger, 0) * 3
            try:
                valid_length = len(values) == expected
            except TypeError:
                valid_length = False
            if valid_length:
                points = tuple(self._force3(values[i:i + 3]) for i in range(0, expected, 3))
                if all(point is not None for point in points):
                    distributed[finger] = points
        with self._lock:
            if generation != self._generation:
                return False
            sample = (timestamp, resultants)
            bucket = int(timestamp * 50.0 + 1e-7)
            if self._pending and int(self._pending[-1][0] * 50.0 + 1e-7) == bucket:
                self._pending[-1] = sample
            else:
                if len(self._pending) == self._pending.maxlen:
                    self.dropped_samples += 1
                self._pending.append(sample)
            self._distributed = distributed
            return True

    def drain(self, now: float | None = None):  # type: ignore[no-untyped-def]
        now = time.monotonic() if now is None else now
        with self._lock:
            if self._history and self._pending and self._pending[0][0] - self._history[-1][0] > .5:
                self._history.append((self._history[-1][0] + .5,
                                      {finger: _INVALID for finger in _FINGERS}))
            self._history.extend(self._pending); self._pending.clear()
            if self._history and now - self._history[-1][0] > .5:
                self._history.append((self._history[-1][0] + .5,
                                      {finger: _INVALID for finger in _FINGERS}))
            while self._history and self._history[0][0] < now - 60:
                self._history.popleft()
            return tuple(self._history), dict(self._distributed)

    @staticmethod
    def _force3(values: Any):  # type: ignore[no-untyped-def]
        try:
            force = tuple(float(value) for value in values) if len(values) == 3 else None
        except (TypeError, ValueError, OverflowError):
            return None
        return force if force is not None and all(math.isfinite(value) for value in force) else None


class _SwitchButton(QAbstractButton):
    """Checkable slider switch, checked when ON."""

    _TRACK_WIDTH, _TRACK_HEIGHT = 44, 22

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 8 + self._TRACK_WIDTH, 30)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(.4)
        height, label_width = self.height(), self.fontMetrics().horizontalAdvance(self.text())
        track = QRectF(label_width + 8, (height - self._TRACK_HEIGHT) / 2,
                       self._TRACK_WIDTH, self._TRACK_HEIGHT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#2e7d32") if self.isChecked() else QColor("#b8b8b8"))
        painter.drawRoundedRect(track, self._TRACK_HEIGHT / 2, self._TRACK_HEIGHT / 2)
        knob = self._TRACK_HEIGHT - 4
        knob_x = track.right() - knob - 2 if self.isChecked() else track.left() + 2
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(knob_x, track.top() + 2, knob, knob))
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        painter.drawText(QRectF(0, 0, label_width + 2, height),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


class TactileWindow(QMainWindow):
    """Render tactile data and emit control requests without opening a device.

    Call update_tactile from an SDK callback. Connect the request signals to
    application-owned device operations and report their results using
    set_connected and set_command_result. Callers own subscriptions and cleanup.
    """

    open_requested = Signal(int)
    close_requested = Signal()
    zero_requested = Signal()

    def __init__(self, side: str = "right") -> None:
        super().__init__()
        self.side = side
        self._data = _TactileDataStore()
        self._connected = self._tactile_opened = False
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(Qt.GlobalColor.black))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
        self.setPalette(palette)
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(33)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()
        self._buttons()

    @property
    def data_generation(self) -> int:
        """Return the token used to reject callbacks from an old subscription."""
        return self._data.generation

    def update_tactile(self, tactile, generation: int | None = None) -> bool:  # type: ignore[no-untyped-def]
        """Copy a tactile frame; safe to call from a subscription thread.

        Capture data_generation when subscribing and pass it on every callback
        to reject stale frames after clear or invalidate.
        """
        if generation is None:
            generation = self.data_generation
        return self._data.ingest(tactile, generation)

    def clear(self) -> int:
        """Clear cached data and return a new generation; thread safe."""
        return self._data.reset()

    def invalidate(self) -> int:
        """Reject old callbacks and clear live data, retaining history; thread safe."""
        return self._data.invalidate()

    def _build_ui(self) -> None:
        self.setWindowTitle("GHand Tactile Display"); self.resize(1600, 1000)
        split, left = QSplitter(Qt.Orientation.Horizontal), QWidget()
        column = QVBoxLayout(left)
        controls, row = QWidget(), QHBoxLayout()
        controls.setLayout(row)
        self.tactile_switch, self.zero_button = _SwitchButton("Tactile"), QPushButton("Zero Tactile")
        self.state_label = QLabel()
        row.addWidget(self.tactile_switch); row.addWidget(self.zero_button)
        row.addWidget(self.state_label, 1); column.addWidget(controls)
        self.tactile_switch.toggled.connect(self._toggle_tactile)
        self.zero_button.clicked.connect(self._zero)
        group, layout = QWidget(), QVBoxLayout()
        group.setLayout(layout); self.overview = HandOverviewWidget(self.side); layout.addWidget(self.overview)
        column.addWidget(group, 5)
        group, row = QWidget(), QHBoxLayout(); group.setLayout(row)
        self.finger_maps = {finger: FingerMapWidget(finger) for finger in _FINGERS}
        for widget in self.finger_maps.values(): row.addWidget(widget, 1)
        column.addWidget(group, 2)
        group, layout = QWidget(), QVBoxLayout(); group.setLayout(layout)
        self.force_plots = ForcePlots(); layout.addWidget(self.force_plots)
        split.addWidget(left)
        split.addWidget(group)
        split.setStretchFactor(0, 9)
        split.setStretchFactor(1, 7)
        split.setSizes([900, 700])
        self.setCentralWidget(split)

    def _toggle_tactile(self, checked: bool) -> None:
        if checked:
            self._open()
        else:
            self._close()

    def _open(self) -> None:
        generation = self.clear()
        self._buttons(True)
        self.open_requested.emit(generation)

    def _close(self) -> None:
        self.invalidate()
        self._buttons(True)
        self.close_requested.emit()

    def _zero(self) -> None:
        self._buttons(True)
        self.set_status("Keep the sensor unloaded; zeroing…")
        self.zero_requested.emit()

    @Slot(str)
    def set_side(self, side: str) -> None:
        self.side = side
        self.overview.set_side(side)

    @Slot(bool, str)
    def set_connected(self, ok: bool, message: str) -> None:
        self._connected = ok; self.set_status(message); self._buttons()

    @Slot(str, bool, str)
    def set_command_result(self, operation: str, ok: bool, message: str) -> None:
        if operation == "open": self._tactile_opened = ok
        if operation == "close" and ok: self._tactile_opened = False
        self.set_status(message); self._buttons()

    def _buttons(self, busy: bool = False) -> None:
        enabled = not busy and self._connected
        self.tactile_switch.setEnabled(enabled)
        if not busy:
            self.tactile_switch.blockSignals(True)
            self.tactile_switch.setChecked(self._tactile_opened)
            self.tactile_switch.blockSignals(False)
        self.zero_button.setEnabled(enabled and self._tactile_opened)

    def set_status(self, message: str) -> None:
        self.state_label.setText(message)

    def _refresh(self) -> None:
        now = time.monotonic(); history, distributed = self._data.drain(now)
        self.force_plots.set_history(history, now)
        self.overview.set_forces(history[-1][1] if history else {})
        for finger, widget in self.finger_maps.items(): widget.set_forces(distributed.get(finger, ()))

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._refresh_timer.stop()
        self.invalidate()
        super().closeEvent(event)
