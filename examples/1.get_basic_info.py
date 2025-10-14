# examples/get_basic_info.py。

from xiaoyao.dexhand import DexHand, CommType


def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT,  "auto") 
    if not connected:
        print("connect failed")
        return
    ver = hand.get_firmware_version()
    hand_name = hand.get_device_name()
    hand_hw_ver = hand.get_hardware_version()
    serial_num = hand.get_serial_number()
    hand_type = hand.get_hand_type()
    print(f"hand name:{hand_name};H/W ver:{hand_hw_ver};ver: {ver};hand_type: {hand_type.value};")
    print(f"Serial num:{int.from_bytes(serial_num, 'little')};")


if __name__ == "__main__":
    main()
