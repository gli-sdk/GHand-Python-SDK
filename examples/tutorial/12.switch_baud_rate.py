"""
Example: Switch RS485/CANFD baud-rate configuration.

The new baud-rate configuration is stored by the device and takes effect after
the next power-up. After power cycling the device, pass the new baud_rate value
to open().
"""

import logging,time

from ghand import (
    CANFDBitTiming,
    CommType,
    GHand,
    ProductType,
    RS485BaudRate,
    CANFDBitTiming,
    configure_logging,
)

# Configure SDK logging (shows connection state, errors, etc.)
configure_logging(level=logging.INFO)


def main():
    device_id = "auto"
    slave_id = 0x31

    # RS485 example: change these two values to match your current and target
    # device configuration.
    # comm_type = CommType.RS485
    # current_baud_rate = RS485BaudRate.BAUD_1000000
    # target_baud_rate = RS485BaudRate.BAUD_460800

    # CANFD example:
    comm_type = CommType.CANFD
    current_baud_rate = CANFDBitTiming.TIMING_1M_5M
    target_baud_rate = CANFDBitTiming.TIMING_1M_4M

    hand = GHand(product_type=ProductType.GHand5, comm_type=comm_type)

    print("Connecting with current baud-rate configuration...")
    if not hand.open(device_id, slave_id=slave_id, baud_rate=current_baud_rate):
        print("Connection failed")
        return

    print(f"Writing new baud-rate configuration: {target_baud_rate.name}")
    if not hand.set_baudrate_config(target_baud_rate):
        print("Failed to write baud-rate configuration")
        hand.close()
        return

    hand.close()
    print("Baud-rate configuration written successfully.")

    print(f"Preparing CANFD adapter listener at {target_baud_rate.name}...")
    if not hand.prepare_canfd_baudrate_listener(device_id, target_baud_rate):
        print("Failed to prepare CANFD adapter listener")
        return

    input("Power-cycle the device now, then press Enter to reconnect...")
    if hand.open(device_id, slave_id=slave_id, baud_rate=target_baud_rate):
        print("Reconnected with the new baud-rate configuration.")
    else:
        print("Failed to reconnect with the new baud-rate configuration.")
    hand.close()


if __name__ == "__main__":
    main()
