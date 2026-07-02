# Copyright 2026 GLITech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Predefined gesture module.

Provides joint-angle definitions and a unified execution interface for
commonly used dexterous-hand gestures.
"""

import logging
import time
from typing import Dict

from .ghand import GHand
from .types import ErrorCode, GestureType, JointCommand, JointId, State

logger = logging.getLogger("ghand.gestures")


# Gesture definitions: joint angles in degrees.
# Key is GestureType, value is a dict of {JointId: angle(degrees)}.
GESTURE_DEFINITIONS: Dict[GestureType, Dict[JointId, float]] = {
    GestureType.OPEN_HAND: {
        JointId.THUMB_MCP: 0,
        JointId.THUMB_TMC_FE: 0,
        JointId.THUMB_TMC_AA: 20,
        JointId.THUMB_TMC_PS: 0,
        JointId.FF_PIP: 0,
        JointId.FF_MCP: 0,
        JointId.FF_MCP_AA: 0,
        JointId.MF_PIP: 0,
        JointId.MF_MCP: 0,
        JointId.RF_PIP: 0,
        JointId.RF_MCP: 0,
        JointId.LF_PIP: 0,
        JointId.LF_MCP: 0,
    },
    GestureType.FIST: {
        JointId.THUMB_MCP: 30,
        JointId.THUMB_TMC_FE: 20,
        JointId.THUMB_TMC_AA: 20,
        JointId.THUMB_TMC_PS: 0,
        JointId.FF_PIP: 75,
        JointId.FF_MCP: 80,
        JointId.FF_MCP_AA: 0,
        JointId.MF_PIP: 85,
        JointId.MF_MCP: 85,
        JointId.RF_PIP: 85,
        JointId.RF_MCP: 85,
        JointId.LF_PIP: 69,
        JointId.LF_MCP: 85,
    },
    GestureType.OK: {
        JointId.THUMB_MCP: 20,
        JointId.THUMB_TMC_FE: 20,
        JointId.THUMB_TMC_AA: 20,
        JointId.THUMB_TMC_PS: 0,
        JointId.FF_PIP: 67,
        JointId.FF_MCP: 35,
        JointId.FF_MCP_AA: 0,
        JointId.MF_PIP: 0,
        JointId.MF_MCP: 0,
        JointId.RF_PIP: 0,
        JointId.RF_MCP: 0,
        JointId.LF_PIP: 0,
        JointId.LF_MCP: 0,
    },
    GestureType.THUMBS_UP: {
        JointId.THUMB_MCP: 0,
        JointId.THUMB_TMC_FE: 0,
        JointId.THUMB_TMC_AA: 20,
        JointId.THUMB_TMC_PS: -10,
        JointId.FF_PIP: 75,
        JointId.FF_MCP: 80,
        JointId.FF_MCP_AA: 0,
        JointId.MF_PIP: 85,
        JointId.MF_MCP: 85,
        JointId.RF_PIP: 85,
        JointId.RF_MCP: 85,
        JointId.LF_PIP: 69,
        JointId.LF_MCP: 85,
    },
    GestureType.SIX_SIGN: {
        JointId.THUMB_MCP: 0,
        JointId.THUMB_TMC_FE: 0,
        JointId.THUMB_TMC_AA: 20,
        JointId.THUMB_TMC_PS: -10,
        JointId.FF_PIP: 75,
        JointId.FF_MCP: 80,
        JointId.FF_MCP_AA: 0,
        JointId.MF_PIP: 85,
        JointId.MF_MCP: 85,
        JointId.RF_PIP: 85,
        JointId.RF_MCP: 85,
        JointId.LF_PIP: 0,
        JointId.LF_MCP: 0,
    },
}


def execute_gesture(
    hand: GHand, gesture: GestureType, speed: int = 100, torque: int = 100, wait: bool = True
) -> bool:
    """Execute a predefined gesture.

    Args:
        hand: GHand instance.
        gesture: Gesture type to execute.
        speed: Speed percentage (0-100). Defaults to 100.
        torque: Torque percentage (0-100). Defaults to 100.
        wait: Whether to block until the motion completes. Defaults to True.

    Returns:
        True on success, False on failure.
    """
    if gesture not in GESTURE_DEFINITIONS:
        logger.error("Unknown gesture: %s", gesture)
        return False

    angles = GESTURE_DEFINITIONS[gesture]
    joints = [
        JointCommand(id=joint_id, angle=angle, speed=speed, torque=torque)
        for joint_id, angle in angles.items()
    ]

    result = hand.move_joints(joints)

    if result:
        return _wait_for_completion(hand)

    return result


def _wait_for_completion(hand: GHand) -> bool:
    """Wait for the hand motion to complete and verify the final state.

    Args:
        hand: GHand instance.

    Returns:
        True if the hand ends in a normal state, False otherwise.
    """
    start_time = time.time()
    has_been_running = False

    while True:
        hand_info = hand.get_hand_info()
        if hand_info.state == State.RUNNING:
            has_been_running = True
        elif has_been_running:
            break
        elif time.time() - start_time >= 0.02:
            break
        time.sleep(0.005)

    if (
        hand_info.state in [State.ABNORMAL_RUNNING, State.PROTECTIVE_STOPPED]
        or hand_info.error != ErrorCode.NORMAL
    ):
        logger.warning("Action completed with error state. Please clear fault and retry.")
        return False
    return True


def get_all_gestures() -> list[GestureType]:
    """Return all available predefined gesture types.

    Returns:
        List of GestureType values.
    """
    return list(GestureType)
