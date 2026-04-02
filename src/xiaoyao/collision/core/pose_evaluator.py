from typing import Callable, Dict, List, Tuple

import numpy as np

from .datatypes import JointData, Plane, STLData
from .transforms import cal_capsule_param, cal_stl_trans, update_joint_transforms
from .collision_detector import is_pose_collision


def evaluate_pose(
    angles: np.ndarray,
    joints_info: Dict[str, JointData],
    finger_funs: Dict[str, List[Callable[[float], np.ndarray]]],
    stl_data: Dict[str, STLData],
    plane: Plane,
    adj_matrix: np.ndarray,
    angle_map: Dict[str, List[int]],
    safety_margin: float,
    transform_stl: bool = False,
) -> Tuple[Dict[str, JointData], Dict[str, STLData], bool, List[str]]:
    joints_info = update_joint_transforms(joints_info, angles, angle_map, finger_funs)
    joints_info = cal_capsule_param(joints_info)
    if transform_stl:
        stl_data = cal_stl_trans(joints_info, stl_data)
    has_collision, collision_links = is_pose_collision(
        joints_info,
        plane,
        adj_matrix,
        safety_margin,
    )
    return joints_info, stl_data, has_collision, list(collision_links)
