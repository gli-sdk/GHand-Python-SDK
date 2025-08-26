import time
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId


def get_temprature(data):
    return data["temp"]


def process_data(data):
    temp = get_temprature(data)
    print(temp)
    for key in ["thumb1", "thumb2"]:
        print(f"{key}: {data[key]}")


def main():
    hand = DexHand()


    joints = []
    
    # # 拇指关节
    # joints.append(Joint(id=JointId.THUMB_PIP, angle=1.1, speed=5000.0, torque=90.0))
    # joints.append(Joint(id=JointId.THUMB_MCP, angle=1.1, speed=5000.0, torque=90.0))
    # joints.append(Joint(id=JointId.THUMB_SWING, angle=1.1, speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=1.1, speed=5000.0, torque=90.0))
    
    # # 食指关节
    # joints.append(Joint(id=JointId.FF_PIP, angle=1.1, speed=5000.0, torque=90.0))
    # joints.append(Joint(id=JointId.FF_MCP, angle=1.1, speed=5000.0, torque=90.0))
    # joints.append(Joint(id=JointId.FF_SWING, angle=1.1, speed=5000.0, torque=90.0))
    
    # # 中指关节
    # joints.append(Joint(id=JointId.MF_PIP, angle=1.1, speed=5000.0, torque=90.0))
    # joints.append(Joint(id=JointId.MF_MCP, angle=1.1, speed=5000.0, torque=90.0))
    
    # # 无名指关节
    # joints.append(Joint(id=JointId.RF_PIP, angle=1.1, speed=5000.0, torque=90.0))
    # joints.append(Joint(id=JointId.RF_MCP, angle=1.1, speed=5000.0, torque=90.0))
    
    # # 小指关节
    # joints.append(Joint(id=JointId.LF_PIP, angle=1.1, speed=5000.0, torque=90.0))
    # joints.append(Joint(id=JointId.LF_MCP, angle=1.1, speed=5000.0, torque=90.0))

    

    connected = hand.open(CommType.ETHERCAT, r"\Device\NPF_{22F450DC-244F-47FA-A538-CBD0142495BE}")
    if not connected:
        print("connect failed")
        return
    ver = hand.get_firmware_version()
    hand_type = hand.get_hand_type()
    print(f"ver: {ver}; hand_type: {hand_type.value}")

    hand.move_joints(joints)
    time.sleep(0.2)
        
    joints = hand.get_joints()

    time.sleep(0.2)

    hand.close()
    time.sleep(0.5)
    # print("hand is closed")


if __name__ == "__main__":
    main()
