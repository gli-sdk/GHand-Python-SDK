"""Display-only despiking tests; no hardware connection."""
import copy
import importlib.util
import math
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
import pytest


def filter_history(history, **kwargs):
    assert importlib.util.find_spec('ghand.tactile_display.moment_filter'), 'display filter is missing'
    from ghand.tactile_display.moment_filter import despike_moment_history
    return despike_moment_history(history, **kwargs)


def samples(values, times=None):
    return tuple((t, {'finger': (v, -v, v)}) for t,v in zip(
        times if times is not None else np.arange(len(values))*.02, values))


def ys(history): return [v['finger'][0] for _,v in history]


def test_small_signed_impulses_removed_without_mutating_raw():
    for sign in (-1,1):
        raw=samples([0,sign*8e-6,0,0]);before=copy.deepcopy(raw)
        out=filter_history(raw,max_jump_nm=1e-5)
        np.testing.assert_allclose(ys(out),[0,0,0])
        assert raw==before
        assert out[-1][0]==raw[-2][0]  # actual old timestamp, not relabeled current


def test_large_impulses_steps_plateaus_and_ramps_survive():
    for values in ([0,.005,0,0],[0,8e-6,8e-6,8e-6],
                   [0,8e-6,8e-6,0,0],[0,2e-6,4e-6,6e-6]):
        np.testing.assert_allclose(ys(filter_history(samples(values))),values[:-1])


def test_zero_threshold_disables_and_nan_gaps_do_not_get_filled():
    raw=samples([0,8e-6,0])
    assert filter_history(raw,max_jump_nm=0)==raw
    out=filter_history(samples([0,8e-6,math.nan,0,0]))
    assert ys(out)[1]==8e-6 and math.isnan(ys(out)[2])
    out=filter_history(samples([0,8e-6,0,0],times=[0,.02,1.,1.02]))
    assert ys(out)[1]==8e-6
    assert math.isnan(ys(filter_history(samples([0,0,math.nan])))[-1])


def test_baseline_offset_returns_to_local_level_not_zero():
    out=filter_history(samples([.02,.020008,.02,.02]))
    np.testing.assert_allclose(ys(out),[.02]*3)
    assert filter_history(())==()
    assert filter_history(samples([.02]))==samples([.02])
    with pytest.raises(ValueError):filter_history(samples([0]),max_jump_nm=-1)


def test_window_toggle_changes_only_moment_curves_and_retains_raw_table():
    from unittest.mock import patch
    from PySide6.QtWidgets import QApplication
    from ghand.types import TactileData,TactileSensorId
    from ghand.tactile_display.window import TactileWindow
    app=QApplication.instance() or QApplication([])
    w=TactileWindow();f=TactileSensorId.FF
    try:
        assert hasattr(w,'moment_filter_checkbox'), 'filter controls are missing'
        assert w.moment_filter_checkbox.isChecked()
        for i,v in enumerate([0,8e-6,0,0]):
            reading=TactileData(state=True,error=0,raw_state=31,resultant_force=[v,0,0],
                distributed_force=[0,0,0]*31,resultant_moment=[v,0,0],moment_reference_point_m=[0,0,0])
            w._data.ingest({f:reading},w.data_generation,timestamp=10+i*.02)
        with patch('ghand.tactile_display.window.time.monotonic',return_value=10.08):
            w._refresh()
            np.testing.assert_allclose(w.moment_plots.curves[f][0].getData()[1],[0,0,0])
            np.testing.assert_allclose(w.force_plots.curves[f][0].getData()[1],[0,8e-6,0,0])
            assert w._data.drain(10.08)[2][1][1][f][0]==8e-6
            w.moment_filter_checkbox.setChecked(False)
            np.testing.assert_allclose(w.moment_plots.curves[f][0].getData()[1],[0,8e-6,0,0])
            w.moment_filter_checkbox.setChecked(True)
            w.moment_filter_limit.setValue(1.)  # µN m, smaller than impulse
            np.testing.assert_allclose(w.moment_plots.curves[f][0].getData()[1],[0,8e-6,0])
        assert 'raw' in w.moment_frame_label.text().lower()
    finally:w.close()
