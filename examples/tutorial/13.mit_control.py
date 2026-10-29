"""MIT control: move the index MCP joint to two target angles."""

# Mode notes
# 1. Whole-hand MIT (mode=3) parses every active joint in MIT mode and is not subject to
#    the CUSTOM in-group mode consistency rule. Joint loop_type only takes effect in
#    CUSTOM; other whole-hand modes use closed-loop by default.
# 2. Even after the whole hand allows motion, each joint's control_state still decides
#    execution: 0 disabled, 1 running, 2 stopped/holding.
#    Whole-hand disabled takes priority over joint commands; a communication loss also
#    leaves all joints idle.
# MIT parameter conventions in the SDK: angle in degrees, velocity/current in %;
# kp=10-2000, kd=0-50, and kp>kd; suggested |velocity|<=5%, |current|<=20%; tune the
# gains for the actual load.
# move_joints() returning success means the command was sent; judge actual execution
# from the whole-hand and joint state feedback.

# MIT velocity/current are target velocity/feedforward current, not limits; zero
# feedforward does not mean the motor is disabled.
# move_joints() returning success only means the command was sent; confirm execution
# with get_hand_info() and get_joints().
# control_state: DISABLED (motor off), RUNNING, STOPPED (holding); whole-hand disabled
# takes priority.
# close() only shuts down the communication link; it does not call stop() or
# disable_hand(). To stop holding or release drive torque, explicitly send the
# corresponding command and confirm the feedback before closing.

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
        for angle, current in ((30.0, 5), (0.0, -10)):
            command = JointCommand(
                id=JointId.MF_MCP,
                angle=angle,
                # MIT velocity/current are targets, not motion limits.
                # Zero feedforward lets position feedback drive both directions.
                velocity=0,
                current=current,
                kp=10,
                kd=0,
            )
            # Whole-hand MIT mode selects MIT for every commanded joint.
            if not hand.move_joints([command], hand_control_mode=HandControlMode.MIT):
                print("Failed to send MIT command")
                return
            time.sleep(2)
            print(f"Hand status: {hand.get_hand_info()}")
            for joint in hand.get_joints():
                if joint.id == JointId.MF_MCP:
                    print(
                        f"{JointId(joint.id).name:<13}-\tangle: {joint.angle:<3.1f}(deg),\tvelocity: {joint.velocity:<3},\tcurrent: {joint.current:<3}, \tcontrol_mode:{joint.control_mode}({(joint.control_mode).name:<7}),\tloop_type:{joint.loop_type}({(joint.loop_type).name:<15}),\tstate:{joint.state}({(joint.state).name:<8}),\terror:{joint.error}({(joint.error).name}),"
                    )
    except KeyboardInterrupt:
        print("Demo interrupted")
    finally:
        if hand.is_connected():
            hand.disable_hand()
        hand.close()
        print("\n=== Demo ended, disconnected ===")


if __name__ == "__main__":
    main()
