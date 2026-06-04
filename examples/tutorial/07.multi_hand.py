"""
Example: Control multiple dexterous hands simultaneously.

This script discovers all available CANFD adapters, connects to each device,
performs simple movements, reads joint states, and closes all connections.
"""

import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand, JointCommand, JointId

# Configure SDK logging
configure_logging(level=logging.INFO)


def main():
    # Step 1: Discover available adapters
    print("Searching for devices...")
    scout = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    adapters = scout.search_adapters()
    print(f"Found {len(adapters)} adapter(s)")

    if not adapters:
        print("No adapters found")
        return

    # Step 2: Connect to all devices
    hands = []
    for i, adapter in enumerate(adapters):
        hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
        try:
            if hand.open(adapter):
                hands.append(hand)
                print(f"  hand_{i}: {hand.get_device_name()} connected")
            else:
                print(f"  hand_{i}: connection failed")
                hand.close()
        except Exception as e:
            print(f"  hand_{i}: error - {e}")
            hand.close()

    if not hands:
        print("No devices connected")
        return

    print(f"\nConnected {len(hands)} device(s)")

    # Step 3: Get device info
    for i, hand in enumerate(hands):
        print(
            f"  hand_{i}: {hand.get_device_name()} "
            f"({hand.get_hand_type().value}, SN: {hand.get_serial_number()})"
        )

    # Step 4: Control each hand individually
    print("\n=== Individual control ===")
    test_joints = [
        JointCommand(id=JointId.THUMB_PIP, angle=30, speed=100, torque=100),
        JointCommand(id=JointId.FF_PIP, angle=45, speed=100, torque=100),
        JointCommand(id=JointId.FF_MCP, angle=30, speed=100, torque=100),
    ]

    for i, hand in enumerate(hands):
        print(f"Controlling hand_{i}...")
        if hand.move_joints(test_joints):
            print("  Command sent successfully")
            time.sleep(1)
            joints = hand.get_joints()
            print(f"  Current joint count: {len(joints)}")
        else:
            print("  Command failed")

    # Step 5: Control all hands simultaneously
    print("\n=== Simultaneous control ===")
    reset_joints = [
        JointCommand(id=JointId.THUMB_PIP, angle=0, speed=100, torque=100),
        JointCommand(id=JointId.FF_PIP, angle=0, speed=100, torque=100),
        JointCommand(id=JointId.FF_MCP, angle=0, speed=100, torque=100),
    ]

    for i, hand in enumerate(hands):
        print(f"Sending reset to hand_{i}...")
        hand.move_joints(reset_joints)
    time.sleep(1)

    # Step 6: Read joint states for all hands
    print("\n=== Joint states ===")
    for i, hand in enumerate(hands):
        joints = hand.get_joints()
        print(f"\nhand_{i}: {len(joints)} joints")
        for joint in joints:
            print(
                f"  {JointId(joint.id).name:<15}"
                f"angle: {joint.angle:.2f} deg, "
                f"speed: {joint.speed}, torque: {joint.torque}"
            )

    # Step 7: Close all connections
    print("\nClosing all connections...")
    for i, hand in enumerate(hands):
        hand.close()
        print(f"  hand_{i} closed")

    print("Done")


if __name__ == "__main__":
    main()
