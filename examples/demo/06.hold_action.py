import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand, JointCommand, JointId

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)

hold_tightly = {
    JointId.THUMB_PIP: 10,
    JointId.THUMB_MCP: 25,
    JointId.THUMB_SWING: 30,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 70,
    JointId.FF_MCP: 65,
    JointId.FF_SWING: 0,
    JointId.MF_PIP: 70,
    JointId.MF_MCP: 65,
    JointId.RF_PIP: 70,
    JointId.RF_MCP: 60,
    JointId.LF_PIP: 70,
    JointId.LF_MCP: 65,
}

hold_loosely = {
    JointId.THUMB_PIP: 10,
    JointId.THUMB_MCP: 25,
    JointId.THUMB_SWING: 30,
    JointId.THUMB_ROTATION: 0,
    JointId.FF_PIP: 40,
    JointId.FF_MCP: 35,
    JointId.FF_SWING: 40,
    JointId.MF_PIP: 35,
    JointId.MF_MCP: 40,
    JointId.RF_PIP: 35,
    JointId.RF_MCP: 40,
    JointId.LF_PIP: 40,
    JointId.LF_MCP: 35,
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


def hold(hand):
    joints = [JointCommand(id=joint_id, angle=angle, speed=100, torque=100) for joint_id, angle in hold_tightly.items()]
    result = hand.move_joints(joints)
    return result


def hand_zero(hand):
    joints = [JointCommand(id=joint_id, angle=angle, speed=100, torque=100) for joint_id, angle in open_hand.items()]
    result = hand.move_joints(joints)
    return result


def main():
    print("***** GHand SDK - Hold Demo *****\n")
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")
    try:
        if not connected:
            print("\n[Scan complete] Failed to connect to dexterous hand.")
            return
        print("\n--- Device ready, starting hold demo ---\n")

        # Loop through gesture actions
        gesture_cycle = 0
        max_cycles = 0  # Set cycle count, 0 means infinite loop

        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break

            print(f"\n--- Cycle {gesture_cycle}: Demo started ---")

            if not hold(hand):
                print(f"Cycle {gesture_cycle}: Hold action failed")
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
