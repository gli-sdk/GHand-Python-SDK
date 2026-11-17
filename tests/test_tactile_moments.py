"""Numerical and SDK snapshot tests. Never open a physical device."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from ghand import CommType, GHand, ProductType
from ghand.types import DeviceData, HandData, TactileData, TactileSensorId
import ghand.tactile_moments as moments


FF = TactileSensorId.FF


def geometry():
    # R rotates CAD -> local by +90 degrees about z. Local +x is CAD -y.
    return {
        "rotation_convention": "cad_to_taxel_local_column_vector",
        "position_unit": "mm",
        "sensor_models": {"FF": "test"},
        "models": {"test": {
            "point_ids": [1, 2],
            "positions_mm": [[1000, 0, 0], [0, 0, 1000]],
            "rotations_cad_to_local": [[[0, -1, 0], [1, 0, 0], [0, 0, 1]]] * 2,
        }},
    }


def reading(**kwargs):
    return TactileData(state=True, raw_state=31, error=0,
                       distributed_force=kwargs.pop("distributed_force", [1, 0, 0, 1, 0, 0]),
                       resultant_force=[9, 8, 7], **kwargs)


def test_inverse_rotation_cross_product_units_and_immutable_input():
    calc = moments.TactileMomentCalculator(geometry=geometry())
    raw = reading()
    result = calc.enrich({FF: raw})[FF]
    np.testing.assert_allclose(result.distributed_force_sensor_frame, [0, -1, 0] * 2)
    np.testing.assert_allclose(result.resultant_force_sensor_frame, [0, -2, 0])
    np.testing.assert_allclose(result.resultant_moment, [1, 0, -1])
    assert result.moment_reference_point_m == [0, 0, 0]
    assert result.resultant_force == [9, 8, 7]
    assert result.distributed_force == raw.distributed_force
    assert result is not raw
    assert raw.resultant_moment is None


def test_reference_shift():
    calc = moments.TactileMomentCalculator(geometry=geometry(), reference_point_m=(0, 0, 1))
    result = calc.enrich({FF: reading()})[FF]
    np.testing.assert_allclose(result.resultant_moment, [-1, 0, -1])
    assert result.moment_reference_point_m == [0, 0, 1]


@pytest.mark.parametrize("changes", [
    {"state": False}, {"error": 1}, {"error": None},
    {"distributed_force": None}, {"distributed_force": [1, 2, 3]},
    {"distributed_force": [float("nan")] * 6},
    {"distributed_force": [float("inf")] * 6},
])
def test_invalid_data_clears_derived_values(changes):
    calc = moments.TactileMomentCalculator(geometry=geometry())
    raw = replace(calc.enrich({FF: reading()})[FF], **changes)
    result = calc.enrich({FF: raw})[FF]
    assert result.resultant_moment is None
    assert result.resultant_force_sensor_frame is None
    assert result.distributed_force_sensor_frame is None
    assert result.moment_reference_point_m is None


def test_unknown_sensor_does_not_borrow_another_geometry():
    calc = moments.TactileMomentCalculator(geometry=geometry())
    assert calc.enrich({TactileSensorId.THUMB: reading()})[TactileSensorId.THUMB].resultant_moment is None


@pytest.mark.parametrize("reference", [(1, 2), (float("nan"), 0, 0), (0, 0, float("inf"))])
def test_invalid_reference_is_rejected(reference):
    with pytest.raises(ValueError):
        moments.TactileMomentCalculator(geometry=geometry(), reference_point_m=reference)


def test_invalid_geometry_is_rejected():
    data = geometry()
    data["models"]["test"]["rotations_cad_to_local"][0] = np.zeros((3, 3)).tolist()
    with pytest.raises(ValueError):
        moments.TactileMomentCalculator(geometry=data)


def test_packaged_geometry_has_all_points_and_vendor_hashes():
    calc = moments.TactileMomentCalculator()
    for finger in TactileSensorId:
        count = 38 if finger == TactileSensorId.THUMB else 31
        sample = reading(distributed_force=[0, 0, 0] * count)
        result = calc.enrich({finger: sample})[finger]
        assert len(result.distributed_force_sensor_frame) == count * 3
        assert result.resultant_moment == [0, 0, 0]
    path = Path(moments.__file__).with_name("config") / "ghand5_tactile_geometry.json"
    document = json.loads(path.read_text())
    assert document["sensor_models"]["THUMB"] != document["sensor_models"]["FF"]
    for model in document["models"].values():
        assert len(model["point_ids"]) == len(model["positions_mm"])
        for name, digest in model["source_sha256"].items():
            source = Path("/home/a/下载/px") / name
            if source.exists():
                assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


def test_polling_and_subscription_enrich_copies_consistently():
    raw = {FF: reading(distributed_force=[0, 0, 1] * 31)}
    frame = DeviceData(HandData(), [], raw, timestamp=123.0)
    callbacks = []
    comm = SimpleNamespace(
        is_connected=lambda: True,
        get_tactile_data=lambda: raw,
        subscribe_device_data=lambda callback, **kw: callbacks.append(callback) or 7,
        close=lambda: None,
    )
    with patch.object(GHand, "_create_comm", return_value=comm):
        hand = GHand(ProductType.GHand5, CommType.ETHERCAT)
    hand._tactile_opened = True
    received = []
    assert hand.subscribe(received.append, interval_ms=20) == 7
    callbacks[0](frame)
    polled = hand.get_tactile_data()
    assert polled[FF].resultant_moment == received[0].tactile[FF].resultant_moment
    assert raw[FF].resultant_moment is None
    assert received[0] is not frame
    assert received[0].timestamp == 123.0
    hand.configure_tactile_moments(reference_point_m=(0, 0, .01))
    shifted = hand.get_tactile_data()[FF]
    np.testing.assert_allclose(shifted.resultant_moment,
        np.array(polled[FF].resultant_moment) - np.cross([0, 0, .01], polled[FF].resultant_force_sensor_frame))
    callbacks[0](replace(frame, tactile=None))
    assert received[-1].tactile is None


def test_lite_product_does_not_apply_ghand5_geometry():
    with patch.object(GHand, "_create_comm", return_value=SimpleNamespace(close=lambda: None)):
        hand = GHand(ProductType.GHandLite1, CommType.ETHERCAT)
    with pytest.raises(ValueError, match="GHand5"):
        hand.configure_tactile_moments()
