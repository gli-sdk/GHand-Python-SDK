import logging
from pathlib import Path
import sys
import time
from typing import Optional
from xiaoyao import configure_logging

_logger = logging.getLogger(__name__)
configure_logging(level=logging.INFO)
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xiaoyao.adaptive_grasp import (
    AdaptiveGrasper,
    GraspState,
)
from xiaoyao.adaptive_grasp.demo_config import build_demo_runtime_config
from xiaoyao.dexhand import CommType, DexHand
from xiaoyao.exceptions import (
    DataReceiveError,
    DeviceDisconnectedError,
    DeviceFaultError,
    JointFaultError,
)

def main() -> None:
    logging.basicConfig(level=logging.INFO)

    hand = DexHand()
    grasper: Optional[AdaptiveGrasper] = None

    connected = hand.open(CommType.ETHERCAT, "auto")
    runtime_config = build_demo_runtime_config()
    try:
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
        while grasper.get_state() == GraspState.ADAPTIVE_HOLD:
            state_val = grasper.get_state().value
            print(f"state={state_val}; torque={grasper.current_torque}\n", flush=True)
            grasper.poll_visualizer()
            time.sleep(0.1)
        print(f"Final state: {grasper.get_state().value}")

        grasper.finish()
        print("Grasp Done.")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        if grasper is not None:
            print("Sending quick release command...")
            grasper.emergency_release(wait_s=runtime_config.interrupt_release_wait_s)
    except DeviceDisconnectedError as exc:
        print(f"\n[Device Disconnected] {exc.message}")
    except JointFaultError as exc:
        print(f"\n[Joint Fault] {exc.message}")
    except DeviceFaultError as exc:
        print(f"\n[Device Fault] {exc.message}")
    except DataReceiveError as exc:
        print(f"\n[Data Receive Error] {exc.message}")
    except Exception as exc:
        print(f"\n[Unexpected Error] {type(exc).__name__}: {exc}")
    finally:
        hand.tactile_close()
        hand.close()
        time.sleep(0.2)  # wait for hardware teardown


if __name__ == "__main__":
    main()
