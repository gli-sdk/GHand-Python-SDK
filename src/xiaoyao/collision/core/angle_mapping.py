"""Angle order mapping helpers that only reorder joints and never compute DIP values."""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from .passive_dip_mapping import JOINT_ORDER


EXTERNAL_JOINT_ORDER = (
    'THUMB_DIP',
    'THUMB_PIP',
    'THUMB_MCP',
    'THUMB_SWING',
    'THUMB_ROTATION',
    'FF_DIP',
    'FF_PIP',
    'FF_MCP',
    'FF_SWING',
    'MF_DIP',
    'MF_PIP',
    'MF_MCP',
    'RF_DIP',
    'RF_PIP',
    'RF_MCP',
    'LF_DIP',
    'LF_PIP',
    'LF_MCP',
)

# External input angle limits in radians, matching EXTERNAL_JOINT_ORDER.
EXTERNAL_JOINT_LIMITS = (
    (0.0, 1.0472),     # THUMB_DIP
    (0.0, 1.2217),     # THUMB_PIP
    (0.0, 0.8727),     # THUMB_MCP
    (0.0, 1.2220),     # THUMB_SWING
    (-0.1510, 1.0472), # THUMB_ROTATION
    (0.0, 1.0472),     # FF_DIP
    (0.0, 1.2217),     # FF_PIP
    (0.0, 1.2217),     # FF_MCP
    (-0.1745, 0.1745), # FF_SWING
    (0.0, 1.0472),     # MF_DIP
    (0.0, 1.2217),     # MF_PIP
    (0.0, 1.2217),     # MF_MCP
    (0.0, 1.0472),     # RF_DIP
    (0.0, 1.2217),     # RF_PIP
    (0.0, 1.2217),     # RF_MCP
    (0.0, 0.8727),     # LF_DIP
    (0.0, 1.0472),     # LF_PIP
    (0.0, 1.2217),     # LF_MCP
)


EXTERNAL_TO_INTERNAL_NAME_MAP = {
    'THUMB_DIP': 'TH-DIP',
    'THUMB_PIP': 'TH-PIP',
    'THUMB_MCP': 'TH-MCP',
    'THUMB_SWING': 'TH-Swing',
    'THUMB_ROTATION': 'TH-Rotation',
    'FF_DIP': 'IF-DIP',
    'FF_PIP': 'IF-PIP',
    'FF_MCP': 'IF-MCP',
    'FF_SWING': 'IF-Swing',
    'MF_DIP': 'MF-DIP',
    'MF_PIP': 'MF-PIP',
    'MF_MCP': 'MF-MCP',
    'RF_DIP': 'RF-DIP',
    'RF_PIP': 'RF-PIP',
    'RF_MCP': 'RF-MCP',
    'LF_DIP': 'LF-DIP',
    'LF_PIP': 'LF-PIP',
    'LF_MCP': 'LF-MCP',
}

_INTERNAL_NAME_TO_INDEX = {
    joint_name: index for index, joint_name in enumerate(JOINT_ORDER)
}

EXTERNAL_TO_INTERNAL_INDEX_MAP = tuple(
    _INTERNAL_NAME_TO_INDEX[EXTERNAL_TO_INTERNAL_NAME_MAP[external_joint_name]]
    for external_joint_name in EXTERNAL_JOINT_ORDER
)

INTERNAL_TO_EXTERNAL_INDEX_MAP = tuple(
    EXTERNAL_TO_INTERNAL_INDEX_MAP.index(internal_index)
    for internal_index in range(len(JOINT_ORDER))
)


def validate_external_angles(angles: Iterable[float]) -> list[float]:
    if isinstance(angles, (str, bytes)):
        raise ValueError('external_angles must be a numeric sequence, not a string or bytes.')

    try:
        normalized_angles = [float(value) for value in angles]
    except TypeError as exc:
        raise ValueError('external_angles must be an iterable numeric sequence.') from exc
    except ValueError as exc:
        raise ValueError('external_angles contains a value that cannot be converted to float.') from exc

    if len(normalized_angles) != len(EXTERNAL_JOINT_ORDER):
        raise ValueError(
            f'external_angles length must be {len(EXTERNAL_JOINT_ORDER)}, got {len(normalized_angles)}'
        )

    for index, value in enumerate(normalized_angles):
        if not math.isfinite(value):
            raise ValueError(f'external_angles[{index}] must be finite, got {value!r}')
        min_limit, max_limit = EXTERNAL_JOINT_LIMITS[index]
        joint_name = EXTERNAL_JOINT_ORDER[index]
        if value < min_limit or value > max_limit:
            raise ValueError(
                f'external_angles[{index}] ({joint_name}) is out of range: '
                f'got {value:.4f} rad, expected [{min_limit:.4f}, {max_limit:.4f}] rad'
            )

    return normalized_angles


def validate_internal_angles(angles: Iterable[float]) -> list[float]:
    if isinstance(angles, (str, bytes)):
        raise ValueError('internal_angles must be a numeric sequence, not a string or bytes.')

    try:
        normalized_angles = [float(value) for value in angles]
    except TypeError as exc:
        raise ValueError('internal_angles must be an iterable numeric sequence.') from exc
    except ValueError as exc:
        raise ValueError('internal_angles contains a value that cannot be converted to float.') from exc

    if len(normalized_angles) != len(JOINT_ORDER):
        raise ValueError(
            f'internal_angles length must be {len(JOINT_ORDER)}, got {len(normalized_angles)}'
        )

    for index, value in enumerate(normalized_angles):
        if not math.isfinite(value):
            raise ValueError(f'internal_angles[{index}] must be finite, got {value!r}')

    return normalized_angles


def _validate_angle_count(angles: Sequence[float], order_name: str) -> None:
    if len(angles) != len(JOINT_ORDER):
        raise ValueError(
            f'{order_name} angle sequence length must be {len(JOINT_ORDER)}, got {len(angles)}'
        )


def _remap_angles_to_float_list(
    angles: Sequence[float],
    index_map: Sequence[int],
) -> list[float]:
    mapped_angles = [0.0] * len(index_map)
    for source_index, target_index in enumerate(index_map):
        mapped_angles[target_index] = float(angles[source_index])
    return mapped_angles


def external_to_internal_angles(angles: Iterable[float]) -> list[float]:
    normalized_angles = validate_external_angles(angles)
    return _remap_angles_to_float_list(normalized_angles, EXTERNAL_TO_INTERNAL_INDEX_MAP)


def internal_to_external_angles(angles: Sequence[float]) -> list[float]:
    _validate_angle_count(angles, 'internal')
    return _remap_angles_to_float_list(angles, INTERNAL_TO_EXTERNAL_INDEX_MAP)


__all__ = [
    'EXTERNAL_JOINT_ORDER',
    'EXTERNAL_TO_INTERNAL_NAME_MAP',
    'EXTERNAL_TO_INTERNAL_INDEX_MAP',
    'INTERNAL_TO_EXTERNAL_INDEX_MAP',
    'validate_external_angles',
    'validate_internal_angles',
    'external_to_internal_angles',
    'internal_to_external_angles',
]