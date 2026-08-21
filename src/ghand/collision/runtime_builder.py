# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

import functools
from typing import Any, Callable, Dict, List, Tuple

import numpy as np

from .datatypes import JointData, JOINT_NAMES
from .transforms import FINGER_JOINT_MAP, build_joint_transform


def build_joint_runtime(
    joint_data: List[Dict[str, Any]],
    capsule_map: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, JointData], Dict[str, List[Callable[[float], np.ndarray]]]]:
    
    joints_info: Dict[str, JointData] = {
        'base_link': JointData(trans_matrix=np.eye(4)),
    }
    joint_funs: Dict[str, Callable[[float], np.ndarray]] = {}
    joint_map = {str(joint['name']): joint for joint in joint_data if 'name' in joint}

    for joint_name in JOINT_NAMES:
        joint = joint_map.get(joint_name)
        if joint is None:
            print(f'{joint_name} not found, please chech joint data')
            continue
        link_name = str(joint.get('child', f'{joint_name}_link'))

        joint_info = JointData()
        joint_info.origin = np.asarray(joint['origin'], dtype=float)
        joint_info.rpy = np.asarray(joint['rpy'], dtype=float)
        joint_info.axis = np.asarray(joint['axis'], dtype=float)
        joint_info.joint_fun = functools.partial(
            build_joint_transform,
            joint_info.origin,
            joint_info.rpy,
            joint_info.axis,
        )

        if link_name in capsule_map:
            capsule = capsule_map[link_name]
            joint_info.capsule_xyz = np.asarray(capsule['xyz'], dtype=float)
            joint_info.r = float(capsule['radius'])
            joint_info.k = float(capsule['k'])
            joint_info.theta_prime = float(capsule['theta_prime'])

        joints_info[link_name] = joint_info
        joint_funs[link_name] = joint_info.joint_fun

    finger_funs: Dict[str, List[Callable[[float], np.ndarray]]] = {}
    for finger_name, link_names in FINGER_JOINT_MAP.items():
        finger_funs[finger_name] = [
            joint_funs[link_name]
            for link_name in link_names
            if link_name in joint_funs
        ]

    return joints_info, finger_funs
