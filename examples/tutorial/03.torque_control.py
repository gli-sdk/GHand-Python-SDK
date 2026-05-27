import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, CtrlMode, GHand, JointCommand, JointId
from ghand.types import ErrorCode, GHandError, HandStateError, State

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.DEBUG)


def main():
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.RS485)
    connected = hand.open("auto")

    try:
        if not connected:
            print("Connection failed")
            return

        print("\n=== Torque Control Mode Demo ===")
        print("This demo controls finger joints using torque mode")
        print("Torque values control the force applied by each joint\n")

        # Torque control cycle
        cycle_count = 0
        max_cycles = 0  # Set to 0 for infinite loop

        while True:
            cycle_count += 1
            if max_cycles > 0 and cycle_count > max_cycles:
                break

            print(f"\n--- Cycle {cycle_count}: Torque control started ---")

            # Step 1: Apply torque to close fingers
            print("\nStep 1: Applying torque to close fingers (torque=10)")
            joints = []
            for joint_id in [
                    # JointId.THUMB_PIP,
                    # JointId.THUMB_MCP,
                    JointId.FF_PIP,
                    # JointId.FF_MCP,
                    # JointId.MF_PIP,
                    # JointId.MF_MCP,
                    # JointId.RF_PIP,
                    # JointId.RF_MCP,
                    # JointId.LF_PIP,
                    # JointId.LF_MCP,
            ]:
                joints.append(JointCommand(id=joint_id, torque=-50))

            result = hand.move_joints(joints, mode=CtrlMode.TORQUE)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states:")
                for joint in current_joints:
                    if joint.id in [JointId.THUMB_PIP, JointId.FF_PIP, JointId.MF_PIP]:
                        print(f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\t"
                              f"error:{ErrorCode(joint.error).name},\t"
                              f"angle: {joint.angle:.2f}°,\t"
                              f"speed: {joint.speed},\ttorque: {joint.torque}")
            else:
                print("Failed to send torque command")
                break

            # Step 2: Release grip (zero torque)
            print("\nStep 2: Opening fingers (torque=-10)")
            joints = []
            for joint_id in [
                    # JointId.THUMB_PIP,
                    # JointId.THUMB_MCP,
                    JointId.FF_PIP,
                    # JointId.FF_MCP,
                    # JointId.MF_PIP,
                    # JointId.MF_MCP,
                    # JointId.RF_PIP,
                    # JointId.RF_MCP,
                    # JointId.LF_PIP,
                    # JointId.LF_MCP,
            ]:
                joints.append(JointCommand(id=joint_id, torque=-10))

            result = hand.move_joints(joints, mode=CtrlMode.TORQUE)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states (released):")
                for joint in current_joints:
                    if joint.id in [JointId.THUMB_PIP, JointId.FF_PIP, JointId.MF_PIP]:
                        print(f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\t"
                              f"error:{ErrorCode(joint.error).name},\t"
                              f"angle: {joint.angle:.2f}°,\t"
                              f"speed: {joint.speed},\ttorque: {joint.torque}")
            else:
                print("Failed to send torque command")
                break

            print(f"\n--- Cycle {cycle_count}: Torque control completed ---")
            if max_cycles == 0:
                print("Press Ctrl+C to stop the demo and exit\n")

    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    except HandStateError as e:
        print(f"\n[Hand State Error] {e}")
    except GHandError as e:
        print(f"\n[Unexpected Error] {type(e).__name__}: {e}")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n=== Demo ended, disconnected ===")


if __name__ == "__main__":
    main()
