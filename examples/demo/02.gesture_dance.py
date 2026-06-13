import logging
import time

from ghand import ProductType, CommType, GHand, JointCommand, JointId, configure_logging
from ghand.gestures import GestureType, execute_gesture

# Configure logging output to console
configure_logging(level=logging.INFO)
logger = logging.getLogger("ghand")

# Constant definitions
ACTION_DELAY = 1
FLEX_CYCLE_COUNT = 4

# Thumb touches other fingers gestures
thumb_touch_little_finger = {
    JointId.THUMB_PIP: 20,
    JointId.THUMB_MCP: 50,
    JointId.THUMB_SWING: 60,
    JointId.THUMB_ROTATION: 0,
    JointId.LF_PIP: 56,
    JointId.LF_MCP: 28,
    # Other joints stay at zero
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 0,
    JointId.MF_MCP: 0,
    JointId.RF_PIP: 0,
    JointId.RF_MCP: 0,
}

thumb_touch_ring_finger = {
    JointId.THUMB_PIP: 19,
    JointId.THUMB_MCP: 38,
    JointId.THUMB_SWING: 45,
    JointId.THUMB_ROTATION: 0,
    JointId.RF_PIP: 67,
    JointId.RF_MCP: 39,
    JointId.LF_PIP: 0,
    JointId.LF_MCP: 0,
    # Other joints stay at zero
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 0,
    JointId.MF_MCP: 0,
}

thumb_touch_middle_finger = {
    JointId.THUMB_PIP: 17,
    JointId.THUMB_MCP: 27,
    JointId.THUMB_SWING: 30,
    JointId.THUMB_ROTATION: 0,
    JointId.MF_PIP: 40,
    JointId.MF_MCP: 57,
    JointId.RF_PIP: 0,
    JointId.RF_MCP: 0,
    # Other joints stay at zero
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.LF_PIP: 0,
    JointId.LF_MCP: 0,
}

thumb_touch_index_finger = {
    JointId.THUMB_PIP: 13,
    JointId.THUMB_MCP: 14,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 51,
    JointId.FF_MCP: 46,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 0,
    JointId.MF_MCP: 0,
    # Other joints stay at zero
    JointId.RF_PIP: 0,
    JointId.RF_MCP: 0,
    JointId.LF_PIP: 0,
    JointId.LF_MCP: 0,
}

# Individual finger opening gestures
open_index_finger = {
    JointId.THUMB_PIP: 30,
    JointId.THUMB_MCP: 20,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    # Open index finger
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    # Other joints stay at zero
    JointId.MF_PIP: 75,
    JointId.MF_MCP: 70,
    JointId.RF_PIP: 75,
    JointId.RF_MCP: 70,
    JointId.LF_PIP: 70,
    JointId.LF_MCP: 70,
}

open_middle_finger = {
    JointId.THUMB_PIP: 30,
    JointId.THUMB_MCP: 20,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    # Open index finger
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 0,
    JointId.MF_MCP: 0,
    # Other joints stay at zero
    JointId.RF_PIP: 75,
    JointId.RF_MCP: 70,
    JointId.LF_PIP: 70,
    JointId.LF_MCP: 70,
}

open_ring_finger = {
    JointId.THUMB_PIP: 30,
    JointId.THUMB_MCP: 20,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    # Open ring finger
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 0,
    JointId.MF_MCP: 0,
    JointId.RF_PIP: 0,
    JointId.RF_MCP: 0,
    # Other joints stay at zero
    JointId.LF_PIP: 70,
    JointId.LF_MCP: 70,
}

open_little_finger = {
    JointId.THUMB_PIP: 30,
    JointId.THUMB_MCP: 20,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    # Open little finger
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 0,
    JointId.MF_MCP: 0,
    JointId.RF_PIP: 0,
    JointId.RF_MCP: 0,
    JointId.LF_PIP: 0,
    JointId.LF_MCP: 0,
}

# Index finger swing gestures
index_finger_swing_neg = {
    JointId.THUMB_PIP: 30,
    JointId.THUMB_MCP: 20,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    # Swing -10 degrees
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: -10,
    JointId.MF_PIP: 75,
    JointId.MF_MCP: 70,
    JointId.RF_PIP: 75,
    JointId.RF_MCP: 70,
    JointId.LF_PIP: 70,
    JointId.LF_MCP: 70,
}

index_finger_swing_pos = {
    JointId.THUMB_PIP: 30,
    JointId.THUMB_MCP: 20,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    # Swing 10 degrees
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 10,
    JointId.MF_PIP: 75,
    JointId.MF_MCP: 70,
    JointId.RF_PIP: 75,
    JointId.RF_MCP: 70,
    JointId.LF_PIP: 70,
    JointId.LF_MCP: 70,
}

# Finger flexing gestures
flex_all_fingers = {
    JointId.THUMB_PIP: 0,
    JointId.THUMB_MCP: 0,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 75,
    JointId.FF_MCP: 70,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 75,
    JointId.MF_MCP: 70,
    JointId.RF_PIP: 75,
    JointId.RF_MCP: 70,
    JointId.LF_PIP: 74,
    JointId.LF_MCP: 70,
}

flex_ring_and_little_fingers = {
    JointId.THUMB_PIP: 0,
    JointId.THUMB_MCP: 0,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 0,
    JointId.MF_MCP: 0,
    JointId.RF_PIP: 75,
    JointId.RF_MCP: 70,
    JointId.LF_PIP: 74,
    JointId.LF_MCP: 70,
}

flex_middle_ring_little_fingers = {
    JointId.THUMB_PIP: 0,
    JointId.THUMB_MCP: 0,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 75,
    JointId.MF_MCP: 70,
    JointId.RF_PIP: 75,
    JointId.RF_MCP: 70,
    JointId.LF_PIP: 74,
    JointId.LF_MCP: 70,
}

flex_little_finger = {
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
    JointId.LF_PIP: 74,
    JointId.LF_MCP: 70,
}

flex_index_finger = {
    JointId.THUMB_PIP: 0,
    JointId.THUMB_MCP: 0,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 75,
    JointId.FF_MCP: 70,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 0,
    JointId.MF_MCP: 0,
    JointId.RF_PIP: 0,
    JointId.RF_MCP: 0,
    JointId.LF_PIP: 0,
    JointId.LF_MCP: 0,
}

flex_middle_finger = {
    JointId.THUMB_PIP: 0,
    JointId.THUMB_MCP: 0,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 0,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 75,
    JointId.MF_MCP: 70,
    JointId.RF_PIP: 0,
    JointId.RF_MCP: 0,
    JointId.LF_PIP: 0,
    JointId.LF_MCP: 0,
}

flex_index_middle_and_ring_fingers = {
    JointId.THUMB_PIP: 0,
    JointId.THUMB_MCP: 0,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 75,
    JointId.FF_MCP: 70,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 75,
    JointId.MF_MCP: 70,
    JointId.RF_PIP: 75,
    JointId.RF_MCP: 70,
    JointId.LF_PIP: 0,
    JointId.LF_MCP: 0,
}


# Generic joint position execution function
def execute_joint_positions(hand, joint_positions, description):
    """Generic joint position execution function

    Args:
        hand: GHand instance
        joint_positions: Joint position dictionary
        description: Action description

    Returns:
        bool: True if action executed successfully, False otherwise
    """
    try:
        joints = [
            JointCommand(id=joint_id, angle=angle, speed=100, torque=100)
            for joint_id, angle in joint_positions.items()
        ]
        if not hand.move_joints(joints):
            logger.error("%s execution failed", description)
            return False
        time.sleep(ACTION_DELAY)
        return True
    except Exception as e:
        logger.error("%s execution failed: %s", description, e)
        return False


# Decorator: unified error handling
def handle_action_error(description):
    """Unified error handling decorator

    Args:
        description: Action description

    Returns:
        Decorated function
    """

    def decorator(func):

        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error("%s execution failed: %s", description, e)
                return False

        return wrapper

    return decorator


@handle_action_error("Thumb touches other fingers")
def thumb_touch_tp(hand):
    """Thumb sequentially touches fingertips of other fingers

    Action sequence:
    1. Thumb touches little finger
    2. Thumb touches ring finger
    3. Thumb touches middle finger
    4. Thumb touches index finger
    5. Reset to zero position

    Args:
        hand: GHand instance

    Returns:
        bool: True if action executed successfully, False otherwise
    """
    # 1: Thumb and little finger touch, other fingers stay at zero
    if not execute_joint_positions(hand, thumb_touch_little_finger, "Thumb touches little finger"):
        return False

    # 2: Thumb and ring finger touch, other fingers stay at zero
    if not execute_joint_positions(hand, thumb_touch_ring_finger, "Thumb touches ring finger"):
        return False

    # 3: Thumb and middle finger touch, other fingers stay at zero
    if not execute_joint_positions(hand, thumb_touch_middle_finger, "Thumb touches middle finger"):
        return False

    # 4: Thumb and index finger touch, other fingers stay at zero
    if not execute_joint_positions(hand, thumb_touch_index_finger, "Thumb touches index finger"):
        return False

    # 5: All fingers stay at zero (use preset gesture)
    if not execute_gesture(hand, GestureType.OPEN_HAND):
        logger.error("Finger reset action failed")
        return False
    time.sleep(ACTION_DELAY)

    return True


@handle_action_error("Fist then open")
def fist_then_open(hand):
    """Fist then open action (using preset gesture)

    Action sequence:
    1. Fist
    2. Open palm

    Args:
        hand: GHand instance

    Returns:
        bool: True if action executed successfully, False otherwise
    """
    # 1: Fist action
    if not execute_gesture(hand, GestureType.FIST):
        logger.error("Fist action failed")
        return False
    time.sleep(ACTION_DELAY)

    # 2: Open palm action
    if not execute_gesture(hand, GestureType.OPEN_HAND):
        logger.error("Open palm action failed")
        return False
    time.sleep(ACTION_DELAY)

    return True


@handle_action_error("Sequential finger opening")
def seq_open_finger(hand):
    """Sequentially open fingers

    Action sequence:
    1. Fist
    2. Open index finger
    3. Open middle finger
    4. Open ring finger
    5. Open little finger
    6. Open thumb

    Args:
        hand: GHand instance

    Returns:
        bool: True if action executed successfully, False otherwise
    """
    # 1: Fist action (using preset gesture)
    if not execute_gesture(hand, GestureType.FIST):
        logger.error("Fist action failed")
        return False
    time.sleep(ACTION_DELAY)

    # 2: Open index finger
    if not execute_joint_positions(hand, open_index_finger, "Open index finger"):
        return False

    # 3: Open middle finger
    if not execute_joint_positions(hand, open_middle_finger, "Open middle finger"):
        return False

    # 4: Open ring finger
    if not execute_joint_positions(hand, open_ring_finger, "Open ring finger"):
        return False

    # 5: Open little finger
    if not execute_joint_positions(hand, open_little_finger, "Open little finger"):
        return False

    # 6: Open thumb (using preset gesture)
    if not execute_gesture(hand, GestureType.OPEN_HAND):
        logger.error("Open thumb action failed")
        return False
    time.sleep(ACTION_DELAY)

    return True


@handle_action_error("Index finger swing")
def swing_index_finger(hand):
    """Index finger swing action

    Action sequence:
    1. Initial pose
    2. Negative swing (-15 degrees)
    3. Positive swing (15 degrees)
    4. Repeat once
    5. Reset to initial pose

    Args:
        hand: GHand instance

    Returns:
        bool: True if action executed successfully, False otherwise
    """
    if not execute_joint_positions(hand, open_index_finger, "Initial pose"):
        return False

    for _ in range(2):
        if not execute_joint_positions(hand, index_finger_swing_neg, "Index finger negative swing"):
            return False

        if not execute_joint_positions(hand, index_finger_swing_pos, "Index finger positive swing"):
            return False

    if not execute_joint_positions(hand, open_index_finger, "Reset pose"):
        return False

    return True


@handle_action_error("Finger flexing")
def flex_finger_movement(hand, cycle_count=FLEX_CYCLE_COUNT):
    """Finger flexing action sequence

    Action sequence:
    1. Flex little finger
    2. Flex ring and little fingers
    3. Flex middle, ring and little fingers
    4. Flex all fingers
    5. Flex index, middle and ring fingers
    6. Flex index finger
    7. Flex middle finger
    8. Reset to zero position

    Args:
        hand: GHand instance
        cycle_count: Number of cycles, default 4

    Returns:
        bool: True if action executed successfully, False otherwise
    """
    for i in range(cycle_count):
        logger.info("Flex cycle %s started", i + 1)

        if not execute_joint_positions(hand, flex_little_finger, "Flex little finger"):
            return False

        if not execute_joint_positions(hand, flex_ring_and_little_fingers,
                                       "Flex ring and little fingers"):
            return False

        if not execute_joint_positions(hand, flex_middle_ring_little_fingers,
                                       "Flex middle, ring and little fingers"):
            return False

        if not execute_joint_positions(hand, flex_all_fingers, "Flex all fingers"):
            return False

        if not execute_joint_positions(hand, flex_index_middle_and_ring_fingers,
                                       "Flex index, middle and ring fingers"):
            return False

        if not execute_joint_positions(hand, flex_index_finger, "Flex index finger"):
            return False

        if not execute_joint_positions(hand, flex_middle_finger, "Flex middle finger"):
            return False

        # Reset to zero (using preset gesture)
        if not execute_gesture(hand, GestureType.OPEN_HAND):
            logger.error("Finger reset action failed")
            return False
        time.sleep(ACTION_DELAY)

    return True


@handle_action_error("OK gesture")
def make_ok(hand):
    """OK gesture (using preset gesture)

    Action:
    Thumb and index fingertips touch

    Args:
        hand: GHand instance

    Returns:
        bool: True if action executed successfully, False otherwise
    """
    if not execute_gesture(hand, GestureType.OK):
        logger.error("OK gesture failed")
        return False
    time.sleep(ACTION_DELAY)
    return True


@handle_action_error("First action group")
def first_action(hand):
    """First action group: thumb touch and fist then open

    Action sequence:
    1. Thumb sequentially touches other fingers
    2. Fist and open (repeat twice)

    Args:
        hand: GHand instance

    Returns:
        bool: True if action executed successfully, False otherwise
    """
    if not thumb_touch_tp(hand):
        return False

    for i in range(2):
        logger.info("Fist and open cycle %s", i + 1)
        if not fist_then_open(hand):
            return False

    return True


@handle_action_error("Second action group")
def second_action(hand, flex_cycles=FLEX_CYCLE_COUNT):
    """Second action group: sequential finger opening and swinging

    Action sequence:
    1. Sequential finger opening
    2. Index finger swing
    3. Finger flexing sequence (repeat specified times)
    4. OK gesture

    Args:
        hand: GHand instance
        flex_cycles: Finger flexing cycle count, default 4

    Returns:
        bool: True if action executed successfully, False otherwise
    """
    if not seq_open_finger(hand):
        return False

    if not swing_index_finger(hand):
        return False

    for i in range(flex_cycles):
        logger.info("Finger flexing cycle %s", i + 1)
        if not flex_finger_movement(hand, cycle_count=1):
            return False

    if not make_ok(hand):
        return False

    return True


def main():
    logger.info("***** GHand SDK - Gesture Dance Demo *****")
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")

    try:
        if not connected:
            logger.error("[Scan complete] Failed to connect to dexterous hand.")
            return

        logger.info("\n--- Device ready, starting gesture dance demo ---")

        # Loop through gesture actions
        gesture_cycle = 0
        max_cycles = 0  # Set cycle count, 0 means infinite loop

        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break

            logger.info("\n--- Cycle %s: Gesture demo started ---", gesture_cycle)

            if not first_action(hand):
                logger.error("First action group failed in cycle %s", gesture_cycle)
                break

            if not second_action(hand):
                logger.error("Second action group failed in cycle %s", gesture_cycle)
                break

            logger.info("--- Cycle %s: Gesture demo ended ---", gesture_cycle)

            # Prompt
            if max_cycles == 0:
                logger.info("Press Ctrl+C to stop demo and exit program")

    except KeyboardInterrupt:
        logger.info("\n\nProgram interrupted by user.")
    except Exception as e:
        logger.error("\n[Critical Error] %s", e)
    finally:
        hand.close()
        time.sleep(0.5)
        logger.info("\n--- Demo ended, disconnected ---")


if __name__ == "__main__":
    main()
