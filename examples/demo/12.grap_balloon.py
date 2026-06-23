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
from ghand.types import ErrorCode, State

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.DEBUG)


def main():
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")

    try:
        if not connected:
            print("Connection failed")
            return

        print("\n=== Torque Control Mode Demo ===")

        # Torque control cycle
        cycle_count = 0
        max_cycles = 1  # Set to 0 for infinite loop

        while True:
            cycle_count += 1
            if max_cycles > 0 and cycle_count > max_cycles:
                break

            # Step 1: Apply torque to close fingers
            print("\nStep 1: Applying torque to close fingers (torque=10)")
            torque_joints = [
                JointCommand(id=JointId.THUMB_TMC_AA, torque=5),
                JointCommand(id=JointId.THUMB_MCP, torque=8),
                JointCommand(id=JointId.FF_PIP, torque=8),
                JointCommand(id=JointId.MF_PIP, torque=8),
            ]

            result = hand.move_joints(torque_joints, mode=CtrlMode.TORQUE)
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
                                f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\t"
                                f"error:{ErrorCode(joint.error).name},\t"
                                f"angle: {joint.angle:.2f}°,\t"
                                f"speed: {joint.speed},\ttorque: {joint.torque}")
            else:
                print("Failed to send torque command")
                break

    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n=== Demo ended, disconnected ===")


if __name__ == "__main__":
    main()
