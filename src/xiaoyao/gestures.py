"""
预设手势模块

本模块提供了灵巧手的预设手势定义和执行功能，包括常用手势的
关节角度配置和统一的执行接口。
"""

import math
import time
import enum
import logging
from typing import Dict

from .dexhand import DexHand, JointId, Joint
from .error import State, ErrorCode

logger = logging.getLogger("xiaoyao.gestures")


class GestureType(enum.Enum):
    """预设手势类型枚举"""
    OPEN_HAND = "open_hand"        # 张开手
    FIST = "fist"                  # 握拳
    OK = "ok"                      # OK手势
    THUMBS_UP = "thumbs_up"        # 竖大拇指
    SIX_SIGN = "six_sign"          # 六手势（比666）


# 手势定义：关节角度（度数）
# 键为 GestureType，值为 {JointId: 角度(度)} 的字典
GESTURE_DEFINITIONS: Dict[GestureType, Dict[JointId, float]] = {
    GestureType.OPEN_HAND: {
        JointId.THUMB_PIP: 0,
        JointId.THUMB_MCP: 0,
        JointId.THUMB_SWING: 0,
        JointId.THUMB_ROTATION: 0,
        JointId.FF_PIP: 0,
        JointId.FF_MCP: 0,
        JointId.FF_SWING: 0,
        JointId.MF_PIP: 0,
        JointId.MF_MCP: 0,
        JointId.RF_PIP: 0,
        JointId.RF_MCP: 0,
        JointId.LF_PIP: 0,
        JointId.LF_MCP: 0,
    },
    GestureType.FIST: {
        JointId.THUMB_PIP: 30,
        JointId.THUMB_MCP: 20,
        JointId.THUMB_SWING: 20,
        JointId.THUMB_ROTATION: 0,
        JointId.FF_PIP: 75,
        JointId.FF_MCP: 85,
        JointId.FF_SWING: 0,
        JointId.MF_PIP: 85,
        JointId.MF_MCP: 85,
        JointId.RF_PIP: 85,
        JointId.RF_MCP: 85,
        JointId.LF_PIP: 69,
        JointId.LF_MCP: 85,
    },
    GestureType.OK: {
        JointId.THUMB_PIP: 20,
        JointId.THUMB_MCP: 20,
        JointId.THUMB_SWING: 20,
        JointId.THUMB_ROTATION: 0,
        JointId.FF_PIP: 67,
        JointId.FF_MCP: 35,
        JointId.FF_SWING: 0,
        JointId.MF_PIP: 0,
        JointId.MF_MCP: 0,
        JointId.RF_PIP: 0,
        JointId.RF_MCP: 0,
        JointId.LF_PIP: 0,
        JointId.LF_MCP: 0,
    },
    GestureType.THUMBS_UP: {
        JointId.THUMB_PIP: 0,
        JointId.THUMB_MCP: 0,
        JointId.THUMB_SWING: 20,
        JointId.THUMB_ROTATION: 0,
        JointId.FF_PIP: 75,
        JointId.FF_MCP: 85,
        JointId.FF_SWING: 0,
        JointId.MF_PIP: 85,
        JointId.MF_MCP: 85,
        JointId.RF_PIP: 85,
        JointId.RF_MCP: 85,
        JointId.LF_PIP: 69,
        JointId.LF_MCP: 85,
    },
    GestureType.SIX_SIGN: {
        JointId.THUMB_PIP: 0,
        JointId.THUMB_MCP: 0,
        JointId.THUMB_SWING: 20,
        JointId.THUMB_ROTATION: 0,
        JointId.FF_PIP: 75,
        JointId.FF_MCP: 85,
        JointId.FF_SWING: 0,
        JointId.MF_PIP: 85,
        JointId.MF_MCP: 85,
        JointId.RF_PIP: 85,
        JointId.RF_MCP: 85,
        JointId.LF_PIP: 0,
        JointId.LF_MCP: 0,
    },
}


def execute_gesture(
    hand: DexHand,
    gesture: GestureType,
    speed: int = 100,
    torque: int = 100,
    wait: bool = True
) -> bool:
    """执行预设手势

    Args:
        hand: DexHand 实例
        gesture: 要执行的手势类型
        speed: 速度百分比 (0-100)，默认 100
        torque: 力矩百分比 (0-100)，默认 100
        wait: 是否等待动作完成，默认 True

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    if gesture not in GESTURE_DEFINITIONS:
        logger.error(f"Unknown gesture: {gesture}")
        return False

    angles = GESTURE_DEFINITIONS[gesture]
    joints = [
        Joint(id=joint_id, angle=math.radians(angle), speed=speed, torque=torque)
        for joint_id, angle in angles.items()
    ]

    result = hand.move_joints(joints)

    if result:
        return _wait_for_completion(hand)

    return result


def _wait_for_completion(hand: DexHand) -> bool:
    """等待动作完成并检查状态

    Args:
        hand: DexHand 实例

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    while True:
        hand_info = hand.get_hand_info()
        if hand_info.state == State.RUNNING:
            break
        time.sleep(0.01)  # 避免 CPU 占用过高

    while True:
        hand_info = hand.get_hand_info()
        if hand_info.state != State.RUNNING:
            break

    if hand_info.state in [State.ABNORMAL_RUNNING, State.PROTECTIVE_STOPED] or \
       hand_info.error != ErrorCode.NORMAL:
        logger.warning("Action completed with error state. Please clear fault and retry.")
        return False
    return True


def get_all_gestures() -> list[GestureType]:
    """获取所有可用的手势类型

    Returns:
        list[GestureType]: 所有手势类型的列表
    """
    return list(GestureType)


def get_gesture_name(gesture: GestureType) -> str:
    """获取手势的中文名称

    Args:
        gesture: 手势类型

    Returns:
        str: 手势中文名称
    """
    names = {
        GestureType.OPEN_HAND: "张开手",
        GestureType.FIST: "握拳",
        GestureType.OK: "OK手势",
        GestureType.THUMBS_UP: "竖大拇指",
        GestureType.SIX_SIGN: "六手势",
    }
    return names.get(gesture, "未知手势")
