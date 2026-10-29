# Mode notes
# 1. angle is in degrees; velocity/current are velocity/current limits (%) — not target
#    velocity/current. Motion and holding commands must provide non-zero limits;
#    setting both to 0 disables the motor, so the position is no longer held.
# 2. Whole-hand POSITION mode uses position control with closed-loop for all joints;
#    loop_type only takes effect in CUSTOM.
# 3. sleep(2) is only a delay, not a guarantee the motion finished; judge the result
#    from the angle, state, and error feedback.
# move_joints() returning success only means the command was sent; confirm execution
# with get_hand_info() and get_joints().
# control_state: DISABLED (motor off), RUNNING, STOPPED (holding); whole-hand disabled
# takes priority.
# close() only shuts down the communication link; it does not call stop() or
# disable_hand(). To stop holding or release drive torque, explicitly send the
# corresponding command and confirm the feedback before closing.

import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand, JointCommand, JointId

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)


def main():
    hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)

    connected = hand.open("auto")

    try:
        if not connected:
            print("Connection failed")
            return
        joints = []

        # Loop through finger gestures
        gesture_cycle = 0
        max_cycles = 0  # Set cycle count, 0 means infinite loop

        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break

            print(f"\n--- Cycle {gesture_cycle}: Finger movement started ---")

            # Configure joint angles for gesture 1
            joints = []
            joints.append(JointCommand(id=JointId.THUMB_MCP, angle=30, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.THUMB_TMC_FE, angle=30, velocity=100,
                                       current=100))
            joints.append(JointCommand(id=JointId.THUMB_TMC_AA, angle=30, velocity=100,
                                       current=100))
            joints.append(JointCommand(id=JointId.THUMB_TMC_PS, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.FF_PIP, angle=30, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.FF_MCP, angle=30, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.FF_MCP_AA, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.MF_PIP, angle=30, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.MF_MCP, angle=30, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.RF_PIP, angle=30, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.RF_MCP, angle=30, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.LF_PIP, angle=30, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.LF_MCP, angle=30, velocity=100, current=100))

            result = hand.move_joints(joints)
            if result:
                time.sleep(2)  # Wait for movement to complete
                # Display current joint states
                current_joints = hand.get_joints()
                for joint in current_joints:
                    print(
                        f"{JointId(joint.id).name:<13}-\tangle: {joint.angle:<3.1f}(deg),\tvelocity: {joint.velocity:<3},\tcurrent: {joint.current:<3}, \tcontrol_mode:{joint.control_mode}({(joint.control_mode).name:<7}),\tloop_type:{joint.loop_type}({(joint.loop_type).name:<15}),\tstate:{joint.state}({(joint.state).name:<8}),\terror:{joint.error}({(joint.error).name}),"
                    )
            else:
                break

            # Configure joint angles for gesture 2 (reset position)
            joints = []
            joints.append(JointCommand(id=JointId.THUMB_MCP, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.THUMB_TMC_FE, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.THUMB_TMC_AA, angle=20, velocity=100,
                                       current=100))
            joints.append(JointCommand(id=JointId.THUMB_TMC_PS, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.FF_PIP, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.FF_MCP, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.FF_MCP_AA, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.MF_PIP, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.MF_MCP, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.RF_PIP, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.RF_MCP, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.LF_PIP, angle=0, velocity=100, current=100))
            joints.append(JointCommand(id=JointId.LF_MCP, angle=0, velocity=100, current=100))

            result = hand.move_joints(joints)
            if result:
                time.sleep(2)  # Wait for movement to complete

                # Display current joint states
                # Note: get_joints() may raise exceptions - will be caught by outer exception handler
                current_joints = hand.get_joints()
                for joint in current_joints:
                    print(
                        f"{JointId(joint.id).name:<13}-\tangle: {joint.angle:<3.1f}(deg),\tvelocity: {joint.velocity:<3},\tcurrent: {joint.current:<3}, \tcontrol_mode:{joint.control_mode}({(joint.control_mode).name:<7}),\tloop_type:{joint.loop_type}({(joint.loop_type).name:<15}),\tstate:{joint.state}({(joint.state).name:<8}),\terror:{joint.error}({(joint.error).name}),"
                    )
            else:
                break

            print(f"--- Cycle {gesture_cycle}: Finger movement completed ---\n")
            # Prompt
            if max_cycles == 0:
                print("Press Ctrl+C to stop the demo and exit\n")

    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n--- Demo ended, disconnected ---")


if __name__ == "__main__":
    main()
