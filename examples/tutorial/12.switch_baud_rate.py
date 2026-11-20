"""
Example: Switch RS485/CANFD baud-rate configuration.

The new baud-rate configuration is stored by the device and takes effect after
the next power-up. After power cycling the device, pass the new baudrate value
to open().
"""

import logging
import sys

from ghand import (
    CANFDBitTiming,
    CommType,
    GHand,
    ProductType,
    RS485BaudRate,
    configure_logging,
)

# Configure SDK logging (shows connection state, errors, etc.)
configure_logging(level=logging.INFO)


def main():
    device_id = "auto"
    slave_id = 0x32

    # RS485 example: change these two values to match your current and target
    # device configuration.
    # comm_type = CommType.RS485
    # current_baud_rate = RS485BaudRate.BAUD_1000000
    # target_baud_rate = RS485BaudRate.BAUD_460800

    # CANFD example:
    comm_type = CommType.CANFD
    # Must match the device's currently active timing, not the target timing.
    current_baud_rate = CANFDBitTiming.TIMING_500K_1M
    target_baud_rate = CANFDBitTiming.TIMING_1M_5M

    hand = GHand(product_type=ProductType.GHand5, comm_type=comm_type)

    try:
        print(f"Connecting with slave ID 0x{slave_id:02X}, "
              f"current baud-rate configuration: {current_baud_rate.name}")
        if not hand.open(device_id, slave_id=slave_id, baudrate=current_baud_rate):
            print("Connection failed; check the slave ID and current baud-rate configuration")
            return 1

        print(f"Writing new baud-rate configuration: {target_baud_rate.name}")
        if not hand.set_baudrate(target_baud_rate):
            print("Failed to confirm baud-rate configuration; check the device before retrying")
            return 1

        hand.close()
        print("Baud-rate configuration written successfully.")

        input("Power-cycle the device now, wait for startup, then press Enter to reconnect...")
        if not hand.open(device_id, slave_id=slave_id, baudrate=target_baud_rate):
            print(f"Failed to reconnect; the written target is {target_baud_rate.name}")
            return 1
        print("Reconnected with the new baud-rate configuration.")
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nDemo interrupted; any written baud-rate configuration remains stored.")
        return 1
    except Exception:
        logging.exception("Baud-rate switching failed")
        return 1
    finally:
        hand.close()


if __name__ == "__main__":
    sys.exit(main())
