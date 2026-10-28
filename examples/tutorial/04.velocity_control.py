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
            for joint_id in [
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
            ]:
                joints.append(JointCommand(id=joint_id, velocity=100, current=100))

            result = hand.move_joints(joints, mode=HandControlMode.VELOCITY)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states:")
                for joint in current_joints:
                    if joint.id in [JointId.THUMB_MCP, JointId.FF_PIP, JointId.MF_PIP]:
                        print(f"  {JointId(joint.id).name:<15}- state:{joint.state:<22},\t"
                              f"error:{joint.error:<30},\t"
                              f"angle: {joint.angle:.2f}deg,\t"
                              f"velocity: {joint.velocity},\tcurrent: {joint.current}")
            else:
                print("Failed to send velocity command")
                break

            # Step 2: Stop movement (zero velocity)
            print("\nStep 2: Opening fingers (velocity=-100)")
            joints = []
            for joint_id in [
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
            ]:
                joints.append(JointCommand(id=joint_id, velocity=-100, current=100))

            result = hand.move_joints(joints, mode=HandControlMode.VELOCITY)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states (stopped):")
                for joint in current_joints:
                    if joint.id in [JointId.THUMB_MCP, JointId.FF_PIP, JointId.MF_PIP]:
                        print(f"  {JointId(joint.id).name:<15}- state:{joint.state:<22},\t"
                              f"error:{joint.error:<30},\t"
                              f"angle: {joint.angle:.2f}deg,\t"
                              f"velocity: {joint.velocity},\tcurrent: {joint.current}")
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
