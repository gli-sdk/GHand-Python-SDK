"""
Collision SDK - 碰撞检测核心接口

适配自 E:\collision-collisions-detection\src\sdk.py
修改导入路径以适配 xiaoyao.collision.core 模块结构
"""

from __future__ import annotations
import copy
import math
from dataclasses import dataclass
import numpy as np
from xiaoyao.collision.core import angle_mapping as ang_mp
from xiaoyao.collision.core import collision_detector as col_detect
from xiaoyao.collision.core import passive_dip_mapping as dip_mp
from xiaoyao.collision.core import pose_evaluator as pose_eval
from xiaoyao.collision.core.datatypes import ANGLE_MAP
from xiaoyao.collision.core.runtime_loader import CollisionRuntime, load_collision_runtime


@dataclass
class CollisionCheckResult:
    """碰撞检测结果"""
    has_collision: bool
    safe_angles: np.ndarray | None
    collision_pairs: list | None


class CollisionSDK:
    """碰撞检测SDK主类"""

    def __init__(self, runtime: CollisionRuntime | None = None):
        self.runtime = runtime if runtime is not None else load_collision_runtime()
        self.joints_info = self.runtime.joints_template
        self.finger_funs = self.runtime.finger_funs
        self.stl_data = self.runtime.stl_data
        self.plane = self.runtime.plane
        self.adj_matrix = self.runtime.adj_matrix

    def collision_check(self, target_angles: np.ndarray, safety_margin: float) -> CollisionCheckResult:

        validated_safety_margin = self._validate_safety_margin(safety_margin) * 2.0  # max safety distance is 2 mm
        internal_angles = np.asarray(
            ang_mp.external_to_internal_angles(target_angles),
            dtype=float,
        )
        full_angles = np.asarray(
            dip_mp.apply_passive_dip_mapping(internal_angles),
            dtype=float,
        )

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
            return CollisionCheckResult(False, None, None)

        safe_angles, _ = col_detect.binary_search_collision(
            start_angles=np.zeros_like(internal_angles, dtype=float),
            target_angles=internal_angles,
            joints_info=joints_info,
            stl_data=stl_data,
            plane=self.plane,
            adj_matrix=self.adj_matrix,
            angle_map=ANGLE_MAP,
            finger_funs=self.finger_funs,
            safety_margin=validated_safety_margin,
        )
        external_angles = np.asarray(
            ang_mp.internal_to_external_angles(safe_angles),
            dtype=float,
        )
        return CollisionCheckResult(True, external_angles, collision_pairs)

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
    CollisionSDK()


if __name__ == '__main__':
    main()
