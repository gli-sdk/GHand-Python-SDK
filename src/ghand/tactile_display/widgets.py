# SPDX-FileCopyrightText: 2026 GLITech
# SPDX-License-Identifier: Apache-2.0
"""Small custom widgets used by the tactile display."""

import math
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
                           QRadialGradient)
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from ghand.types import TactileSensorId


FINGER_NAMES = {
    TactileSensorId.THUMB: "Thumb",
    TactileSensorId.FF: "Index Finger",
    TactileSensorId.MF: "Middle Finger",
    TactileSensorId.RF: "Ring Finger",
    TactileSensorId.LF: "Little Finger",
}

_ASSETS = Path(__file__).with_name("assets")

THUMB_POINTS = (
    (18.55, 315.35), (14.75, 250.75), (16.65, 189.0), (24.25, 125.35), (35.65, 75.95),
    (59.4, 325.8), (57.5, 263.1), (57.5, 189.0), (65.1, 118.7), (71.75, 69.3),
    (97.4, 332.45), (99.3, 266.9), (98.35, 189.0), (105.95, 114.9), (105.95, 63.6),
    (74.6, 35.1), (143.0, 337.2), (143.0, 268.8), (143.0, 189.0), (142.05, 111.1),
    (142.05, 57.9), (143.0, 10.4), (187.65, 332.45), (188.6, 266.9), (189.55, 189.0),
    (184.8, 114.9), (177.2, 63.6), (210.45, 34.15), (229.45, 323.9), (232.3, 261.2),
    (232.3, 189.0), (228.5, 119.65), (212.35, 69.3), (268.4, 315.35), (274.1, 250.75),
    (275.05, 189.0), (269.35, 125.35), (247.5, 75.95),
)

FINGER_POINTS = (
    (28.5725, 328.0545), (20.0225, 284.3545), (20.0225, 230.2045), (21.9225, 181.7545),
    (35.2225, 109.5545), (67.5225, 47.8045), (79.8725, 338.457), (81.7725, 289.957),
    (82.7225, 230.2045), (84.6225, 177.9545), (85.525, 118.1045), (94.1225, 73.4545),
    (142.05, 343.15), (143.0, 293.75), (143.0, 230.1), (143.0, 175.0), (143.0, 123.7),
    (143.0, 79.05), (143.0, 30.6), (201.9, 337.45), (201.9, 289.95), (201.9, 230.1),
    (202.85, 177.85), (200.0, 117.05), (189.55, 74.3), (259.85, 328.0), (267.45, 284.3),
    (267.45, 230.1), (263.65, 181.65), (248.45, 111.35), (213.3, 47.7),
)


_DOT_STOPS = ((0.1, "#0DFF00"), (6.25, "#EEFF00"), (12.5, "#FFB700"),
              (18.75, "#FF8502"), (25.0, "#FF0004"))
_ARROW_STOPS = ((0.0, "#0DFF00"), (2.5, "#EEFF00"), (5.0, "#FFB700"),
                (7.5, "#FF8502"), (10.0, "#FF0004"))


def _interpolate_color(value: float, stops, default: QColor, absolute: bool = False) -> QColor:  # type: ignore[no-untyped-def]
    value = abs(value) if absolute else value
    if value < stops[0][0]:
        return default
    if value >= stops[-1][0]:
        return QColor(stops[-1][1])
    for (low, low_color), (high, high_color) in zip(stops, stops[1:]):
        if low <= value <= high:
            ratio = (value - low) / (high - low)
            start, end = QColor(low_color), QColor(high_color)
            return QColor(int(start.red() + ratio * (end.red() - start.red())),
                          int(start.green() + ratio * (end.green() - start.green())),
                          int(start.blue() + ratio * (end.blue() - start.blue())))
    return QColor("#FF0004")


def _qround(value: float) -> int:
    return math.floor(value + 0.5)


def _draw_marker(painter: QPainter, center: QPointF, force: tuple[float, float, float],
                 scale: float, *, overview: bool, rotation: float = 0.0) -> None:
    fx, fy, fz = force
    magnitude = min(math.hypot(fx, fy), 15.0)
    rounded_magnitude = _qround(magnitude)
    if rounded_magnitude > 0:
        if overview:
            arrow_size, circle_diameter = min(8 + (rounded_magnitude - 1) * 2, 44), 49
        else:
            arrow_size, circle_diameter = min(3 + rounded_magnitude - 1, 12), 27
        radius = circle_diameter / 2
        angle = math.atan2(-fy, fx) + math.pi / 2 + math.radians(rotation)
        painter.save()
        painter.translate(center)
        painter.rotate(math.degrees(angle))
        color = _interpolate_color(magnitude, _ARROW_STOPS, QColor("#0DFF00"), True)
        triangle = QPainterPath()
        polygon = QPolygonF([
            QPointF(0, -(radius + arrow_size) * scale),
            QPointF(radius * math.cos(math.radians(240)) * scale,
                    radius * math.sin(math.radians(240)) * scale),
            QPointF(radius * math.cos(math.radians(300)) * scale,
                    radius * math.sin(math.radians(300)) * scale),
        ])
        triangle.addPolygon(polygon)
        circle = QPainterPath()
        circle.addEllipse(QPointF(0, 0), radius * scale, radius * scale)
        painter.setBrush(color)
        painter.setPen(QPen(color, max(scale, 1.0)))
        painter.drawPath(triangle.subtracted(circle))
        if overview:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), radius * scale, radius * scale)
        painter.restore()

    value = max(0.0, min(fz, 25.0))
    rounded = _qround(value)
    if overview:
        diameter = 0 if rounded <= 0 else min(7 + (rounded - 1) * 2, 41)
        default = QColor(0, 255, 0)
    else:
        diameter = 2 if rounded <= 0 else min(4 + rounded - 1, 25)
        default = QColor(255, 255, 255, 128)
    if diameter <= 0:
        return
    color = _interpolate_color(value, _DOT_STOPS, default)
    radius = diameter * scale / 2
    glow_radius = radius * 2
    gradient = QRadialGradient(center, glow_radius)
    gradient.setColorAt(0.5, QColor(color.red(), color.green(), color.blue(), 90))
    gradient.setColorAt(0.7, QColor(color.red(), color.green(), color.blue(), 70))
    gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawEllipse(center, glow_radius, glow_radius)
    painter.setBrush(color)
    painter.drawEllipse(center, radius, radius)


class FingerMapWidget(QWidget):

    def __init__(self, finger: TactileSensorId, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.finger = finger
        self.points = THUMB_POINTS if finger == TactileSensorId.THUMB else FINGER_POINTS
        stem = "thumb" if finger == TactileSensorId.THUMB else "four_fingers"
        self.background = QPixmap(str(_ASSETS / f"{stem}.png"))
        self.overlay = QPixmap(str(_ASSETS / f"{stem}1.png"))
        self.forces: tuple[tuple[float, float, float], ...] = ()
        self.setMinimumSize(150, 220)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_forces(self, forces: tuple[tuple[float, float, float], ...]) -> None:
        self.forces = forces if len(forces) == len(self.points) else ()
        self.update()

    def _mapped_points(self) -> list[QPointF]:
        rect, scale = self._image_rect()
        return [QPointF(rect.left() + (11 + x) * scale,
                        rect.top() + (21 + y) * scale) for x, y in self.points]

    def _image_rect(self) -> tuple[QRectF, float]:
        available = self.rect().adjusted(6, 28, -6, -6)
        scale = min(available.width() / 312.0, available.height() / 419.0)
        width, height = 312 * scale, 419 * scale
        return QRectF(available.center().x() - width / 2, available.center().y() - height / 2,
                      width, height), scale

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#dbe8f5"))
        painter.drawText(QRectF(0, 3, self.width(), 24), Qt.AlignmentFlag.AlignCenter,
                         FINGER_NAMES[self.finger])
        image_rect, scale = self._image_rect()
        painter.drawPixmap(image_rect, self.background, QRectF(self.background.rect()))
        overlay_rect = QRectF(image_rect.left() + 8 * scale, image_rect.top() + 18 * scale,
                              292 * scale, 370 * scale)
        painter.save()
        painter.setOpacity(1.0)
        painter.drawPixmap(overlay_rect, self.overlay, QRectF(self.overlay.rect()))
        painter.restore()
        mapped = self._mapped_points()
        for index, center in enumerate(mapped):
            force = self.forces[index] if index < len(self.forces) else (0.0, 0.0, 0.0)
            _draw_marker(painter, center, force, scale, overview=False)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self.forces:
            self.setToolTip("No valid data available")
            return
        position = event.position()
        nearest = min(range(len(self.points)),
                      key=lambda index: (self._mapped_points()[index] - position).manhattanLength())
        if (self._mapped_points()[nearest] - position).manhattanLength() < 16:
            fx, fy, fz = self.forces[nearest]
            self.setToolTip(f"#{nearest}: Fx {fx:.1f} N, Fy {fy:.1f} N, Fz {fz:.1f} N")
        else:
            self.setToolTip("")


class HandOverviewWidget(QWidget):

    _POSITIONS = {
        "right": {
            TactileSensorId.THUMB: (443, 179), TactileSensorId.FF: (252, -14),
            TactileSensorId.MF: (168, -18), TactileSensorId.RF: (91, -8),
            TactileSensorId.LF: (20, 53),
        },
        "left": {
            TactileSensorId.THUMB: (42, 235), TactileSensorId.FF: (220, -3),
            TactileSensorId.MF: (303, -21), TactileSensorId.RF: (381, -17),
            TactileSensorId.LF: (452, 33),
        },
    }

    _TORQUE_POSITIONS = {
        "right": {
            TactileSensorId.THUMB: (404, 213), TactileSensorId.FF: (323, 30),
            TactileSensorId.MF: (183, 18), TactileSensorId.RF: (109, 35),
            TactileSensorId.LF: (43, 113),
        },
        "left": {
            TactileSensorId.THUMB: (155, 211), TactileSensorId.FF: (240, 53),
            TactileSensorId.MF: (379, 19), TactileSensorId.RF: (451, 35),
            TactileSensorId.LF: (520, 106),
        },
    }

    def __init__(self, side: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.side = side
        self.hand = QPixmap(str(_ASSETS / f"{side}_hand_icon.png"))
        self.forces = {finger: (math.nan, math.nan, math.nan) for finger in FINGER_NAMES}
        self.setMinimumHeight(300)

    def set_side(self, side: str) -> None:
        if side != self.side:
            self.side = side
            self.hand = QPixmap(str(_ASSETS / f"{side}_hand_icon.png"))
            self.update()

    def set_forces(self, forces: dict[TactileSensorId, tuple[float, float, float]]) -> None:
        self.forces = forces
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = min(self.width() / 586.0, self.height() / 625.0)
        scene = QRectF((self.width() - 586 * scale) / 2, (self.height() - 625 * scale) / 2,
                       586 * scale, 625 * scale)
        image_scale = min(scene.width() / self.hand.width(), scene.height() / self.hand.height())
        image_rect = QRectF(scene.center().x() - self.hand.width() * image_scale / 2,
                            scene.center().y() - self.hand.height() * image_scale / 2,
                            self.hand.width() * image_scale, self.hand.height() * image_scale)
        painter.drawPixmap(image_rect, self.hand, QRectF(self.hand.rect()))
        rotations = {TactileSensorId.THUMB: 30, TactileSensorId.FF: 6.77,
                     TactileSensorId.MF: 0, TactileSensorId.RF: -4,
                     TactileSensorId.LF: -8.04} if self.side == "right" else {
                         TactileSensorId.THUMB: -30, TactileSensorId.FF: -6.77,
                         TactileSensorId.MF: 0, TactileSensorId.RF: 4,
                         TactileSensorId.LF: 8.04}
        for finger, position in self._POSITIONS[self.side].items():
            angle = math.radians(rotations[finger])
            local_x = 58 * math.cos(angle) - 58 * math.sin(angle)
            local_y = 58 * math.sin(angle) + 58 * math.cos(angle)
            center = QPointF(scene.left() + (position[0] + local_x) * scale,
                             scene.top() + (position[1] + local_y) * scale)
            force = self.forces.get(finger, (math.nan, math.nan, math.nan))
            if not all(math.isfinite(value) for value in force):
                continue
            _draw_marker(painter, center, force, scale, overview=True,
                         rotation=rotations[finger])
            self._paint_fz_bar(painter, finger, force[2], scene, scale)

    def _paint_fz_bar(self, painter: QPainter, finger: TactileSensorId, fz: float,
                      scene: QRectF, scale: float) -> None:
        x, y = self._TORQUE_POSITIONS[self.side][finger]
        left, top = scene.left() + x * scale, scene.top() + y * scale
        width, text_width = 24 * scale, 40 * scale
        text_rect_x = left + (width - text_width) / 2
        painter.save()
        font = painter.font()
        font.setPixelSize(max(8, round(13 * scale)))
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRectF(text_rect_x, top + 5 * scale, text_width, 18 * scale),
                         Qt.AlignmentFlag.AlignCenter, f"{fz:.1f}")
        bar = QRectF(left + 8 * scale, top + 29 * scale, 8 * scale, 31 * scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#D5D5D5"))
        painter.drawRoundedRect(bar, 4 * scale, 4 * scale)
        ratio = max(0.0, min(fz, 25.0)) / 25.0
        if ratio > 0:
            filled = QRectF(bar.left(), bar.bottom() - bar.height() * ratio,
                            bar.width(), bar.height() * ratio)
            painter.setBrush(_interpolate_color(fz, _DOT_STOPS, QColor("#0DFF00")))
            painter.drawRoundedRect(filled, 4 * scale, 4 * scale)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRectF(text_rect_x, top + 66 * scale, text_width, 18 * scale),
                         Qt.AlignmentFlag.AlignCenter, "Fz")
        painter.restore()


class _ForceAxis(pg.AxisItem):
    """Left axis whose label is drawn horizontally beside the tick values."""

    def __init__(self, orientation: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(orientation, **kwargs)
        self.label.setRotation(0)
        self.setWidth(80)

    def resizeEvent(self, event=None) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        if self.label is None:
            return
        rect = self.label.boundingRect()
        self.label.setPos(2, (self.size().height() - rect.height()) / 2)


class ForcePlots(QWidget):

    COLORS = ("#e74c3c", "#27ae60", "#3498db")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.plots: dict[TactileSensorId, pg.PlotWidget] = {}
        self.curves: dict[TactileSensorId, tuple[pg.PlotDataItem, ...]] = {}
        for finger in FINGER_NAMES:
            plot = pg.PlotWidget(title=FINGER_NAMES[finger],
                                 axisItems={"left": _ForceAxis("left")})
            plot.setXRange(-60, 0, padding=0)
            plot.setYRange(-10, 25, padding=0)
            plot.setLabel("left", "F", units="N")
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.addLegend(offset=(5, 5))
            curves = tuple(plot.plot(name=axis, pen=pg.mkPen(color, width=1.5))
                           for axis, color in zip(("Fx", "Fy", "Fz"), self.COLORS))
            self.plots[finger] = plot
            self.curves[finger] = curves
            layout.addWidget(plot, 1)

    def set_history(self, history, now: float) -> None:  # type: ignore[no-untyped-def]
        x = [timestamp - now for timestamp, _ in history]
        for finger, curves in self.curves.items():
            for axis, curve in enumerate(curves):
                curve.setData(x, [forces[finger][axis] for _, forces in history])
