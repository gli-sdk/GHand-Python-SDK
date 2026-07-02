"""
Example: Connecting two dexterous hands

Now that EthercatClient has removed the singleton pattern, you can directly
create multiple GHand instances to connect to multiple devices.
"""

import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand, JointCommand, JointId

# Configure SDK logging
configure_logging(level=logging.INFO)


def main():
    """Connect and control two dexterous hands"""

    # Create and connect first hand
    print("Connecting first dexterous hand...")
    hand1 = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    connected1 = hand1.open("\\Device\\NPF_{B1A930DF-53B0-483A-ABB8-6C3146F1FC2D}")
    if not connected1:
        print("First hand connection failed")
        return

        # Create and connect second hand
    print("Connecting second dexterous hand...")
    hand2 = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    connected2 = hand2.open("\\Device\\NPF_{5539C758-F9F9-482D-B319-1760CE5958A6}")
    if not connected2:
        print("Second hand connection failed")
        hand1.close()
        return

    # logger.info("Two dexterous hands connected successfully!")

    # Get info for first hand
    try:
        ver1 = hand1.get_firmware_version()
        name1 = hand1.get_device_name()
        hw_ver1 = hand1.get_hardware_version()
        serial1 = hand1.get_serial_number()
        type1 = hand1.get_hand_type()
        print(f"First hand - Name: {name1}, HW: {hw_ver1}, "
              f"FW: {ver1}, Type: {type1.value}, "
              f"SN: {serial1}")
    except Exception as e:
        print(f"Failed to get first hand info: {e}")

    # Get info for second hand
    try:
        ver2 = hand2.get_firmware_version()
        name2 = hand2.get_device_name()
        hw_ver2 = hand2.get_hardware_version()
        serial2 = hand2.get_serial_number()
        type2 = hand2.get_hand_type()
        print(f"Second hand - Name: {name2}, HW: {hw_ver2}, "
              f"FW: {ver2}, Type: {type2.value}, "
              f"SN: {serial2}")
    except Exception as e:
        print(f"Failed to get second hand info: {e}")

    print("Dexterous hands ready, control operations can begin")

    # Add your control logic here...
    # For example:
    # hand1.move_joints([...])
    # hand2.move_joints([...])
    joints1 = []

    joints1.append(JointCommand(id=JointId.THUMB_MCP, angle=0, speed=100,
                                torque=100))  # Angle range: 0~75 (degrees)
    joints1.append(JointCommand(id=JointId.THUMB_TMC_FE, angle=50, speed=100,
                                torque=100))  # Angle range: 0~55 (degrees)
    joints1.append(JointCommand(id=JointId.THUMB_TMC_AA, angle=20, speed=100,
                                torque=100))  # Angle range: 0~90 (degrees)
    joints1.append(JointCommand(id=JointId.THUMB_TMC_PS, angle=0, speed=100,
                                torque=100))  # Angle range: 0~90 (degrees)
    joints1.append(JointCommand(id=JointId.FF_PIP, angle=0, speed=100,
                                torque=100))  # Angle range: 0~75 (degrees)
    joints1.append(JointCommand(id=JointId.FF_MCP, angle=0, speed=100,
                                torque=100))  # Angle range: 0~70 (degrees)

    result = hand1.move_joints(joints1)
    if result:
        print("Command 1 sent successfully")
        time.sleep(0.7)
        current_joints = hand1.get_joints()
        if current_joints:
            joint = current_joints[2]
            print(
                f"  {JointId(joint.id).name:<15}- Angle: {joint.angle:.2f} deg,\tSpeed: {joint.speed},\tTorque: {joint.torque}"
            )

    joints1.append(JointCommand(id=JointId.THUMB_MCP, angle=0, speed=100,
                                torque=100))  # Angle range: 0~75 (degrees)
    joints1.append(JointCommand(id=JointId.THUMB_TMC_FE, angle=0, speed=100,
                                torque=100))  # Angle range: 0~55 (degrees)
    joints1.append(JointCommand(id=JointId.THUMB_TMC_AA, angle=20, speed=100,
                                torque=100))  # Angle range: 0~90 (degrees)
    joints1.append(JointCommand(id=JointId.THUMB_TMC_PS, angle=0, speed=100,
                                torque=100))  # Angle range: 0~90 (degrees)
    joints1.append(JointCommand(id=JointId.FF_PIP, angle=50, speed=100,
                                torque=100))  # Angle range: 0~75 (degrees)
    joints1.append(JointCommand(id=JointId.FF_MCP, angle=50, speed=100,
                                torque=100))  # Angle range: 0~70 (degrees)

    result = hand2.move_joints(joints1)
    if result:
        print("Command 1 sent successfully")
        time.sleep(0.7)
        current_joints2 = hand2.get_joints()
        if current_joints2:
            joint = current_joints2[7]
            print(
                f"  {JointId(joint.id).name:<15}- Angle: {joint.angle:.2f} deg,\tSpeed: {joint.speed},\tTorque: {joint.torque}"
            )

    # Close connections when program ends
    # Note: Context managers can also be used for automatic closing
    print("Closing all connections...")
    hand1.close()
    hand2.close()
    print("Complete")


if __name__ == "__main__":
    main()
