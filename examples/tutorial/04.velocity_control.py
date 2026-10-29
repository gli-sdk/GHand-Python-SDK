# Mode notes
# 1. velocity is the signed target velocity (%, -100..100) and current is the current
#    limit (%). ±100% velocity with a 100% current limit is full-scale; reduce them for
#    the actual load when tuning.
# 2. Velocity control has no target angle; a negative velocity means reverse motion,
#    not a stop command. sleep(2) is only a delay, not a guarantee the motion finished;
#    use stop() when you need to hold position.
# 3. Whole-hand VELOCITY mode uses velocity control with closed-loop for all joints;
#    loop_type only takes effect in CUSTOM.
#    If a joint reports DISABLED, first check the enable state and error feedback; do not
#    just increase velocity or current.
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
from ghand.ghand import CommType, HandControlMode, GHand, JointCommand, JointId

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)


def main():
    hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")

    try:
        if not connected:
            print("Connection failed")
            return

        print("\n=== velocity Control Mode Demo ===")
        print("This demo controls finger joints using velocity mode")
        print("velocity values control the continuous velocity of each joint\n")

        velocity_joint_ids = (
            JointId.THUMB_MCP,
            JointId.THUMB_TMC_FE,
            JointId.FF_PIP,
            JointId.FF_MCP,
            JointId.MF_PIP,
            JointId.MF_MCP,
            JointId.RF_PIP,
            JointId.RF_MCP,
            JointId.LF_PIP,
            JointId.LF_MCP,
        )

        # velocity control cycle
        cycle_count = 0
        max_cycles = 0  # Set to 0 for infinite loop

        while True:
            cycle_count += 1
            if max_cycles > 0 and cycle_count > max_cycles:
                break

            print(f"\n--- Cycle {cycle_count}: velocity control started ---")

            # Step 1: Move fingers at specified velocity
            print("\nStep 1: Closing fingers (velocity=100)")
            joints = []
            for joint_id in velocity_joint_ids:
                joints.append(JointCommand(id=joint_id, velocity=100, current=100))

            result = hand.move_joints(joints, hand_control_mode=HandControlMode.VELOCITY)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states:")
                for joint in current_joints:
                    print(
                        f"{JointId(joint.id).name:<13}-\tangle: {joint.angle:<3.1f}(deg),\tvelocity: {joint.velocity:<3},\tcurrent: {joint.current:<3}, \tcontrol_mode:{joint.control_mode}({(joint.control_mode).name:<7}),\tloop_type:{joint.loop_type}({(joint.loop_type).name:<15}),\tstate:{joint.state}({(joint.state).name:<8}),\terror:{joint.error}({(joint.error).name}),"
                    )
            else:
                print("Failed to send velocity command")
                break

            # Step 2: Stop movement (zero velocity)
            print("\nStep 2: Opening fingers (velocity=-100)")
            joints = []
            for joint_id in velocity_joint_ids:
                joints.append(JointCommand(id=joint_id, velocity=-100, current=100))

            result = hand.move_joints(joints, hand_control_mode=HandControlMode.VELOCITY)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states (stopped):")
                for joint in current_joints:
                    print(
                        f"{JointId(joint.id).name:<13}-\tangle: {joint.angle:<3.1f}(deg),\tvelocity: {joint.velocity:<3},\tcurrent: {joint.current:<3}, \tcontrol_mode:{joint.control_mode}({(joint.control_mode).name:<7}),\tloop_type:{joint.loop_type}({(joint.loop_type).name:<15}),\tstate:{joint.state}({(joint.state).name:<8}),\terror:{joint.error}({(joint.error).name}),"
                    )
            else:
                print("Failed to send velocity command")
                break

            print(f"\n--- Cycle {cycle_count}: velocity control completed ---")
            if max_cycles == 0:
                print("Press Ctrl+C to stop the demo and exit\n")
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n=== Demo ended, disconnected ===")


if __name__ == "__main__":
    main()
