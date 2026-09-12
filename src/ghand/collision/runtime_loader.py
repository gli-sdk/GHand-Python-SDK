# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

import numpy as np

from .collision_detector import PLANE_NORMAL, PLANE_ORIGIN, gen_adj_matrix, get_plane_from_normal
from .datatypes import JointData, Plane, STLData
from .read_data import load_capsule_from_json, load_stl_data, read_urdf_xml
from .runtime_builder import build_joint_runtime


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
    urdf_path: str | None = None,
    stl_dir: str | None = None,
    capsule_json_path: str | None = None,
    plane_normal: np.ndarray | None = None,
    plane_origin: np.ndarray | None = None,
) -> CollisionRuntime:
    joint_data = read_urdf_xml(urdf_path)
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
