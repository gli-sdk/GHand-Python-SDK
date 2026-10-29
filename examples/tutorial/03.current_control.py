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

        print("\n=== current control Mode Demo ===")
        print("This demo controls finger joints using current mode")
        print("Current values control the force applied by each joint\n")

        current_joint_ids = (
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

        # current control cycle
        cycle_count = 0
        max_cycles = 0  # Set to 0 for infinite loop

        while True:
            cycle_count += 1
            if max_cycles > 0 and cycle_count > max_cycles:
                break

            print(f"\n--- Cycle {cycle_count}: current control started ---")

            # Step 1: Apply current to close fingers
            print("\nStep 1: Applying current to close fingers (current=10)")
            joints = []
            for joint_id in current_joint_ids:
                joints.append(JointCommand(id=joint_id, current=10))

            result = hand.move_joints(joints, hand_control_mode=HandControlMode.CURRENT)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states:")
                for joint in current_joints:
                    if joint.id in [JointId.THUMB_MCP, JointId.FF_PIP, JointId.MF_PIP]:
                        print(
                            f"{JointId(joint.id).name:<13}-\tangle: {joint.angle:<3.1f}(deg),\tvelocity: {joint.velocity:<3},\tcurrent: {joint.current:<3}, \tcontrol_mode:{joint.control_mode}({(joint.control_mode).name:<7}),\tloop_type:{joint.loop_type}({(joint.loop_type).name:<15}),\tstate:{joint.state}({(joint.state).name:<8}),\terror:{joint.error}({(joint.error).name}),"
                        )
            else:
                print("Failed to send current command")
                break

            # Step 2: Release grip (zero current)
            print("\nStep 2: Opening fingers (current=-10)")
            joints = []
            for joint_id in current_joint_ids:
                joints.append(JointCommand(id=joint_id, current=-10))

            result = hand.move_joints(joints, hand_control_mode=HandControlMode.CURRENT)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states (released):")
                for joint in current_joints:
                    if joint.id in [JointId.THUMB_MCP, JointId.FF_PIP, JointId.MF_PIP]:
                        print(
                            f"{JointId(joint.id).name:<13}-\tangle: {joint.angle:<3.1f}(deg),\tvelocity: {joint.velocity:<3},\tcurrent: {joint.current:<3}, \tcontrol_mode:{joint.control_mode}({(joint.control_mode).name:<7}),\tloop_type:{joint.loop_type}({(joint.loop_type).name:<15}),\tstate:{joint.state}({(joint.state).name:<8}),\terror:{joint.error}({(joint.error).name}),"
                        )
            else:
                print("Failed to send current command")
                break

            print(f"\n--- Cycle {cycle_count}: current control completed ---")
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
