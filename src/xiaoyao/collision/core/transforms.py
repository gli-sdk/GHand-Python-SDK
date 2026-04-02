from typing import Callable, Dict, List

import numpy as np

from .datatypes import JointData, STLData

FINGER_JOINT_MAP = {
    'LF': ['MCP', 'PIP', 'DIP'],
    'RF': ['MCP', 'PIP', 'DIP'],
    'MF': ['MCP', 'PIP', 'DIP'],
    'IF': ['Swing', 'MCP', 'PIP', 'DIP'],
    'TH': ['Rotation', 'Swing', 'MCP', 'PIP', 'DIP'],
}

CAPSULE_LINK_NAMES = [
    'LF-MCP', 'LF-PIP', 'LF-DIP',
    'RF-MCP', 'RF-PIP', 'RF-DIP',
    'MF-MCP', 'MF-PIP', 'MF-DIP',
    'IF-MCP', 'IF-PIP', 'IF-DIP',
    'TH-MCP', 'TH-PIP', 'TH-DIP',
]

STL_TRANSFORM_LINK_NAMES = [
    'LF-MCP', 'LF-PIP', 'LF-DIP',
    'RF-MCP', 'RF-PIP', 'RF-DIP',
    'MF-MCP', 'MF-PIP', 'MF-DIP',
    'IF-Swing', 'IF-MCP', 'IF-PIP', 'IF-DIP',
    'TH-Rotation', 'TH-Swing', 'TH-MCP', 'TH-PIP', 'TH-DIP',
    'base_link',
]


def _translation_matrix(xyz: np.ndarray) -> np.ndarray:
    """Return a 4x4 translation matrix."""
    transform = np.eye(4)
    transform[:3, 3] = np.asarray(xyz, dtype=float).reshape(3)
    return transform


def _rotation_x(angle: float) -> np.ndarray:
    """Return a 4x4 rotation matrix around the X axis."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([
        [1, 0, 0, 0],
        [0, c, -s, 0],
        [0, s, c, 0],
        [0, 0, 0, 1],
    ])


def _rotation_y(angle: float) -> np.ndarray:
    """Return a 4x4 rotation matrix around the Y axis."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([
        [c, 0, s, 0],
        [0, 1, 0, 0],
        [-s, 0, c, 0],
        [0, 0, 0, 1],
    ])


def _rotation_z(angle: float) -> np.ndarray:
    """Return a 4x4 rotation matrix around the Z axis."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([
        [c, -s, 0, 0],
        [s, c, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ])


def _to_homogeneous_points(points: np.ndarray) -> np.ndarray:
    """Convert an Nx3 point array into a 4xN homogeneous-coordinate matrix."""
    points = np.asarray(points, dtype=float).reshape(-1, 3)
    return np.hstack([points, np.ones((points.shape[0], 1))]).T


def _capsule_local_points(data: JointData) -> np.ndarray:
    """Return the two capsule endpoints in local homogeneous coordinates."""
    x0, y0, z0 = data.capsule_xyz
    local_start = np.array([x0, y0, z0, 1.0])
    local_end = np.array([
        x0 + data.k * np.cos(data.theta_prime),
        y0 + data.k * np.sin(data.theta_prime),
        z0,
        1.0,
    ])
    return np.column_stack([local_start, local_end])


def build_joint_transform(xyz: np.ndarray, rpy: np.ndarray, joint_axis: np.ndarray, theta: float) -> np.ndarray:
    """
    Build the 4x4 homogeneous transform for a joint.

    Args:
        xyz: Joint translation vector with shape `(3,)`.
        rpy: Fixed joint roll, pitch, and yaw with shape `(3,)`.
        joint_axis: Joint rotation axis with shape `(3,)`.
        theta: Current joint angle.

    Returns:
        A 4x4 homogeneous transform matrix.
    """
    xyz = np.asarray(xyz, dtype=float).reshape(3)
    rpy = np.asarray(rpy, dtype=float).reshape(3)
    joint_axis = np.asarray(joint_axis, dtype=float).reshape(3)

    r, p, y = rpy
    fixed_transform = _translation_matrix(xyz) @ _rotation_z(y) @ _rotation_y(p) @ _rotation_x(r)

    # The current hand model uses the local Z axis for revolute joints,
    # and joint_axis[2] is used only to encode the rotation direction.
    joint_rotation = _rotation_z(theta * joint_axis[2])
    return fixed_transform @ joint_rotation


def update_joint_transforms(
    joints_info: Dict[str, JointData],
    theta: np.ndarray,
    angles_map: Dict[str, List[int]],
    finger_funs: Dict[str, List[Callable]],
) -> Dict[str, JointData]:
    """
    Update each joint transform from the full-hand angle vector.

    Args:
        joints_info: Runtime joint data keyed by joint name.
        theta: Full joint-angle array.
        angles_map: Per-finger index mapping into `theta`.
        finger_funs: Per-finger joint transform functions.

    Returns:
        The updated `joints_info` dictionary.
    """
    theta = np.asarray(theta, dtype=float)

    for finger_name, fun_list in finger_funs.items():
        if finger_name not in angles_map:
            raise KeyError(f'angles_map is missing angle indices for finger {finger_name}')
        if finger_name not in FINGER_JOINT_MAP:
            raise KeyError(f'FINGER_JOINT_MAP is missing joint names for finger {finger_name}')

        angle_indices = np.asarray(angles_map[finger_name], dtype=int)
        invalid_mask = (angle_indices < 0) | (angle_indices >= len(theta))
        if np.any(invalid_mask):
            invalid_index = int(angle_indices[invalid_mask][0])
            raise ValueError(
                f'{finger_name} angle index {invalid_index} is out of range for theta with length {len(theta)}'
            )

        theta_list = theta[angle_indices]
        joint_names = FINGER_JOINT_MAP[finger_name]

        if len(theta_list) != len(fun_list):
            raise ValueError(
                f'{finger_name} angle count ({len(theta_list)}) does not match function count ({len(fun_list)})'
            )
        if len(joint_names) != len(fun_list):
            raise ValueError(
                f'{finger_name} joint-name count ({len(joint_names)}) does not match function count ({len(fun_list)})'
            )

        cumulative_transform = np.eye(4)
        for joint_suffix, joint_fun, joint_theta in zip(joint_names, fun_list, theta_list):
            cumulative_transform = cumulative_transform @ joint_fun(joint_theta)
            joints_info[f'{finger_name}-{joint_suffix}'].trans_matrix = cumulative_transform

    return joints_info


def cal_capsule_param(joints_info: Dict[str, JointData]) -> Dict[str, JointData]:
    """
    Update capsule endpoints in world coordinates for each supported link.

    Args:
        joints_info: Runtime joint data keyed by joint name.

    Returns:
        The updated `joints_info` dictionary.
    """
    for link_name in CAPSULE_LINK_NAMES:
        data = joints_info[link_name]
        capsule_points = _capsule_local_points(data)
        transformed_points = data.trans_matrix @ capsule_points
        data.p1 = transformed_points[:3, 0]
        data.p2 = transformed_points[:3, 1]

    return joints_info


def cal_stl_trans(joints_info: Dict[str, JointData], stl_data: Dict[str, STLData]) -> Dict[str, STLData]:
    """
    Update STL vertices in homogeneous world coordinates for each supported link.

    Args:
        joints_info: Runtime joint data keyed by joint name.
        stl_data: STL runtime data keyed by link name.

    Returns:
        The updated `stl_data` dictionary.
    """
    for link_name in STL_TRANSFORM_LINK_NAMES:
        if link_name not in joints_info or link_name not in stl_data:
            continue

        stl_item = stl_data[link_name]
        points = stl_item.raw_data.points.reshape(-1, 3)
        vertices_homo = _to_homogeneous_points(points)
        stl_item.V_homo = joints_info[link_name].trans_matrix @ vertices_homo

    return stl_data
