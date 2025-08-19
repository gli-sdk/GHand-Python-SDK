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
    connected = hand.open(CommType.ETHERCAT, r"\Device\NPF_{22F450DC-244F-47FA-A538-CBD0142495BE}")
    if not connected:
        print("connect failed")
        return
    ver = hand.get_firmware_version()
    hand_type = hand.get_hand_type()
    print(f"ver: {ver}; hand_type: {hand_type.value}")

    th_pip = Joint(id=JointId.THUMB_PIP, angle=0)
    th_mcp = Joint(id=JointId.THUMB_MCP, angle=0)
    joints = [th_pip, th_mcp]
    hand.move_joints(joints=joints)
    joints = hand.get_joints()
    # print(joints)
    # sub_id = hand.sub_hand_data(callback=process_data)
    time.sleep(5)
    # hand.unsub_hand_data(sub_id)
    hand.close()


if __name__ == "__main__":
    main()
