"""A7 SDK angle validation and unit conversion helpers."""

from __future__ import annotations

import math
import warnings
from typing import Iterable, Sequence

import numpy as np

from .datatypes import JOINT_NAMES
from .passive_dip_mapping import JOINT_ORDER
from .read_data import read_urdf_xml


SDK_JOINT_ORDER = JOINT_ORDER
EXTERNAL_JOINT_ORDER = SDK_JOINT_ORDER
PASSIVE_JOINT_NAMES = frozenset({"LF_DIP", "RF_DIP", "MF_DIP", "FF_DIP", "Thumb_IP"})
ACTIVE_JOINT_NAMES = tuple(n for n in JOINT_NAMES if n not in PASSIVE_JOINT_NAMES)
DIP_JOINT_NAMES = tuple(n for n in JOINT_NAMES if n in PASSIVE_JOINT_NAMES)
LIMIT_TOLERANCE_DEG = 5.0
_LIMIT_EPS_DEG = 1e-9

_LAST_WARNINGS: list[str] = []
_URDF_LIMITS_DEG: dict[str, tuple[float, float]] | None = None


def _normalize_angles(angles: Iterable[float], label: str) -> list[float]:
    if isinstance(angles, (str, bytes)):
        raise ValueError(f"{label} must be a numeric sequence, not a string or bytes.")

    try:
        normalized = [float(value) for value in angles]
    except TypeError as exc:
        raise ValueError(f"{label} must be an iterable numeric sequence.") from exc
    except ValueError as exc:
        raise ValueError(f"{label} contains a value that cannot be converted to float.") from exc

    if len(normalized) != len(SDK_JOINT_ORDER):
        raise ValueError(f"{label} length must be {len(SDK_JOINT_ORDER)}, got {len(normalized)}")

    for index, value in enumerate(normalized):
        if not math.isfinite(value):
            raise ValueError(f"{label}[{index}] must be finite, got {value!r}")

    return normalized


def _load_urdf_limits_deg() -> dict[str, tuple[float, float]]:
    global _URDF_LIMITS_DEG
    if _URDF_LIMITS_DEG is not None:
        return _URDF_LIMITS_DEG

    limits: dict[str, tuple[float, float]] = {}
    for joint in read_urdf_xml():
        name = str(joint["name"])
        limits[name] = (
            math.degrees(float(joint["limitLower"])),
            math.degrees(float(joint["limitUpper"])),
        )
    _URDF_LIMITS_DEG = limits
    return limits


def clear_angle_warnings() -> None:
    _LAST_WARNINGS.clear()


def angle_warnings() -> list[str]:
    return list(_LAST_WARNINGS)


def neutral_sdk_degrees() -> np.ndarray:
    limits = _load_urdf_limits_deg()
    angles = []
    for joint_name in SDK_JOINT_ORDER:
        if joint_name in DIP_JOINT_NAMES:
            angles.append(0.0)
            continue
        lower, upper = limits[joint_name]
        angles.append(min(max(0.0, lower), upper))
    return np.asarray(angles, dtype=float)


def neutral_internal_radians() -> np.ndarray:
    return np.radians(neutral_sdk_degrees())


def sdk_degrees_to_internal_radians(angles_deg: Iterable[float]) -> np.ndarray:
    clear_angle_warnings()
    normalized = _normalize_angles(angles_deg, "sdk_angles")
    limits = _load_urdf_limits_deg()
    clamped = list(normalized)

    for index, joint_name in enumerate(SDK_JOINT_ORDER):
        if joint_name in DIP_JOINT_NAMES:
            continue
        lower, upper = limits[joint_name]
        value = normalized[index]
        tolerance_lower = lower - LIMIT_TOLERANCE_DEG
        tolerance_upper = upper + LIMIT_TOLERANCE_DEG
        if value < tolerance_lower - _LIMIT_EPS_DEG or value > tolerance_upper + _LIMIT_EPS_DEG:
            raise ValueError(
                f"sdk_angles[{index}] ({joint_name}) is out of range: "
                f"got {value:.4f} deg, expected [{tolerance_lower:.4f}, {tolerance_upper:.4f}] deg "
                f"with {LIMIT_TOLERANCE_DEG:.1f} deg tolerance"
            )
        if value < lower - _LIMIT_EPS_DEG or value > upper + _LIMIT_EPS_DEG:
            clamped_value = min(max(value, lower), upper)
            message = (
                f"{joint_name} angle {value:.4f} deg is outside URDF limit "
                f"[{lower:.4f}, {upper:.4f}] deg but within tolerance; clamped to {clamped_value:.4f} deg."
            )
            warnings.warn(message, RuntimeWarning, stacklevel=2)
            _LAST_WARNINGS.append(message)
            clamped[index] = clamped_value

    return np.radians(np.asarray(clamped, dtype=float))


def internal_radians_to_sdk_degrees(angles_rad: Sequence[float]) -> np.ndarray:
    normalized = _normalize_angles(angles_rad, "internal_angles")
    return np.degrees(np.asarray(normalized, dtype=float))


def validate_external_angles(angles: Iterable[float]) -> list[float]:
    return _normalize_angles(angles, "sdk_angles")


def validate_internal_angles(angles: Iterable[float]) -> list[float]:
    return _normalize_angles(angles, "internal_angles")


def external_to_internal_angles(angles: Iterable[float]) -> list[float]:
    return sdk_degrees_to_internal_radians(angles).tolist()


def internal_to_external_angles(angles: Sequence[float]) -> list[float]:
    return internal_radians_to_sdk_degrees(angles).tolist()


EXTERNAL_TO_INTERNAL_NAME_MAP = {name: name for name in SDK_JOINT_ORDER}
EXTERNAL_TO_INTERNAL_INDEX_MAP = tuple(range(len(SDK_JOINT_ORDER)))
INTERNAL_TO_EXTERNAL_INDEX_MAP = tuple(range(len(SDK_JOINT_ORDER)))


__all__ = [
    "SDK_JOINT_ORDER",
    "EXTERNAL_JOINT_ORDER",
    "ACTIVE_JOINT_NAMES",
    "DIP_JOINT_NAMES",
    "PASSIVE_JOINT_NAMES",
    "LIMIT_TOLERANCE_DEG",
    "EXTERNAL_TO_INTERNAL_NAME_MAP",
    "EXTERNAL_TO_INTERNAL_INDEX_MAP",
    "INTERNAL_TO_EXTERNAL_INDEX_MAP",
    "angle_warnings",
    "clear_angle_warnings",
    "neutral_sdk_degrees",
    "neutral_internal_radians",
    "sdk_degrees_to_internal_radians",
    "internal_radians_to_sdk_degrees",
    "validate_external_angles",
    "validate_internal_angles",
    "external_to_internal_angles",
    "internal_to_external_angles",
]
