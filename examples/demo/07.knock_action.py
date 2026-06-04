import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand, JointCommand, JointId

# Configure logging output to console
configure_logging(level=logging.INFO)

logger = logging.getLogger("ghand")

konck_tightly = {
    JointId.THUMB_PIP: 60,
    JointId.THUMB_MCP: 0,
    JointId.THUMB_SWING: 20,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 75,
    JointId.FF_MCP: 0,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 75,
    JointId.MF_MCP: 0,
    JointId.RF_PIP: 75,
    JointId.RF_MCP: 70,
    JointId.LF_PIP: 74,
    JointId.LF_MCP: 70,
}

open_hand = {
    # All fingers at zero position
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
}


def hand_konck(hand):
    joints = [JointCommand(id=joint_id, angle=angle, speed=100, torque=100) for joint_id, angle in konck_tightly.items()]
    result = hand.move_joints(joints)
    return result


def hand_zero(hand):
    joints = [JointCommand(id=joint_id, angle=angle, speed=100, torque=100) for joint_id, angle in open_hand.items()]
    result = hand.move_joints(joints)
    return result


def main():
    print("***** GHand SDK - Knock Demo *****\n")
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")
    try:
        if not connected:
            print("\n[Scan complete] Failed to connect to dexterous hand.")
            return
        print("\n--- Device ready, starting knock demo ---\n")

        # Loop through gesture actions
        gesture_cycle = 0
        max_cycles = 0  # Set cycle count, 0 means infinite loop

        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break

            print(f"\n--- Cycle {gesture_cycle}: Demo started ---")

            if not hand_konck(hand):
                print(f"Cycle {gesture_cycle}: Knock action failed")
                break
            time.sleep(5)

            if not hand_zero(hand):
                print(f"Cycle {gesture_cycle}: Reset action failed")
                break
            time.sleep(5)

            print(f"--- Cycle {gesture_cycle}: Demo ended ---\n")

            # Prompt
            if max_cycles == 0:
                print("Press Ctrl+C to stop demo and exit program\n")
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user.")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n--- Demo ended, disconnected ---")


if __name__ == "__main__":
    main()
