"""CUSTOM control: select a control mode and feedback loop per joint."""

# Mode notes (docs/协议/灵巧手EtherCAT通信协议V2.4.md §2.9, §2.10, §4.1):
# 1. Whole-hand CUSTOM (mode=0x0F) parses commands per joint from control_mode and
#    loop_type.
# 2. Within one finger's arbitration group, mode must be consistent; otherwise the whole
#    group's command is silently ignored: nothing executes, no error is reported, and the
#    motors keep the previous cycle's command. Configure consistent control_mode and
#    loop_type within a group.
#    Index: FF_PIP / FF_MCP / FF_MCP_AA; middle: MF_PIP / MF_MCP;
#    ring: RF_PIP / RF_MCP; little: LF_PIP / LF_MCP.
#    The four active thumb joints are independent and may mix modes per joint; whole-hand
#    mode=0..3 is not subject to this rule.
# 3. In position mode, velocity/current are velocity/current limits; motion or holding
#    commands should provide non-zero limits; when both are 0, the slave treats it as a
#    zero-torque stop, the motor is disabled, and the position is no longer held.
#    In current mode, current is the target current; angle is in degrees and
#    velocity/current are in %.
# 4. Even after the whole hand allows motion, each joint's control_state still decides
#    execution: 0 disabled, 1 running, 2 stopped/holding.
#    Consistent mode does not mean the joint is enabled; whole-hand disabled takes
#    priority over joint commands, and a communication loss leaves all joints idle.
# move_joints() returning success means the command was sent; judge actual execution
# from the whole-hand and joint state feedback.

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

        for angle, current in ((30.0, 30), (0.0, -30)):
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
                # Match the position/closed-loop mode of the index MCP too.
                JointCommand(
                    id=JointId.FF_PIP,
                    control_mode=JointControlMode.POSITION,
                    loop_type=JointLoopType.CLOSED_LOOP,
                    control_state=JointControlState.RUNNING,
                    angle=0,
                    velocity=10,
                    current=20,
                ),
                JointCommand(
                    id=JointId.FF_MCP_AA,
                    control_mode=JointControlMode.POSITION,
                    loop_type=JointLoopType.CLOSED_LOOP,
                    control_state=JointControlState.RUNNING,
                    angle=0,
                    velocity=10,
                    current=20,
                ),
                JointCommand(
                    id=JointId.MF_MCP,
                    control_mode=JointControlMode.CURRENT,
                    loop_type=JointLoopType.CLOSED_LOOP,
                    control_state=JointControlState.RUNNING,
                    current=current,
                ),
                # CUSTOM requires the same mode for MCP and PIP in this finger.
                # Keep PIP disabled while selecting CURRENT for the whole group.
                JointCommand(
                    id=JointId.MF_PIP,
                    control_mode=JointControlMode.CURRENT,
                    loop_type=JointLoopType.CLOSED_LOOP,
                    control_state=JointControlState.DISABLED,
                ),
            ]
            # CUSTOM preserves each joint's control_mode and loop_type.
            # Other whole-hand modes select one mode and force closed-loop control.
            # Angle: degrees; velocity/current: %; MIT requires kp > kd.
            if not hand.move_joints(commands, hand_control_mode=HandControlMode.CUSTOM):
                print("Failed to send CUSTOM command")
                return
            time.sleep(2)
            print(f"Hand status: {hand.get_hand_info()}")
            for joint in hand.get_joints():
                if joint.id in (JointId.FF_MCP, JointId.MF_MCP):
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
