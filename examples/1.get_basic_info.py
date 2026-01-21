import logging
from xiaoyao.dexhand import DexHand, CommType

logger = logging.getLogger("xiaoyao")

def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT,  "auto") 
    if not connected:
        logger.error("connect failed")
        return
    ver = hand.get_firmware_version()
    hand_name = hand.get_device_name()
    hand_hw_ver = hand.get_hardware_version()
    serial_num = hand.get_serial_number()
    hand_type = hand.get_hand_type()
    hand_temperature = hand.get_temperature()
    logger.info(f"hand name:{hand_name};H/W ver:{hand_hw_ver};ver: {ver};hand_type: {hand_type.value};")
    logger.info(f"Serial num:{int.from_bytes(serial_num, 'little')};")
    logger.info(f"hand temperature:{hand_temperature};")

if __name__ == "__main__":
    main()
