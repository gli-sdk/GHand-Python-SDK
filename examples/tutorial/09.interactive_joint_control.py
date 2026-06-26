import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand, JointCommand, JointId

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)


def main():
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)

    # Create independent parameter dictionary for each joint
    joint_params = {
        JointId.THUMB_MCP: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.THUMB_TMC_FE: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.THUMB_TMC_AA: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.THUMB_TMC_PS: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.FF_PIP: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.FF_MCP: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.FF_MCP_AA: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.MF_PIP: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.MF_MCP: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.RF_PIP: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.RF_MCP: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.LF_PIP: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
        JointId.LF_MCP: {
            "angle": 0,
            "speed": 0,
            "torque": 0
        },
    }

    connected = hand.open("auto")
    if not connected:
        print("connect failed")
        return
    ver = hand.get_firmware_version()
    hand_name = hand.get_device_name()
    hand_hw_ver = hand.get_hardware_version()
    serial_num = hand.get_serial_number()
    hand_type = hand.get_hand_type()
    print(f"hand name:{hand_name};H/W ver:{hand_hw_ver};ver: {ver};hand_type: {hand_type.value};")
    print(f"Serial num:{serial_num};")

    try:
        while True:
            # Reset all joint parameters to default values at start of each loop
            for joint_id in joint_params:
                joint_params[joint_id]["angle"] = 0
                joint_params[joint_id]["speed"] = 0
                joint_params[joint_id]["torque"] = 0

            # Record joints that have been set
            set_joints = set()

            # Get user input
            print("\nSet parameters for joints (enter empty line to finish):")
            print("Joint ID list:")
            print("1:THUMB_MCP, 2:THUMB_TMC_FE, 3:THUMB_TMC_AA, 4:THUMB_TMC_PS")
            print("6:FF_PIP, 7:FF_MCP, 8:FF_MCP_AA")
            print("10:MF_PIP, 11:MF_MCP")
            print("13:RF_PIP, 14:RF_MCP")
            print("16:LF_PIP, 17:LF_MCP")

            try:
                while True:
                    # Display already set joints and their parameters
                    if set_joints:
                        print("Already set joints:")
                        for joint_id in set_joints:
                            params = joint_params[joint_id]
                            print(
                                f"  {JointId(joint_id).name}: angle={params['angle']}, speed={params['speed']}, torque={params['torque']}"
                            )

                    joint_input = input("Enter joint ID (or press Enter to finish): ").strip()
                    if not joint_input:
                        break

                    if joint_input.isdigit():
                        joint_id = int(joint_input)
                        if joint_id in joint_params:
                            set_joints.add(joint_id)
                            current_params = joint_params[joint_id]
                            print(f"Set parameters for joint {JointId(joint_id).name}:")
                            angle_input = input(
                                f"Angle value [{current_params['angle']}]: ").strip()
                            speed_input = input(
                                f"Speed value [{current_params['speed']}]: ").strip()
                            torque_input = input(
                                f"Torque value [{current_params['torque']}]: ").strip()

                            # Update parameters for selected joint
                            if angle_input:
                                joint_params[joint_id]["angle"] = float(angle_input)
                            if speed_input:
                                joint_params[joint_id]["speed"] = int(speed_input)
                            if torque_input:
                                joint_params[joint_id]["torque"] = int(torque_input)
                        else:
                            print("Invalid joint ID")
                    else:
                        print("Please enter a valid joint ID number")
            except ValueError:
                print("Input format error, skipping this setting")

            joints = []

            # Create Joint object for each joint
            for joint_id, params in joint_params.items():
                joints.append(
                    JointCommand(
                        id=joint_id,
                        angle=params["angle"],
                        speed=params["speed"],
                        torque=params["torque"],
                    ))

            result = hand.move_joints(joints)
            if result:
                hand.get_joints()
            else:
                break
    except KeyboardInterrupt:
        print("\nUser interrupted program, closing hand connection...")
    finally:
        hand.close()
        time.sleep(0.5)
        print("hand is closed")


if __name__ == "__main__":
    main()
