import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand
from ghand.types import ErrorCode, State, JointId

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)


def data_callback(data):
    """
    Data callback function

    Args:
        data: DeviceData instance containing hand state, joints and tactile info.
    """
    print("Received device data:")
    print(f"  Hand state: {data.hand}")
    for joint in data.joints:
        print(
            f"  {JointId(joint.id).name}: angle={joint.angle:.1f}°, "
            f"speed={joint.speed}, torque={joint.torque}, "
            f"state={State(joint.state).name}, error={ErrorCode(joint.error).name}"
        )
    if data.tactile:
        for sensor_id, tactile in data.tactile.items():
            print(
                f"  Tactile {sensor_id.name}: state={tactile.state}, "
                f"resultant_force={tactile.resultant_force}, "
                f"distributed_force={tactile.distributed_force}"
            )
    # Process received data here


def main():
    # Create dexterous hand instance
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)

    # Open connection
    if not hand.open():
        print("Failed to open hand connection")
        return

    hand.tactile_open()

    # Subscribe to data updates
    sub_id = hand.subscribe(data_callback)
    print(f"Subscribed with ID: {sub_id}")

    try:
        # Let subscription run for a while
        time.sleep(10)
    except KeyboardInterrupt:
        print("Stopping subscription")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Unsubscribe and close connection
        hand.unsubscribe(sub_id)
        hand.tactile_close()
        hand.close()


if __name__ == "__main__":
    main()
