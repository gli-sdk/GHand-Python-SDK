import time
import math
import logging
from ghand.ghand import GHand, CommType, Joint, JointId, CtrlMode
from ghand.types import State, ErrorCode
from ghand import configure_logging
from ghand.types import (
    DeviceDisconnectedError,
    DeviceFaultError,
    JointFaultError,
    DataReceiveError
)

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)

def main():
    hand = GHand()
    connected = hand.open(CommType.ETHERCAT, "auto")

    try:
        if not connected:
            print("Connection failed")
            return

        print("\n=== Speed Control Mode Demo ===")
        print("This demo controls finger joints using speed mode")
        print("Speed values control the continuous velocity of each joint\n")

        # Speed control cycle
        cycle_count = 0
        max_cycles = 0  # Set to 0 for infinite loop

        while True:
            cycle_count += 1
            if max_cycles > 0 and cycle_count > max_cycles:
                break

            print(f"\n--- Cycle {cycle_count}: Speed control started ---")

            # Step 1: Move fingers at specified speed
            print("\nStep 1: Closing fingers (speed=100)")
            joints = []
            for joint_id in [JointId.THUMB_PIP, JointId.THUMB_MCP, JointId.FF_PIP,
                           JointId.FF_MCP, JointId.MF_PIP, JointId.MF_MCP,
                           JointId.RF_PIP, JointId.RF_MCP, JointId.LF_PIP, JointId.LF_MCP]:
                joints.append(
                    Joint(id=joint_id, speed=100, torque=100)
                )

            result = hand.move_joints(joints, mode=CtrlMode.SPEED)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states:")
                for joint in current_joints:
                    if joint.id in [JointId.THUMB_PIP, JointId.FF_PIP, JointId.MF_PIP]:
                        print(
                            f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\t"
                            f"error:{ErrorCode(joint.error).name},\t"
                            f"angle: {math.degrees(joint.angle):.2f}°,\t"
                            f"speed: {joint.speed},\ttorque: {joint.torque}"
                        )
            else:
                print("Failed to send speed command")
                break

            # Step 2: Stop movement (zero speed)
            print("\nStep 2: Opening fingers (speed=-100)")
            joints = []
            for joint_id in [JointId.THUMB_PIP, JointId.THUMB_MCP, JointId.FF_PIP,
                           JointId.FF_MCP, JointId.MF_PIP, JointId.MF_MCP,
                           JointId.RF_PIP, JointId.RF_MCP, JointId.LF_PIP, JointId.LF_MCP]:
                joints.append(Joint(id=joint_id, angle=0.0, speed=-100, torque=100))

            result = hand.move_joints(joints, mode=CtrlMode.SPEED)
            if result:
                time.sleep(2)
                current_joints = hand.get_joints()
                print("Current joint states (stopped):")
                for joint in current_joints:
                    if joint.id in [JointId.THUMB_PIP, JointId.FF_PIP, JointId.MF_PIP]:
                        print(
                            f"  {JointId(joint.id).name:<15}- state:{State(joint.state).name},\t"
                            f"error:{ErrorCode(joint.error).name},\t"
                            f"angle: {math.degrees(joint.angle):.2f}°,\t"
                            f"speed: {joint.speed},\ttorque: {joint.torque}"
                        )
            else:
                print("Failed to send speed command")
                break

            print(f"\n--- Cycle {cycle_count}: Speed control completed ---")
            if max_cycles == 0:
                print("Press Ctrl+C to stop the demo and exit\n")
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
