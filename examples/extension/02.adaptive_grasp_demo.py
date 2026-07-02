import sys
# import logging
import time
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = str(PROJECT_ROOT / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from adaptive_grasp import AdaptiveGrasper
from adaptive_grasp.demo_config import build_demo_runtime_config
from ghand import (
    CommType,
    CommunicationError,
    GHand,
    HandStateError,
    ProductType,
    configure_logging,
)


# configure_logging(level=logging.INFO)


def main() -> None:
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")
    grasper: Optional[AdaptiveGrasper] = None

    runtime_config = build_demo_runtime_config()
    try:
        if connected:
            print("Hand connect successful.")
        else:
            print("Not connected.")
            return
        if not connected:
            print("Connection failed.")
            return

        if not hand.tactile_open():
            print("Failed to open tactile sensors.")
            return
        time.sleep(0.5)
        
        config = runtime_config.adaptive_config
        grasper = AdaptiveGrasper(hand=hand, config=config)

        print("Starting adaptive grasp...")
        print(
            f"release_hold_time_s={config.release_hold_time_s}, "
            f"default_object={config.default_object}"
        )

        grasp_ok = grasper.grasp_core()
        if not grasp_ok:
            print(f"Grasp failed at the state={grasper.get_state().value}")
            return

        print("Holding object...")
        final_state = grasper.wait_for_completion()
        print(f"Final state: {final_state.value}")
        print("Grasp Done.")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        if grasper is not None:
            print("Sending quick release command...")
            grasper.emergency_release(wait_s=runtime_config.interrupt_release_wait_s)
    except CommunicationError as exc:
        print(f"\n[Communication Error] {exc}")
    except HandStateError as exc:
        print(f"\n[Hand State Error] {exc}")
    except Exception as exc:
        print(f"\n[Unexpected Error] {type(exc).__name__}: {exc}")
    finally:
        hand.tactile_close()
        hand.close()
        time.sleep(0.2)  # wait for hardware teardown

if __name__ == "__main__":
    main()
