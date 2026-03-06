import time
import math
import logging
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId
from xiaoyao.error import State, ErrorCode
from xiaoyao import configure_logging

# Configure SDK logging (shows connection status, warnings, errors)
configure_logging(level=logging.INFO)

def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, "auto")

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
            joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(30), speed=100, torque=100))
            joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(30), speed=100, torque=100))

            result = hand.move_joints(joints)
            if result:
                time.sleep(2)  # Wait for movement to complete
                # Display current joint states
                current_joints = hand.get_joints()
                for joint in current_joints:
                    print(
                        f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\terror:{ErrorCode(joint.error).name},\tangle: {math.degrees(joint.angle):.2f}°,\tspeed: {joint.speed},\ttorque: {joint.torque}"
                    )
            else:
                break

            # Configure joint angles for gesture 2 (reset position)
            joints = []
            joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(0), speed=100, torque=100))
            joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(0), speed=100, torque=100))

            result = hand.move_joints(joints)
            if result:
                time.sleep(2)  # Wait for movement to complete

                # Display current joint states
                # Note: get_joints() may raise exceptions - will be caught by outer exception handler
                current_joints = hand.get_joints()
                for joint in current_joints:
                    print(
                        f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\terror:{ErrorCode(joint.error).name},\tangle: {math.degrees(joint.angle):.2f}°,\tspeed: {joint.speed},\ttorque: {joint.torque}"
                    )
            else:
                break

            print(f"--- Cycle {gesture_cycle}: Finger movement completed ---\n")
            # Prompt
            if max_cycles == 0:
                print("Press Ctrl+C to stop the demo and exit\n")

    except KeyboardInterrupt:
        hand.close()
        print("\nProgram interrupted by user.")
    except Exception as e:
        print(f"[Fatal Error] {e}")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n--- Demo ended, disconnected ---")

if __name__ == "__main__":
    main()
