import time
from xiaoyao.dexhand import DexHand, CommType, Joint


def get_temprature(data):
    return data["temp"]


def process_data(data):
    temp = get_temprature(data)
    print(temp)
    for key in ["thumb1", "thumb2"]:
        print(f"{key}: {data[key]}")


def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, "auto")
    # if not connected:
    #     print("connect failed")
    #     return
    # ver = hand.get_firmware_version()
    # hand_type = hand.get_hand_type()
    # print(f"ver: {ver}; hand_type: {hand_type.value}")

    hand.move_joints(th_pip=Joint(angle=0), th_mcp=Joint(angle=0))
    # sub_id = hand.sub_hand_data(callback=process_data)
    # time.sleep(3)
    # hand.unsub_hand_data(sub_id)
    hand.close()


if __name__ == "__main__":
    main()
