import logging
import time

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand
from ghand.types import ErrorCode, State

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)


def data_callback(tpdo):
    """
    Data callback function

    Args:
        tpdo: Parsed TPDO data object
    """
    print("Received TPDO data:")
    print(f"  Hand state: {tpdo.hand}")
    print(
        f"  Thumb DIP: angle={tpdo.thumb_dip.angle:.1f}°, state={State(tpdo.thumb_dip.state).name}, error={ErrorCode(tpdo.thumb_dip.error).name}"
    )
    print(
        f"  FF MCP: angle={tpdo.ff_mcp.angle:.1f}°, state={State(tpdo.ff_mcp.state).name}, error={ErrorCode(tpdo.ff_mcp.error).name}"
    )
    # Process received data here


def main():
    # Create dexterous hand instance
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)

    # Open connection
    if not hand.open():
        print("Failed to open hand connection")
        return

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
        hand.close()


if __name__ == "__main__":
    main()
