import logging
import time

from ghand import (
    ProductType,
    CommType,
    CtrlMode,
    GestureType,
    GHand,
    JointCommand,
    JointId,
    configure_logging,
    execute_gesture,
)

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.DEBUG)


def main():
    hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")

    try:
        if not connected:
            print("Connection failed")
            return

        print("\n=== current control Mode Demo ===")

        # current control cycle
        cycle_count = 0
        max_cycles = 1  # Set to 0 for infinite loop

        while True:
            cycle_count += 1
            if max_cycles > 0 and cycle_count > max_cycles:
                break

            # Step 1: Apply current to close fingers
            print("\nStep 1: Applying current to close fingers (current=10)")
            current_joints = [
                JointCommand(id=JointId.THUMB_TMC_AA, current=5),
                JointCommand(id=JointId.THUMB_MCP, current=8),
                JointCommand(id=JointId.FF_PIP, current=8),
                JointCommand(id=JointId.MF_PIP, current=8),
            ]

            result = hand.move_joints(current_joints, mode=CtrlMode.CURRENT)
            if result:
                while True:
                    time.sleep(10)
                    current_joints = hand.get_joints()
                    print("Current joint states:")
                    for joint in current_joints:
                        if joint.id in [
                                JointId.THUMB_TMC_AA,
                                JointId.THUMB_MCP,
                                JointId.FF_PIP,
                                JointId.MF_PIP,
                        ]:
                            print(
                                f"  {JointId(joint.id).name:<15}- state:{joint.state:<22},\t"
                                f"error:{joint.error:<30},\t"
                                f"angle: {joint.angle:.2f}deg,\t"
                                f"speed: {joint.speed},\tcurrent: {joint.current}")
            else:
                print("Failed to send current command")
                break

    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n=== Demo ended, disconnected ===")


if __name__ == "__main__":
    main()
