import time
from adaptive_grasp import AdaptiveGrasper
from adaptive_grasp.demo_config import build_demo_runtime_config
from ghand import GHand,CommType, ProductType

hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
grasper = None
runtime_config = build_demo_runtime_config("paper_cup", 60.0)

try:
    
    if not hand.open("auto"):
        raise RuntimeError("Connection failed")

    if not hand.tactile_open():
        raise RuntimeError("Failed to open tactile sensors")

    time.sleep(0.5)

    grasper = AdaptiveGrasper(
        hand=hand,
        config=runtime_config.adaptive_config,
    )

    grasp_ok = grasper.grasp_core()
    if not grasp_ok:
        raise RuntimeError(f"Grasp failed at state={grasper.get_state().value}")

    final_state = grasper.wait_until_finished()
    print(f"Final state: {final_state.value}")
except KeyboardInterrupt:
    if grasper is not None:
        grasper.emergency_release(wait_s=runtime_config.interrupt_release_wait_s)
finally:
    hand.tactile_close()
    hand.close()