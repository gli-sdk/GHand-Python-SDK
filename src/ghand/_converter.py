from typing import Optional

import numpy as np

from .types import JointCommand, JointData, JointId


def joints_to_nparray(
    joints: list[JointCommand | JointData],
    current_joints: Optional[list[JointData]] = None,
) -> np.ndarray:
    """Convert a list of JointCommand or JointData to an 18-dimensional numpy array.

    Unspecified joints are filled from ``current_joints`` if provided,
    otherwise default to 0.0.

    Args:
        joints: List of JointCommand objects to convert.
        current_joints: Optional list of current JointData states used for filling
            unspecified joints.

    Returns:
        An 18-element numpy array of joint angles in degrees.
    """
    angles = np.zeros(18, dtype=float)
    if current_joints is not None:
        for j in current_joints:
            angles[int(j.id)] = float(j.angle)
    for j in joints:
        angles[int(j.id)] = float(j.angle)
    return angles


def nparray_to_joints(
    angles: np.ndarray, speed: int = 100, torque: int = 100
) -> list[JointCommand]:
    """Convert an 18-dimensional numpy array back to a list of JointCommand objects.

    The returned list uses ids 0-17, matching the ``ghand.JointId``
    enumeration order.

    Args:
        angles: 18-element numpy array of joint angles in degrees.
        speed: Speed percentage (0-100) applied to all joints. Defaults to 100.
        torque: Torque percentage (0-100) applied to all joints. Defaults to 100.

    Returns:
        List of 18 JointCommand objects.
    """
    return [
        JointCommand(id=JointId(i), angle=float(angles[i]), speed=speed, torque=torque)
        for i in range(18)
    ]
