from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List
import os

import numpy as np

from .collision_detector import PLANE_NORMAL, PLANE_ORIGIN, gen_adj_matrix, get_plane_from_normal
from .datatypes import JointData, Plane, STLData
from .read_data import load_capsule_from_json, load_stl_data, read_urdf_json
from .runtime_builder import build_joint_runtime


def _get_default_data_path() -> str:
    """
    获取碰撞检测数据的默认路径

    Returns:
        str: 碰撞检测数据目录的绝对路径
    """
    try:
        # 优先使用 importlib.resources
        try:
            # Python 3.9+
            import importlib.resources as resources
        except ImportError:
            # Python 3.8
            import importlib_resources as resources

        # 获取 xiaoyao.data.collision 路径
        collision_path = resources.files('xiaoyao.data') / 'collision'
        return str(collision_path)
    except Exception:
        # 回退：使用相对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # xiaoyao/collision/core/ -> xiaoyao/data/collision/
        return os.path.abspath(os.path.join(current_dir, '../../data/collision'))


@dataclass
class CollisionRuntime:
    joint_data: List[Dict[str, Any]]
    capsule_map: Dict[str, Dict[str, Any]]
    joints_template: Dict[str, JointData]
    finger_funs: Dict[str, List[Callable]]
    stl_data: Dict[str, STLData]
    plane: Plane
    adj_matrix: np.ndarray


def load_collision_runtime(
    urdf_json_path: str | None = None,
    stl_dir: str | None = None,
    capsule_json_path: str | None = None,
    plane_normal: np.ndarray | None = None,
    plane_origin: np.ndarray | None = None,
) -> CollisionRuntime:
    # 获取默认数据路径
    data_path = _get_default_data_path()

    # 如果未指定路径，使用默认值
    if urdf_json_path is None:
        urdf_json_path = os.path.join(data_path, 'G5-13A-A6.json')
    if stl_dir is None:
        stl_dir = os.path.join(data_path, 'meshes')
    if capsule_json_path is None:
        capsule_json_path = os.path.join(data_path, 'capsule_parameters.json')

    joint_data = read_urdf_json(urdf_json_path)
    stl_data = load_stl_data(stl_dir)
    capsule_map = load_capsule_from_json(capsule_json_path)
    joints_template, finger_funs = build_joint_runtime(joint_data, capsule_map)
    plane = get_plane_from_normal(
        stl_data['base_link'],
        PLANE_NORMAL if plane_normal is None else plane_normal,
        PLANE_ORIGIN if plane_origin is None else plane_origin,
    )
    adj_matrix = gen_adj_matrix()
    return CollisionRuntime(
        joint_data=joint_data,
        capsule_map=capsule_map,
        joints_template=joints_template,
        finger_funs=finger_funs,
        stl_data=stl_data,
        plane=plane,
        adj_matrix=adj_matrix,
    )
