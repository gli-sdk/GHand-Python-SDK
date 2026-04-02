from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from stl import mesh

from . import datatypes
from .datatypes import STLData


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URDF_JSON_PATH = PROJECT_ROOT / 'raw_data' / 'G5-13A-A6.json'
DEFAULT_STL_DIR = PROJECT_ROOT / 'raw_data' / 'URDF_data' / 'meshes'
DEFAULT_CAPSULE_JSON_PATH = PROJECT_ROOT / 'raw_data' / 'capsule_parameters.json'


def _to_float(value: Any, default: float = 0.0) -> float:
    return float(value) if value is not None else default


def _resolve_path(path: Optional[str | Path], default_path: Path) -> Path:
    return Path(path) if path is not None else default_path


def _load_json_data(json_path: Optional[str | Path], default_path: Path, label: str) -> Any:
    path = _resolve_path(json_path, default_path)
    if not path.exists():
        raise FileNotFoundError(f'{label} JSON not found: {path}')

    with path.open('r', encoding='utf-8') as file:
        return json.load(file)


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


def _normalize_urdf_joint(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    joint_name = item.get('Joint Name', '')
    if joint_name is None or str(joint_name).strip() == '':
        return None

    return {
        'name': str(joint_name).strip(),
        'type': str(item.get('Joint Type', '') or '').strip(),
        'origin': np.array(
            [
                _to_float(item.get('Joint Origin X')),
                _to_float(item.get('Joint Origin Y')),
                _to_float(item.get('Joint Origin Z')),
            ],
            dtype=float,
        ),
        'rpy': np.array(
            [
                _to_float(item.get('Joint Origin Roll')),
                _to_float(item.get('Joint Origin Pitch')),
                _to_float(item.get('Joint Origin Yaw')),
            ],
            dtype=float,
        ),
        'parent': str(item.get('Parent', '') or '').strip(),
        'axis': np.array(
            [
                _to_float(item.get('Joint Axis X')),
                _to_float(item.get('Joint Axis Y')),
                _to_float(item.get('Joint Axis Z')),
            ],
            dtype=float,
        ),
        'limitLower': _to_float(item.get('Limit Lower')),
        'limitUpper': _to_float(item.get('Limit Upper')),
    }


def _normalize_capsule_params(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'xyz': np.array(params['xyz'], dtype=float),
        'radius': _to_float(params.get('radius')),
        'k': _to_float(params.get('k')),
        'theta_prime': _to_float(params.get('theta_prime')),
    }


def get_finger_joints(joint_data: List[Dict[str, Any]], finger_name: str) -> List[Dict[str, Any]]:
    valid_fingers = ['LF', 'RF', 'MF', 'IF', 'TH']
    if finger_name not in valid_fingers:
        raise ValueError(f'finger_name must be one of: {", ".join(valid_fingers)}')

    return [joint for joint in joint_data if joint['name'].startswith(f'{finger_name}-')]


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
    angles_array = _extract_numeric_array(dataframe, drop_columns=['Collision-pair'])
    return angles_array, collision_pairs


def load_safe_angles(csv_path: str = 'Safe_Angles.csv') -> np.ndarray:
    dataframe = _read_csv_with_fallback_encodings(csv_path, 'safe angles CSV')
    return _extract_numeric_array(dataframe)


def read_urdf_json(json_path: Optional[str] = None) -> List[Dict[str, Any]]:
    joint_data_raw = _load_json_data(json_path, DEFAULT_URDF_JSON_PATH, 'URDF')
    normalized_joints = [_normalize_urdf_joint(item) for item in joint_data_raw]
    return [joint for joint in normalized_joints if joint is not None]


def load_stl_data(path: Optional[str] = None) -> Dict[str, STLData]:
    stl_dir = _resolve_path(path, DEFAULT_STL_DIR)
    stl_data: Dict[str, STLData] = {}

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


def load_capsule_from_json(json_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    capsule_data = _load_json_data(json_path, DEFAULT_CAPSULE_JSON_PATH, 'capsule')
    return {
        joint_name: _normalize_capsule_params(params)
        for joint_name, params in capsule_data.items()
    }
