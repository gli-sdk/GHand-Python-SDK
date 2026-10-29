"""CUSTOM control: select a control mode and feedback loop per joint."""

import logging
import time

from ghand import (
    CommType,
    GHand,
    HandControlMode,
    JointCommand,
    JointControlMode,
    JointControlState,
    JointId,
    JointLoopType,
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

        for angle in (15.0, 0.0):
            commands = [
                JointCommand(
                    id=JointId.FF_MCP,
                    control_mode=JointControlMode.POSITION,
                    loop_type=JointLoopType.CLOSED_LOOP,
                    control_state=JointControlState.RUNNING,
                    angle=angle,
                    velocity=10,
                    current=20,
                ),
                JointCommand(
                    id=JointId.MF_MCP,
                    control_mode=JointControlMode.MIT,
                    loop_type=JointLoopType.SEMI_CLOSED_LOOP,
                    control_state=JointControlState.RUNNING,
                    angle=angle,
                    velocity=0,
                    current=0,
                    kp=100,
                    kd=10,
                ),
            ]
            # CUSTOM preserves each joint's control_mode and loop_type.
            # Other whole-hand modes select one mode and force closed-loop control.
            # Angle: degrees; velocity/current: %; MIT requires kp > kd.
            if not hand.move_joints(commands, hand_control_mode=HandControlMode.CUSTOM):
                print("Failed to send CUSTOM command")
                return
            time.sleep(2)
            for joint in hand.get_joints():
                if joint.id in (JointId.FF_MCP, JointId.MF_MCP):
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
