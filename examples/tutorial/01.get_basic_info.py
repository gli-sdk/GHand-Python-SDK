import logging

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand

# Configure SDK logging (shows connection state, errors, etc.)
configure_logging(level=logging.INFO)


def format_version(version):
    if version == (0, 0, 0):
        return "not available"
    return f"{version[0]}.{version[1]}.{version[2]}"


def main():
    hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)
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
    firmware_package_ver = hand.get_firmware_package_version()
    position_sensor_ver = hand.get_position_sensor_version()
    tactile_sensor_ver = hand.get_tactile_sensor_version()
    motor_ver = hand.get_motor_driver_version()
    thumb_tactile_sensor_ver = hand.get_thumb_tactile_sensor_version()
    finger_tactile_sensor_ver = hand.get_finger_tactile_sensor_version()

    # Output device information
    print(f"\tDevice Name: {hand_name}")
    print(f"\tFirmware: {ver}, Hardware: {hand_hw_ver}")
    print(f"\tHand Type: {hand_type.value}")
    print(f"\tSerial Number: {serial_num}")
    print(f"\tFirmware Package Version: {format_version(firmware_package_ver)}")
    print(f"\tPosition Sensor Version: {format_version(position_sensor_ver)}")
    print(f"\tTactile Sensor Version: {format_version(tactile_sensor_ver)}")
    print(f"\tMotor Driver Version: {format_version(motor_ver)}")
    print(f"\tThumb Tactile Sensor Version: {format_version(thumb_tactile_sensor_ver)}")
    print(f"\tFinger Tactile Sensor Version: {format_version(finger_tactile_sensor_ver)}")
    hand.close()


if __name__ == "__main__":
    main()
