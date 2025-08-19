# examples/get_basic_info.py。

from xiaoyao.dexhand import DexHand, CommType


def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, "auto")
    if not connected:
        print("connect failed")
        return
    ver = hand.get_firmware_version()
    hand_type = hand.get_hand_type()
    print(f"ver: {ver}; hand_type: {hand_type.value}")


if __name__ == "__main__":
    main()
