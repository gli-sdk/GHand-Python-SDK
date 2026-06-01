import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand, JointCommand, JointId
from ghand.types import ErrorCode, GHandError, HandStateError, State

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)


def main():
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    
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
            joints.append(JointCommand(id=JointId.THUMB_PIP, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.THUMB_MCP, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.THUMB_SWING, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.THUMB_ROTATION, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.FF_PIP, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.FF_MCP, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.FF_SWING, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.MF_PIP, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.MF_MCP, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.RF_PIP, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.RF_MCP, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.LF_PIP, angle=30, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.LF_MCP, angle=30, speed=100, torque=100))

            result = hand.move_joints(joints)
            if result:
                time.sleep(2)  # Wait for movement to complete
                # Display current joint states
                current_joints = hand.get_joints()
                for joint in current_joints:
                    print(
                        f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\terror:{ErrorCode(joint.error).name},\tangle: {joint.angle:.2f}°,\tspeed: {joint.speed},\ttorque: {joint.torque}"
                    )
            else:
                break

            # Configure joint angles for gesture 2 (reset position)
            joints = []
            joints.append(JointCommand(id=JointId.THUMB_PIP, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.THUMB_MCP, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.THUMB_SWING, angle=20, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.THUMB_ROTATION, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.FF_PIP, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.FF_MCP, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.FF_SWING, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.MF_PIP, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.MF_MCP, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.RF_PIP, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.RF_MCP, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.LF_PIP, angle=0, speed=100, torque=100))
            joints.append(JointCommand(id=JointId.LF_MCP, angle=0, speed=100, torque=100))

            result = hand.move_joints(joints)
            if result:
                time.sleep(2)  # Wait for movement to complete

                # Display current joint states
                # Note: get_joints() may raise exceptions - will be caught by outer exception handler
                current_joints = hand.get_joints()
                for joint in current_joints:
                    print(
                        f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\terror:{ErrorCode(joint.error).name},\tangle: {joint.angle:.2f}°,\tspeed: {joint.speed},\ttorque: {joint.torque}"
                    )
            else:
                break

            print(f"--- Cycle {gesture_cycle}: Finger movement completed ---\n")
            # Prompt
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
        print("\n--- Demo ended, disconnected ---")


if __name__ == "__main__":
    main()
