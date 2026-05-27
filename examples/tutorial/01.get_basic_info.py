import logging

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand

# Configure SDK logging (shows connection state, errors, etc.)
configure_logging(level=logging.INFO)


def main():
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.RS485)
    connected = hand.open("auto")
    if not connected:
        print("Connection failed")
        return

    # Get device information
    ver = hand.get_firmware_version()
    hand_name = hand.get_device_name()
    hand_hw_ver = hand.get_hardware_version()
    serial_num = hand.get_serial_number()
    hand_type = hand.get_hand_type()
    hand_info = hand.get_hand_info()
    # motor_ver = hand.get_motor_driver_version()

    # Output device information
    print(f"\tDevice Name: {hand_name}")
    print(f"\tFirmware: {ver}, Hardware: {hand_hw_ver}")
    print(f"\tHand Type: {hand_type.value}")
    print(f"\tSerial Number: {serial_num}")
    # print(f"\tMotor Driver Version: {motor_ver[0]}.{motor_ver[1]}.{motor_ver[2]}")
    print(f"\thand_state: {hand_info.state}")
    hand.close()


if __name__ == "__main__":
    main()
