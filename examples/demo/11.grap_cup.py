import time
import math
import logging
from ghand import DexHand, CommType, Joint, JointId, CtrlMode,GestureType,execute_gesture
from ghand.types import State, ErrorCode
from ghand import configure_logging
from ghand.types import (
    DeviceDisconnectedError,
    DeviceFaultError,
    JointFaultError,
    DataReceiveError
)

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.DEBUG)

def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, "auto")

    try:
        if not connected:
            print("Connection failed")
            return

        print("\n=== Torque Control Mode Demo ===")

        # Torque control cycle
        cycle_count = 0
        max_cycles = 1 # Set to 0 for infinite loop

        while True:
            cycle_count += 1
            if max_cycles > 0 and cycle_count > max_cycles:
                break

            joints = []
            joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(36), speed=50, torque=100))
            joints.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(70), speed=50, torque=100))
            joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(10), speed=50, torque=100))
            joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(51), speed=50, torque=100))
            joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(46), speed=50, torque=100))
            joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(40), speed=50, torque=100))

            result = hand.move_joints(joints)
            if result:
                time.sleep(2)  # Wait for movement to complete

            print(f"\n--- Cycle {cycle_count}: Torque control started ---")

            # Step 1: Apply torque to close fingers
            print("\nStep 1: Applying torque to close fingers (torque=10)")
            torque_joints = [
                Joint(id=JointId.THUMB_SWING, torque=5),
                Joint(id=JointId.THUMB_PIP, torque=8),
                Joint(id=JointId.FF_PIP, torque=8),
                Joint(id=JointId.MF_PIP, torque=8),
            ]

            result = hand.move_joints(torque_joints, mode=CtrlMode.TORQUE)
            if result:
                while True:
                    time.sleep(2)
                    current_joints = hand.get_joints()
                    print("Current joint states:")
                    for joint in current_joints:
                        if joint.id in [
                            JointId.THUMB_SWING,
                            JointId.THUMB_PIP,
                            JointId.FF_PIP,
                            JointId.MF_PIP
                        ]:
                            print(
                                f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\t"
                                f"error:{ErrorCode(joint.error).name},\t"
                                f"angle: {math.degrees(joint.angle):.2f}°,\t"
                                f"speed: {joint.speed},\ttorque: {joint.torque}"
                            )
            else:
                print("Failed to send torque command")
                break
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    except DeviceDisconnectedError as e:
        print(f"\n[Device Disconnected] {e.message}")
        if e.reason:
            print(f"Reason: {e.reason}")
    except JointFaultError as e:
        print(f"\n[Joint Fault] {e.message}")
        if e.faulty_joints:
            print("Faulty joints:")
            for joint in e.faulty_joints:
                print(f"  - {joint.joint_id}: state={joint.state.name}, error={joint.error_code.name}")
    except DeviceFaultError as e:
        print(f"\n[Device Fault] {e.message}")
        if e.fault_info:
            print(f"Details: {e.fault_info}")
    except DataReceiveError as e:
        print(f"\n[Data Receive Error] {e.message}")
        if e.expected_length is not None and e.actual_length is not None:
            print(f"Expected {e.expected_length} bytes, got {e.actual_length} bytes")
    except Exception as e:
        print(f"\n[Unexpected Error] {type(e).__name__}: {e}")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n=== Demo ended, disconnected ===")

if __name__ == "__main__":
    main()
