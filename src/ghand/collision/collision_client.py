# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
from . import angle_mapping as ang_mp
from . import collision_detector as col_detect
from . import passive_dip_mapping as dip_mp
from . import pose_evaluator as pose_eval
from .datatypes import ANGLE_MAP
from .runtime_loader import CollisionRuntime, load_collision_runtime


@dataclass
class CollisionCheckResult:
    has_collision: bool
    safe_angles: np.ndarray | None
    collision_pairs: list | None
    warnings: list[str]


class CollisionClient:
    def __init__(self, runtime: CollisionRuntime | None = None):
        self.runtime = runtime if runtime is not None else load_collision_runtime()
        self.joints_info = self.runtime.joints_template
        self.finger_funs = self.runtime.finger_funs
        self.stl_data = self.runtime.stl_data
        self.plane = self.runtime.plane
        self.adj_matrix = self.runtime.adj_matrix

    def collision_check(self, target_angles: np.ndarray, safety_margin: float = 0.0) -> CollisionCheckResult:
        validated_safety_margin = self._validate_safety_margin(safety_margin) * 2/1000 #max safety distance is 2 mm
        clamped_angles = np.asarray(
            ang_mp.sdk_degrees_to_internal_radians(target_angles),
            dtype=float,
        )
        input_warnings = ang_mp.angle_warnings()
        full_angles = np.asarray(
            dip_mp.apply_passive_dip_mapping(clamped_angles),
            dtype=float,
        )

        has_collision, safe_angles, collision_pairs = self._evaluate_collision(
            full_angles,
            validated_safety_margin,
        )
        if not has_collision:
            return CollisionCheckResult(False, None, None, input_warnings)

        safe_angles_deg = np.asarray(
            ang_mp.internal_radians_to_sdk_degrees(safe_angles),
            dtype=float,
        )
        return CollisionCheckResult(True, safe_angles_deg, collision_pairs, input_warnings)

    def _evaluate_collision(
        self,
        full_angles: np.ndarray,
        validated_safety_margin: float,
    ) -> tuple[bool, np.ndarray, list]:
        joints_info, stl_data, has_collision, collision_pairs = pose_eval.evaluate_pose(
            angles=full_angles,
            joints_info=self.joints_info,
            finger_funs=self.finger_funs,
            stl_data=self.stl_data,
            plane=self.plane,
            adj_matrix=self.adj_matrix,
            angle_map=ANGLE_MAP,
            safety_margin=validated_safety_margin,
        )
        if not has_collision:
            return False, full_angles, []

        safe_angles, _ = col_detect.binary_search_collision(
            start_angles=dip_mp.apply_passive_dip_mapping(ang_mp.neutral_internal_radians()),
            target_angles=full_angles,
            joints_info=joints_info,
            stl_data=stl_data,
            plane=self.plane,
            adj_matrix=self.adj_matrix,
            angle_map=ANGLE_MAP,
            finger_funs=self.finger_funs,
            safety_margin=validated_safety_margin,
        )
        return True, safe_angles, collision_pairs

    def _validate_safety_margin(self, safety_margin: float) -> float:
        if not isinstance(safety_margin, (float, int)):
            raise TypeError(
                f'the datatype of safety margin must be float or int, got {type(safety_margin).__name__}'
            )
        validated = float(safety_margin)
        if not math.isfinite(validated):
            raise ValueError(f'the value of safety margin must be finite, got {validated!r}')
        if validated < 0.0 or validated > 1.0:
            raise ValueError('the value of safety margin must be within the range [0.0, 1.0]')
        return validated

    


def main() -> None:
    CollisionClient()


if __name__ == '__main__':
    main()
