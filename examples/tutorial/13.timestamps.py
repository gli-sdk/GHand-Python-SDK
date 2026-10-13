"""Show host receive/send timestamps in Unix milliseconds and Beijing time.

Change COMM_TYPE, PRODUCT_TYPE and DEVICE_ID to match your device.
The command holds the currently read joint angles. sent_at_ms describes the
completed transport send call, not completed device execution.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from ghand import (
    CommandReceipt,
    CommType,
    GHand,
    JointCommand,
    JointId,
    ProductType,
    configure_logging,
)

COMM_TYPE = CommType.ETHERCAT  # Also supports RS485 and CANFD.
PRODUCT_TYPE = ProductType.GHand5
DEVICE_ID = "auto"
BEIJING_TZ = timezone(timedelta(hours=8))


def format_timestamp(timestamp_ms: int | None) -> str:
    if timestamp_ms is None:
        return "None (not recorded)"
    seconds, milliseconds = divmod(timestamp_ms, 1000)
    dt = datetime.fromtimestamp(seconds, tz=BEIJING_TZ)
    return f"{timestamp_ms} -> {dt:%Y-%m-%d %H:%M:%S}.{milliseconds:03d} UTC+8"


def data_callback(data):
    lines = [
        "\n[RX] Device feedback",
        f"  received_at_ms: {format_timestamp(data.received_at_ms)}",
        f"  Hand: state={data.hand.state}, error={data.hand.error}, "
        f"temperature={data.hand.temperature}",
    ]
    for joint in data.joints:
        lines.append(
            f"  {JointId(joint.id).name} (id={joint.id}): "
            f"angle={joint.angle:.3f}deg, speed={joint.speed}, torque={joint.torque}, "
            f"state={joint.state}, error={joint.error}")
    if data.tactile:
        for sensor_id, tactile in data.tactile.items():
            lines.append(
                f"  Tactile {sensor_id.name}: state={tactile.state}, "
                f"resultant_force={tactile.resultant_force}, "
                f"distributed_force={tactile.distributed_force}, "
                f"received_at_ms={format_timestamp(tactile.received_at_ms)}")
    print("\n".join(lines))


def main():
    configure_logging(level=logging.INFO)
    hand = GHand(product_type=PRODUCT_TYPE, comm_type=COMM_TYPE)
    try:
        if not hand.open(DEVICE_ID):
            print("Connection failed")
            return

        joints = hand.get_joints()
        for joint in joints:
            print(f"Joint {joint.id} received_at_ms: "
                  f"{format_timestamp(joint.received_at_ms)}")

        hand.subscribe(data_callback, interval_ms=1000)
        commands = [
            JointCommand(id=joint.id, angle=30, speed=20, torque=20)
            for joint in joints
        ]
        # Each call needs its own receipt. Without receipt=..., the method
        # still returns bool and behaves like the original API.
        receipt = CommandReceipt()
        success = hand.move_joints(commands, receipt=receipt)

        # EtherCAT fills this same receipt asynchronously in the cyclic thread.
        # Use a monotonic clock for the wait timeout, not Unix timestamps.
        deadline = time.monotonic() + 1.0
        while success and receipt.sent_at_ms is None and time.monotonic() < deadline:
            time.sleep(0.01)
        lines = [
            "\n[TX] Command result",
            f"  success: {success}; receipt.success: {receipt.success}",
            f"  submitted_at_ms: {format_timestamp(receipt.submitted_at_ms)}",
            f"  sent_at_ms: {format_timestamp(receipt.sent_at_ms)}",
            "  Requested commands: mode=POSITION",
        ]
        # The SDK may apply limits and filter passive joints before encoding.
        for command in commands:
            lines.append(
                f"    {JointId(command.id).name} (id={command.id}): "
                f"angle={command.angle:.3f}deg, speed={command.speed}, "
                f"torque={command.torque}")
        print("\n".join(lines))
        if success and receipt.sent_at_ms is None:
            print("Send completion was not recorded within 1 second.")
        time.sleep(2)  # Observe receive timestamps from subscription callbacks.
    except KeyboardInterrupt:
        print("Stopping timestamp example")
    finally:
        if hand.is_connected():
            print(f"\n[TX] Stop command result: {hand.stop()}")
        hand.close()  # Also stops subscriptions.


if __name__ == "__main__":
    main()
