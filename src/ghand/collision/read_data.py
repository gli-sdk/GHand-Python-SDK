# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from stl import mesh

from . import collision_config, datatypes
from .datatypes import STLData


def _get_assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def _get_default_urdf_path() -> Path:
    """返回 ghand-assets 中的默认 URDF 路径。"""
    return _get_assets_dir() / "ghand5_system" / "urdf" / "ghand5_right.urdf"


def _get_default_stl_dir() -> Path:
    """返回 ghand-assets 中的默认 meshes 目录。"""
    return _get_assets_dir() / "ghand5_system" / "meshes" / "hands" / "visual" / "right"


DEFAULT_URDF_PATH: Path = _get_default_urdf_path()
DEFAULT_STL_DIR: Path = _get_default_stl_dir()
# Filesystem defaults used only when an explicit path is provided.
#
# When no path is passed to read_urdf_xml() or load_capsule_from_json(),
# the values from collision_config.py are used instead of reading the disk.


def _to_float(value: Any, default: float = 0.0) -> float:
    return float(value) if value is not None else default


def _read_csv_with_fallback_encodings(csv_path: str | Path, label: str) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f'{label} not found: {path.resolve()}')

    for encoding in ('utf-8', 'gbk', 'gb2312'):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError('csv', b'', 0, 1, f'Unable to decode CSV: {path}')


def _extract_numeric_array(
    dataframe: pd.DataFrame,
    *,
    drop_columns: Optional[List[str]] = None,
) -> np.ndarray:
    working_dataframe = dataframe.drop(columns=drop_columns) if drop_columns else dataframe
    return working_dataframe.select_dtypes(include=[np.number]).to_numpy(dtype=float, copy=True)


def _normalize_capsule_params(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'xyz': np.array(params['xyz'], dtype=float),
        'radius': _to_float(params.get('radius')),
        'k': _to_float(params.get('k')),
        'theta_prime': _to_float(params.get('theta_prime')),
    }


def get_finger_joints(joint_data: List[Dict[str, Any]], finger_name: str) -> List[Dict[str, Any]]:
    valid_fingers = ['LF', 'RF', 'MF', 'FF', 'Thumb']
    if finger_name not in valid_fingers:
        raise ValueError(f'finger_name must be one of: {", ".join(valid_fingers)}')

    return [joint for joint in joint_data if joint['name'].startswith(f'{finger_name}_')]


def get_all_joint_names(joint_data: List[Dict[str, Any]]) -> List[str]:
    return [joint['name'] for joint in joint_data]


def find_joint_by_name(joint_data: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for joint in joint_data:
        if joint['name'] == name:
            return joint
    return None


def load_trajectory_angles(csv_path: str = 'Trajectory_Collision_Angles.csv') -> np.ndarray:
    dataframe = _read_csv_with_fallback_encodings(csv_path, 'trajectory CSV')
    return _extract_numeric_array(dataframe)


def load_static_collision_data(
    csv_path: str = 'Static_Collision_Angles.csv',
) -> Tuple[np.ndarray, List[str]]:
    dataframe = _read_csv_with_fallback_encodings(csv_path, 'static collision CSV')
    collision_pairs = dataframe['Collision-pair'].astype(str).tolist()
    drop_columns = ['Collision-pair']
    if 'SAFETY_MARGIN' in dataframe.columns:
        drop_columns.append('SAFETY_MARGIN')
    angles_array = _extract_numeric_array(dataframe, drop_columns=drop_columns)
    return angles_array, collision_pairs


def load_safe_angles(csv_path: str = 'Safe_Angles.csv') -> np.ndarray:
    dataframe = _read_csv_with_fallback_encodings(csv_path, 'safe angles CSV')
    return _extract_numeric_array(dataframe)


def read_urdf_xml(xml_path: Optional[str] = None) -> List[Dict[str, Any]]:
    if xml_path is None:
        # default_path = _get_default_urdf_path()
        # if default_path.exists():
        #     root = ET.parse(str(default_path)).getroot()
        # else:
        root = ET.fromstring(collision_config.DEFAULT_URDF_XML)
    else:
        path = Path(xml_path)
        if not path.exists():
            raise FileNotFoundError(f'URDF XML not found: {path}')
        root = ET.parse(str(path)).getroot()

    joints: List[Dict[str, Any]] = []
    for joint in root.findall('joint'):
        name = joint.get('name', '').strip()
        if not name:
            continue

        origin = joint.find('origin')
        parent = joint.find('parent')
        child = joint.find('child')
        axis = joint.find('axis')
        limit = joint.find('limit')

        def _parse_xyz(attr: Optional[str]) -> np.ndarray:
            if attr is None:
                return np.array([0.0, 0.0, 0.0], dtype=float)
            parts = attr.strip().split()
            return np.array([float(parts[0]), float(parts[1]), float(parts[2])], dtype=float) if len(parts) >= 3 else np.array([0.0, 0.0, 0.0], dtype=float)

        joints.append({
            'name': name,
            'type': str(joint.get('type', '')).strip(),
            'origin': _parse_xyz(origin.get('xyz')) if origin is not None else np.array([0.0, 0.0, 0.0], dtype=float),
            'rpy': _parse_xyz(origin.get('rpy')) if origin is not None else np.array([0.0, 0.0, 0.0], dtype=float),
            'parent': str(parent.get('link', '')).strip() if parent is not None else '',
            'child': str(child.get('link', '')).strip() if child is not None else f"{name}_link",
            'axis': _parse_xyz(axis.get('xyz')) if axis is not None else np.array([0.0, 0.0, 0.0], dtype=float),
            'limitLower': _to_float(limit.get('lower')) if limit is not None else 0.0,
            'limitUpper': _to_float(limit.get('upper')) if limit is not None else 0.0,
        })

    return joints


def load_stl_data(path: Optional[str] = None) -> Dict[str, STLData]:
    if path is None:
        stl_dir = _get_default_stl_dir()
    else:
        stl_dir = Path(path)
    stl_data: Dict[str, STLData] = {}

    if path is None and not stl_dir.exists():
        return {
            link_name: STLData(raw_data=None, V_homo=_default_link_vertices(link_name))
            for link_name in datatypes.LINK_NAMES
        }

    for link_name in datatypes.LINK_NAMES:
        stl_path = stl_dir / f'{link_name}.STL'
        try:
            raw_mesh = mesh.Mesh.from_file(str(stl_path))
        except Exception as exc:
            raise FileNotFoundError(
                f'Failed to load STL file: {stl_path}\n'
                f'Underlying error: {exc}'
            ) from exc
        stl_data[link_name] = STLData(raw_data=raw_mesh)

    return stl_data


def _default_link_vertices(link_name: str) -> np.ndarray:
    """Return a tiny built-in box for runtime paths that do not need mesh detail."""
    if link_name == 'base_link':
        x_min, x_max = -0.08, 0.08
        y_min, y_max = -0.03, 0.03
        z_min, z_max = -0.01, 0.12
    else:
        x_min, x_max = -0.005, 0.005
        y_min, y_max = -0.005, 0.005
        z_min, z_max = -0.005, 0.005
    vertices = np.array([
        [x_min, y_min, z_min],
        [x_max, y_min, z_min],
        [x_max, y_max, z_min],
        [x_min, y_max, z_min],
        [x_min, y_min, z_max],
        [x_max, y_min, z_max],
        [x_max, y_max, z_max],
        [x_min, y_max, z_max],
    ], dtype=float)
    return np.vstack([vertices.T, np.ones((1, vertices.shape[0]))])


def load_capsule_from_json(json_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    if json_path is None:
        capsule_data = collision_config.DEFAULT_CAPSULE_PARAMS
    else:
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f'Capsule JSON not found: {path}')
        with path.open('r', encoding='utf-8') as file:
            capsule_data = json.load(file)
    return {
        joint_name: _normalize_capsule_params(params)
        for joint_name, params in capsule_data.items()
    }

