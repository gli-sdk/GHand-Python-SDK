import numpy as np
from typing import List, Optional
from ghand.types import Joint, JointId


def joints_to_nparray(joints: list, current_joints: Optional[list] = None) -> np.ndarray:
    """
    将 ghand 的 Joint 列表转为 18 维 numpy 数组（弧度）。
    未指定的关节使用 current_joints 填充，否则为 0。
    """
    angles = np.zeros(18, dtype=float)
    if current_joints is not None:
        for j in current_joints:
            angles[int(j.id)] = float(j.angle)
    for j in joints:
        angles[int(j.id)] = float(j.angle)
    return angles


def nparray_to_joints(angles: np.ndarray, speed: int = 100, torque: int = 100) -> list:
    """
    将 18 维 numpy 数组转回 ghand 的 Joint 列表。

    返回的 Joint 列表中，id 顺序为 0-17，对应 ghand.JointId 枚举顺序。
    """
    return [
        Joint(id=JointId(i), angle=float(angles[i]), speed=speed, torque=torque)
        for i in range(18)
    ]
