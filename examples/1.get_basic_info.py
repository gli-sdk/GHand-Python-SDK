# examples/get_basic_info.py。

from xiaoyao.dexhand import DexHand, CommType


def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, r"\Device\NPF_{22F450DC-244F-47FA-A538-CBD0142495BE}")
    if not connected:
        print("connect failed")
        return
    ver = hand.get_firmware_version()
    hand_name = hand.get_device_name()
    hand_hw_ver = hand.get_hardware_version()
    mfr_mark = hand.get_manufacturer_mark()
    prod_code = hand.get_product_code()
    rev_num = hand.get_revision_number()
    serial_num = hand.get_serial_number()
    hand_type = hand.get_hand_type()
    print(f"hand name:{hand_name};H/W ver:{hand_hw_ver};ver: {ver};hand_type: {hand_type.value};")
    print(f"Mfr Mark:{mfr_mark};Prod code:{prod_code};Rev num:{rev_num};Serial num:{int.from_bytes(serial_num, 'little')};")


if __name__ == "__main__":
    main()
