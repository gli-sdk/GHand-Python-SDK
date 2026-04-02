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

LINK_NAMES = [
    'LF-MCP', 'LF-PIP', 'LF-DIP',
    'RF-MCP', 'RF-PIP', 'RF-DIP',
    'MF-MCP', 'MF-PIP', 'MF-DIP',
    'IF-Swing', 'IF-MCP', 'IF-PIP', 'IF-DIP',
    'TH-Rotation', 'TH-Swing', 'TH-MCP', 'TH-PIP', 'TH-DIP',
    'base_link',
]

ANGLE_MAP = {
    'TH': [13, 14, 15, 16, 17],
    'IF': [9, 10, 11, 12],
    'MF': [6, 7, 8],
    'RF': [3, 4, 5],
    'LF': [0, 1, 2],
}