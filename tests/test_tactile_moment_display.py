"""Offscreen Qt behavior tests; no device connection or SDK worker thread."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch

import numpy as np
import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter

from ghand.types import TactileData, TactileSensorId
from ghand.tactile_display.window import TactileWindow
from ghand.tactile_display import widgets


FF = TactileSensorId.FF


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def reading(**kw):
    return TactileData(state=True, error=0, raw_state=31,
                       resultant_force=[1, 2, 3], distributed_force=[0, 0, 1] * 31,
                       resultant_moment=[.01, -.02, .03],
                       moment_reference_point_m=[0, 0, 0], **kw)


def test_window_shows_signed_moments_units_and_history(app):
    window = TactileWindow()
    try:
        assert window.wrench_tabs.tabText(1) == "Moment (N·m)"
        assert "sensor CAD" in window.moment_frame_label.text()
        assert window.moment_plots.plots[FF].getAxis("left").autoSIPrefixScale == 1
        assert window._data.ingest({FF: reading()}, window.data_generation, timestamp=10.)
        with patch("ghand.tactile_display.window.time.monotonic", return_value=10.1):
            window._refresh()
        assert window.moment_table.item(1, 1).text() == "+0.01000"
        assert window.moment_table.item(1, 2).text() == "-0.02000"
        assert "0" in window.moment_table.item(1, 4).text()
        x, y = window.moment_plots.curves[FF][1].getData()
        np.testing.assert_allclose(y, [-.02])
        assert window.moment_table.item(0, 1).text() == "—"
        window.show()
        app.processEvents()
    finally:
        window.close()


def test_stale_and_invalid_moments_are_not_shown_as_zero(app):
    window = TactileWindow()
    try:
        generation = window.data_generation
        window._data.ingest({FF: reading()}, generation, timestamp=10.)
        with patch("ghand.tactile_display.window.time.monotonic", return_value=10.6):
            window._refresh()
        assert window.moment_table.item(1, 1).text() == "—"
        _, y = window.moment_plots.curves[FF][0].getData()
        assert np.isnan(y[-1])
        assert not window.finger_maps[FF].forces
        invalid = reading()
        invalid.error = 4
        window._data.ingest({FF: invalid}, generation, timestamp=11.)
        with patch("ghand.tactile_display.window.time.monotonic", return_value=11.1):
            window._refresh()
        assert window.moment_table.item(1, 1).text() == "—"
    finally:
        window.close()


def test_reset_and_invalidate_clear_live_moments_reject_old_generation(app):
    window = TactileWindow()
    try:
        generation = window.data_generation
        window.update_tactile({FF: reading()}, generation)
        window._refresh()
        assert window.moment_table.item(1, 1).text() == "+0.01000"
        window.invalidate()
        window._refresh()
        assert window.moment_table.item(1, 1).text() == "—"
        assert not window.update_tactile({FF: reading()}, generation)
        window.clear()
        window._refresh()
        assert window.moment_table.item(1, 4).text() == "—"
        x, _ = window.moment_plots.curves[FF][0].getData()
        assert x is None or len(x) == 0
    finally:
        window.close()


def test_missing_moment_and_reference_change_break_curves(app):
    window = TactileWindow()
    try:
        generation = window.data_generation
        window._data.ingest({FF: reading()}, generation, timestamp=10.)
        changed = reading()
        changed.moment_reference_point_m = [0, 0, .01]
        window._data.ingest({FF: changed}, generation, timestamp=10.1)
        with patch("ghand.tactile_display.window.time.monotonic", return_value=10.2):
            window._refresh()
        _, y = window.moment_plots.curves[FF][0].getData()
        assert np.isnan(y).any(), "changing the moment origin must break the curve"
        missing = reading()
        missing.resultant_moment = None
        window._data.ingest({FF: missing}, generation, timestamp=10.3)
        with patch("ghand.tactile_display.window.time.monotonic", return_value=10.4):
            window._refresh()
        assert window.moment_table.item(1, 1).text() == "—"
    finally:
        window.close()


def test_stream_gap_breaks_curve_even_when_gui_has_not_refreshed(app):
    window = TactileWindow()
    try:
        generation = window.data_generation
        window._data.ingest({FF: reading()}, generation, timestamp=10.)
        window._data.ingest({FF: reading()}, generation, timestamp=11.)
        with patch("ghand.tactile_display.window.time.monotonic", return_value=11.1):
            window._refresh()
        _, y = window.moment_plots.curves[FF][0].getData()
        assert np.isnan(y).any()
        assert y[-1] == .01
    finally:
        window.close()


def test_recovered_stream_history_remains_chronological(app):
    window = TactileWindow()
    try:
        generation = window.data_generation
        window._data.ingest({FF: reading()}, generation, timestamp=10.)
        window._data.drain(now=10.6)
        window._data.drain(now=11.2)
        window._data.ingest({FF: reading()}, generation, timestamp=12.)
        _, _, moments, _ = window._data.drain(now=12.1)
        times = [sample[0] for sample in moments]
        assert times == sorted(times)
    finally:
        window.close()


@pytest.mark.parametrize("quantity,weak,maximum_span", [("force", .1, 1.), ("moment", .00002, .001)])
def test_weak_signals_use_tight_signed_ranges_without_changing_values(app, quantity, weak, maximum_span):
    plots = widgets.ForcePlots(quantity=quantity)
    try:
        history = [(10., {s: (weak, -weak, 0.) for s in TactileSensorId})]
        plots.set_history(history, now=10.1)
        low, high = plots.plots[FF].viewRange()[1]
        assert low < -weak and high > weak
        assert high - low < maximum_span
        np.testing.assert_allclose(plots.curves[FF][0].getData()[1], [weak])
    finally:
        plots.close()


def test_old_large_peaks_do_not_hide_current_weak_force_and_nan_is_ignored(app):
    plots = widgets.ForcePlots()
    try:
        history = [(1., {s: (20., 0., 0.) for s in TactileSensorId}),
                   (10., {s: (.1, -.1, float("nan")) for s in TactileSensorId})]
        plots.set_history(history, now=10.1)
        assert plots.plots[FF].viewRange()[1][1] < 1.
        plots.set_auto_scale(False)
        plots.set_history(history, now=10.1)
        np.testing.assert_allclose(plots.plots[FF].viewRange()[1], [-10., 25.])
    finally:
        plots.close()


def test_window_auto_scale_toggle_controls_both_plots_and_marker_range(app):
    window = TactileWindow()
    try:
        assert window.auto_scale_checkbox.isChecked()
        window.update_tactile({FF: reading()})
        window._refresh()
        assert window.finger_maps[FF].force_range < 25.
        assert "25 N" in window.force_scale_label.text()
        window.auto_scale_checkbox.setChecked(False)
        assert not window.force_plots.auto_scale
        assert not window.moment_plots.auto_scale
        assert window.finger_maps[FF].force_range == 25.
        window.auto_scale_checkbox.setChecked(True)
        assert window.force_plots.auto_scale and window.moment_plots.auto_scale
    finally:
        window.close()


def test_point_colors_get_darker_and_weak_points_are_larger():
    forces = [0., .1, .5, 1., 5., 25.]
    colors = [widgets._force_color(force) for force in forces]
    brightness = [sum(color.getRgb()[:3]) for color in colors]
    assert all(a > b for a, b in zip(brightness, brightness[1:]))
    idle = widgets._marker_radius(0., 1., .4, overview=False)
    weak = widgets._marker_radius(.1, 1., .4, overview=False)
    strong = widgets._marker_radius(1., 1., .4, overview=False)
    assert idle >= 2.
    assert idle < weak < strong
    assert strong <= 7.


def test_sub_half_newton_tangential_force_has_visible_direction_arrow(app):
    def render(force):
        image = QImage(80, 80, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        widgets._draw_marker(painter, QPointF(40, 40), force, .5,
                             overview=False, force_range=.2)
        painter.end()
        return image
    normal, tangential = render((0., 0., .1)), render((.1, 0., 0.))
    assert any(tangential.pixelColor(x, y).alpha() > normal.pixelColor(x, y).alpha()
               for x in range(49, 55) for y in range(38, 43))
