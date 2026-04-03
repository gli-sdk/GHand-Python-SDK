"""
关节角度转换器

在 Xiaoyao SDK 的 Joint 对象格式和 Collision SDK 的 numpy 数组格式之间进行双向转换。
"""

import numpy as np
from xiaoyao.dexhand import Joint, JointId


def joints_to_nparray(joints: list[Joint], current_joints: list[Joint] | None = None) -> np.ndarray:
    """
    将 Joint 列表转换为 18 元素的 numpy 数组

    Args:
        joints: 用户提供的关节列表（可以不包含全部18个关节）
        current_joints: 当前关节状态（用于填充未指定的关节）
                       如果为 None，未指定的关节默认为 0°

    Returns:
        np.ndarray: 18 个关节角度的数组，按 JointId 枚举顺序（0-17）

    Example:
        >>> joints = [Joint(id=JointId.THUMB_PIP, angle=0.5)]
        >>> angles = joints_to_nparray(joints)
        >>> print(angles[JointId.THUMB_PIP.value])
        0.5
    """
    # 初始化 18 个关节角度
    angles = np.zeros(18, dtype=float)

    # 如果提供了当前关节状态，先用当前值填充
    if current_joints is not None:
        for joint in current_joints:
            if 0 <= joint.id < 18:
                angles[joint.id] = joint.angle

    # 用用户提供的关节覆盖（仅覆盖用户指定的）
    for joint in joints:
        if 0 <= joint.id < 18:
            angles[joint.id] = joint.angle

    # 规范化处理：避免 -0.0（确保所有接近0的值都是正0）
    angles = np.where(np.abs(angles) < 1e-10, 0.0, angles)

    return angles


def nparray_to_joints(
    angles: np.ndarray,
    speed: int = 100,
    torque: int = 100,
    reference_joints: list[Joint] | None = None
) -> list[Joint]:
    """
    将 numpy 数组转换为 Joint 列表

    Args:
        angles: 18 个关节角度的 numpy 数组
        speed: 所有关节的速度参数（默认100）
               如果提供了 reference_joints，则使用参考关节的速度
        torque: 所有关节的力矩参数（默认100）
                如果提供了 reference_joints，则使用参考关节的力矩
        reference_joints: 参考关节列表，用于保留原始的 speed 和 torque 值

    Returns:
        list[Joint]: 18 个 Joint 对象的列表

    Example:
        >>> angles = np.zeros(18)
        >>> angles[JointId.THUMB_PIP.value] = 0.5
        >>> joints = nparray_to_joints(angles, speed=80, torque=90)
        >>> print(joints[JointId.THUMB_PIP.value].angle)
        0.5

        >>> # 使用参考关节保留 speed 和 torque
        >>> original_joints = [Joint(id=JointId.THUMB_PIP, angle=0.3, speed=50, torque=60)]
        >>> safe_joints = nparray_to_joints(angles, reference_joints=original_joints)
    """
    if len(angles) != 18:
        raise ValueError(f"角度数组必须包含18个元素，当前为 {len(angles)}")

    # 如果提供了参考关节，创建一个 speed 和 torque 的映射
    speed_map = {}
    torque_map = {}
    if reference_joints is not None:
        for joint in reference_joints:
            if 0 <= joint.id < 18:
                speed_map[joint.id] = joint.speed
                torque_map[joint.id] = joint.torque

    joints = []
    for joint_id in range(18):
        # 优先使用参考关节的 speed 和 torque，否则使用默认值
        joint_speed = speed_map.get(joint_id, speed)
        joint_torque = torque_map.get(joint_id, torque)

        joints.append(Joint(
            id=joint_id,
            angle=angles[joint_id],
            speed=joint_speed,
            torque=joint_torque
        ))

    return joints


__all__ = ['joints_to_nparray', 'nparray_to_joints']
