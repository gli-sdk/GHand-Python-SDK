# SPDX-FileCopyrightText: 2026 GLITech
# SPDX-License-Identifier: Apache-2.0
"""Computed per-finger CAD wrenches from taxel-local forces in Newtons.

Vendor R maps CAD -> taxel local (column vectors). Thus F_CAD = R.T @ F_local.
These are tactile resultants, not measured motor torques or robot-world wrenches.
"""
from dataclasses import replace
from importlib.resources import files
import json
from typing import Mapping, Sequence

import numpy as np

from .types import TactileData, TactileSensorId


class TactileMomentCalculator:
    """Immutable calculation settings, shared safely by polling and callbacks.

    Default geometry is the supplied GHand5 PX sensor CAD data. A custom geometry
    mapping must use the same keys, point order, mm and CAD-to-local convention.
    The reference point is in meters in each sensor's own CAD coordinate frame.
    """

    def __init__(self, *, geometry: Mapping | None = None,
                 reference_point_m: Sequence[float] = (0., 0., 0.)) -> None:
        if geometry is None:
            geometry = json.loads(files("ghand").joinpath("config/ghand5_tactile_geometry.json").read_text(encoding="utf-8"))
        if geometry.get("position_unit") != "mm" or geometry.get("rotation_convention") != "cad_to_taxel_local_column_vector":
            raise ValueError("Geometry must use mm and CAD-to-taxel-local column-vector rotations")
        reference = np.array(reference_point_m, dtype=float, copy=True)
        if reference.shape != (3,) or not np.isfinite(reference).all():
            raise ValueError("reference_point_m must contain three finite values in meters")
        reference.flags.writeable = False
        self._reference = reference
        self._geometry: dict[TactileSensorId, tuple[np.ndarray, np.ndarray]] = {}
        for sensor, model_name in geometry["sensor_models"].items():
            model = geometry["models"][model_name]
            positions = np.array(model["positions_mm"], dtype=float, copy=True) * .001
            rotations = np.array(model["rotations_cad_to_local"], dtype=float, copy=True)
            count = len(positions)
            if (count == 0 or positions.shape != (count, 3) or rotations.shape != (count, 3, 3)
                    or model["point_ids"] != list(range(1, count + 1))
                    or not np.isfinite(positions).all() or not np.isfinite(rotations).all()
                    or not np.allclose(rotations @ rotations.transpose(0, 2, 1), np.eye(3), atol=2e-5, rtol=0)
                    or not np.allclose(np.linalg.det(rotations), 1, atol=2e-5, rtol=0)):
                raise ValueError(f"Invalid positions, IDs or rotation matrices for {sensor}")
            positions.flags.writeable = rotations.flags.writeable = False
            self._geometry[TactileSensorId[sensor]] = positions, rotations

    def enrich(self, tactile: Mapping[TactileSensorId, TactileData]) -> dict[TactileSensorId, TactileData]:
        """Return new readings; unknown/error/missing data has None derived fields.

        Requires explicit healthy status (state=True and error=0). A transport
        that does not report a tactile error byte cannot establish this here.
        Original force/status fields and communication-cache objects are intact.
        """
        return {sensor: self._calculate(sensor, info) for sensor, info in tactile.items()}

    def _calculate(self, sensor: TactileSensorId, info: TactileData) -> TactileData:
        result = replace(info, distributed_force_sensor_frame=None, resultant_force_sensor_frame=None,
                         resultant_moment=None, moment_reference_point_m=None)
        geometry = self._geometry.get(sensor)
        if geometry is None or not info.state or info.error != 0:
            return result
        positions, rotations = geometry
        try:
            force = np.asarray(info.distributed_force, dtype=float)
        except (TypeError, ValueError, OverflowError):
            return result
        if force.shape != (len(positions) * 3,) or not np.isfinite(force).all():
            return result
        # Each R_i is CAD -> local, so transpose it to undo that transform.
        with np.errstate(over="ignore", invalid="ignore"):
            cad_force = np.einsum("nji,nj->ni", rotations, force.reshape(-1, 3))
            resultant = cad_force.sum(axis=0)
            moment = np.cross(positions - self._reference, cad_force).sum(axis=0)
        if not np.isfinite(cad_force).all() or not np.isfinite(resultant).all() or not np.isfinite(moment).all():
            return result
        result.distributed_force_sensor_frame = cad_force.ravel().tolist()
        result.resultant_force_sensor_frame = resultant.tolist()
        result.resultant_moment = moment.tolist()
        result.moment_reference_point_m = self._reference.tolist()
        return result
