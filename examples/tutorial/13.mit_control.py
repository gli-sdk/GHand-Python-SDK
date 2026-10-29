"""MIT control: move the index MCP joint to two target angles."""

import logging
import time

from ghand import (
    CommType,
    GHand,
    HandControlMode,
    JointCommand,
    JointControlState,
    JointId,
    ProductType,
    configure_logging,
)


def main():
    configure_logging(level=logging.INFO)
    # For CAN FD / RS485, change comm_type and use the adapter port in open().
    hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)
    try:
        if not hand.open("auto"):
            print("Connection failed")
            return

        # MIT combines target angle, velocity, feedforward current, and kp/kd.
        # Angle: degrees; velocity/current: %. Tune gains for the actual load.
        # Recommended MIT magnitudes: velocity <= 5%, current <= 20%.
        # kp: 10-2000; kd: 0-50; kp must be greater than kd.
        for angle in (15.0, 0.0):
            command = JointCommand(
                id=JointId.FF_MCP,
                angle=angle,
                velocity=0,
                current=0,
                kp=100,
                kd=10,
            )
            # Whole-hand MIT mode selects MIT for every commanded joint.
            if not hand.move_joints([command], hand_control_mode=HandControlMode.MIT):
                print("Failed to send MIT command")
                return
            time.sleep(2)
            for joint in hand.get_joints():
                if joint.id == JointId.FF_MCP:
                    print(
                        f"{JointId(joint.id).name:<13}-\tangle: {joint.angle:<3.1f}(deg),\tvelocity: {joint.velocity:<3},\tcurrent: {joint.current:<3}, \tcontrol_mode:{joint.control_mode}({(joint.control_mode).name:<7}),\tloop_type:{joint.loop_type}({(joint.loop_type).name:<15}),\tstate:{joint.state}({(joint.state).name:<8}),\terror:{joint.error}({(joint.error).name}),"
                    )
    except KeyboardInterrupt:
        print("Demo interrupted")
    finally:
        try:
            if hand.is_connected():
                hand.disable_hand()
        finally:
            hand.close()


if __name__ == "__main__":
    main()
