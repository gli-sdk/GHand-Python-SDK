# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

import numpy as np
from dataclasses import dataclass
from typing import Any


@dataclass
class JointData:
    origin: np.ndarray = None
    rpy: np.ndarray = None
    axis: np.ndarray = None
    joint_fun: callable = None
    trans_matrix: np.ndarray = None
    capsule_xyz: np.ndarray = None
    r: float = None
    k: float = None
    theta_prime: float = None
    p1: np.ndarray = None
    p2: np.ndarray = None
    figure_handle: Any = None


@dataclass
class STLData:
    """STL data class"""

    raw_data: Any = None
    V_homo: np.ndarray = None


@dataclass
class Plane:
    n: np.ndarray
    p0: np.ndarray
    d: float
    aabb_min: np.ndarray = None
    aabb_max: np.ndarray = None
    aabb_vertices: np.ndarray = None

JOINT_NAMES = [
    'LF_MCP', 'LF_PIP', 'LF_DIP',
    'RF_MCP', 'RF_PIP', 'RF_DIP',
    'MF_MCP', 'MF_PIP', 'MF_DIP',
    'FF_MCP_AA', 'FF_MCP', 'FF_PIP', 'FF_DIP',
    'Thumb_TMC_PS', 'Thumb_TMC_AA', 'Thumb_TMC_FE', 'Thumb_MCP', 'Thumb_IP',
]

LINK_NAMES = [
    'base_link',
    'LF_MCP_link', 'LF_PIP_link', 'LF_DIP_link',
    'RF_MCP_link', 'RF_PIP_link', 'RF_DIP_link',
    'MF_MCP_link', 'MF_PIP_link', 'MF_DIP_link',
    'FF_MCP_AA_link', 'FF_MCP_link', 'FF_PIP_link', 'FF_DIP_link',
    'Thumb_TMC_PS_link', 'Thumb_TMC_AA_link', 'Thumb_TMC_FE_link',
    'Thumb_MCP_link', 'Thumb_IP_link',
]

ANGLE_MAP = {
    'little': [0, 1, 2],
    'ring': [3, 4, 5],
    'middle': [6, 7, 8],
    'index': [9, 10, 11, 12],
    'thumb': [13, 14, 15, 16, 17],
}
