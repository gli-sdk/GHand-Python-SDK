"""
预设手势模块

本模块提供了灵巧手的预设手势定义和执行功能，包括常用手势的
关节角度配置和统一的执行接口。
"""

import math
import time
import logging
from typing import Dict

from .ghand import GHand
from .types import JointId, State, ErrorCode, Joint, GestureType

logger = logging.getLogger("ghand.gestures")


# 手势定义：关节角度（度数）
# 键为 GestureType，值为 {JointId: 角度(度)} 的字典
GESTURE_DEFINITIONS: Dict[GestureType, Dict[JointId, float]] = {
    GestureType.OPEN_HAND: {
        JointId.THUMB_PIP: 0,
        JointId.THUMB_MCP: 0,
        JointId.THUMB_SWING: 20,
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
        JointId.FF_MCP: 80,
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
        JointId.THUMB_ROTATION: -10,
        JointId.FF_PIP: 75,
        JointId.FF_MCP: 80,
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
        JointId.THUMB_ROTATION: -10,
        JointId.FF_PIP: 75,
        JointId.FF_MCP: 80,
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
    hand: GHand,
    gesture: GestureType,
    speed: int = 100,
    torque: int = 100,
    wait: bool = True
) -> bool:
    """执行预设手势

    Args:
        hand: GHand 实例
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


def _wait_for_completion(hand: GHand) -> bool:
    """等待动作完成并检查状态

    Args:
        hand: GHand 实例

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    start_time = time.time()
    has_been_running = False

    while True:
        hand_info = hand.get_hand_info()
        if hand_info.state == State.RUNNING:
            has_been_running = True
        elif has_been_running:
            # 场景 A：从 RUNNING 变为 STOPPED，立刻判定完成
            break
        elif time.time() - start_time >= 0.02:
            # 场景 B：一直是 STOPPED，20ms 观察期后判定完成
            break
        time.sleep(0.005)

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

