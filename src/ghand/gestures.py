# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

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


def _wait_for_completion(
    hand: GHand,
    timeout_s: float = 5.0,
    poll_period_s: float = 0.005,
    warmup_s: float = 0.1,
    transient_error_grace_s: float = 0.1,
) -> bool:
    """Wait for the hand motion to complete and verify the final state.

    A single ``get_hand_info()`` failure is tolerated: EtherCAT can briefly
    return no fresh TPDO frame during a bad cycle, and treating that as a
    fatal test error causes false negatives. We keep retrying until either
    we get a fresh reading, the transient-error grace period elapses, or
    the overall deadline is hit.

    Args:
        hand: GHand instance.
        timeout_s: Overall deadline for the motion to complete.
        poll_period_s: Delay between polls.
        warmup_s: Grace period during which we allow the hand to not yet
            report RUNNING before we assume the command produced no motion.
        transient_error_grace_s: Contiguous duration for which
            ``get_hand_info()`` may fail before we give up.

    Returns:
        True if the hand ends in a normal state, False otherwise.
    """
    deadline = time.monotonic() + timeout_s
    start_time = time.monotonic()
    has_been_running = False
    hand_info = None
    last_error = None
    first_error_time = None

    while True:
        try:
            hand_info = hand.get_hand_info()
            last_error = None
            first_error_time = None
        except Exception as exc:
            # Only fail if we've been unable to read state for a sustained
            # window — a single WKC miss must not surface as a test error.
            now = time.monotonic()
            if first_error_time is None:
                first_error_time = now
            last_error = exc
            if now - first_error_time >= transient_error_grace_s:
                logger.error(
                    "get_hand_info() failed for %.3fs while waiting for motion: %s",
                    now - first_error_time,
                    exc,
                )
                return False
            if now >= deadline:
                logger.error(
                    "Timed out waiting for motion; last error: %s", exc
                )
                return False
            time.sleep(poll_period_s)
            continue

        if hand_info.state == State.RUNNING:
            has_been_running = True
        elif has_been_running and hand_info.state == State.STOPPED:
            break
        elif hand_info.state.is_abnormal:
            break
        elif not has_been_running and time.monotonic() - start_time >= warmup_s:
            break

        if time.monotonic() >= deadline:
            logger.warning("Motion did not complete within %.3fs", timeout_s)
            break

        time.sleep(poll_period_s)

    if hand_info is None:
        logger.warning(
            "No hand_info observed while waiting for motion (last error: %s)",
            last_error,
        )
        return False
    if hand_info.state.is_abnormal or hand_info.error != ErrorCode.NORMAL:
        logger.warning("Action completed with error state. Please clear fault and retry.")
        return False
    return True


def get_all_gestures() -> list[GestureType]:
    """Return all available predefined gesture types.

    Returns:
        List of GestureType values.
    """
    return list(GestureType)
