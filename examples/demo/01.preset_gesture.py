import logging
import time

from ghand import ProductType, CommType, GestureType, GHand, configure_logging, execute_gesture
from ghand.types import GHandError

# Configure SDK logging (shows connection state, warnings, errors)
# configure_logging(level=logging.INFO)


def main():
    """Main execution function, demonstrates how to execute preset gestures."""
    print("***** GHand SDK - Preset Gesture Demo *****\n")
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")

    try:
        if not connected:
            print("[Scan complete] Failed to connect to dexterous hand.")
            return

        print("\n--- Device ready, starting preset gesture demo ---\n")

        # Define gesture list to demo
        gesture_demo = [
            GestureType.OPEN_HAND,
            GestureType.FIST,
            GestureType.OK,
            GestureType.THUMBS_UP,
            GestureType.SIX_SIGN,
        ]

        # Loop through gesture actions
        gesture_cycle = 0
        max_cycles = 0  # Set cycle count, 0 means infinite loop

        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break

            print(f"\n--- Cycle {gesture_cycle}: Gesture demo started ---")

            # Demo all gestures in sequence
            for i, gesture in enumerate(gesture_demo, 1):
                print(f"Demo {i}: [{gesture.value}]")

                if not execute_gesture(hand, gesture, speed=100, torque=100):
                    print(f"{gesture.value} action failed, terminating demo")
                    hand.close()
                    return
                # time.sleep(1)

            print(f"\n--- Cycle {gesture_cycle}: Gesture demo ended ---\n")

            # Prompt
            if max_cycles == 0:
                print("Press Ctrl+C to stop demo and exit program\n")

    except KeyboardInterrupt:
        print("Program interrupted by user.")
    except GHandError as e:
        print(f"[Critical Error] {e}")
    finally:
        hand.close()
        time.sleep(0.5)
        print("Demo ended, disconnected")


if __name__ == "__main__":
    main()
