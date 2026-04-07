import argparse
import logging
from pathlib import Path
import sys
import time

# Ensure local "src" package is imported before site-packages.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xiaoyao import configure_logging
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig, AdaptiveGrasper
from xiaoyao.dexhand import CommType, DexHand, JointId
from xiaoyao.exceptions import DataReceiveError, DeviceDisconnectedError, DeviceFaultError, JointFaultError


configure_logging(level=logging.INFO)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adaptive grasp demo with optional Phase 4-EXT.")
    parser.add_argument("--stiffness", type=float, default=0.2)
    parser.add_argument("--base-torque", type=int, default=10)
    parser.add_argument("--max-torque", type=int, default=30)
    parser.add_argument("--max-normal-force", type=float, default=0.5)
    parser.add_argument("--variance-threshold", type=float, default=0.06)
    parser.add_argument("--hold-time", type=float, default=10.0)
    parser.add_argument(
        "--pre-grasp-preset",
        type=str,
        default="three_finger_pinch",
        choices=["two_finger_pinch", "three_finger_pinch", "five_finger_grasp"],
        help="Pre-grasp preset from grasp table. DIP joints are passive and excluded.",
    )
    parser.add_argument("--phase4-ext", action="store_true", help="Enable dynamic load adaptation.")
    parser.add_argument("--load-gain", type=float, default=1.0)
    parser.add_argument("--ext-smoothing-alpha", type=float, default=0.4)
    parser.add_argument("--ext-safety-margin-ratio", type=float, default=0.9)
    return parser


def build_config(args: argparse.Namespace) -> AdaptiveGraspConfig:
    return AdaptiveGraspConfig(
        stiffness=args.stiffness,
        base_torque=args.base_torque,
        max_torque=args.max_torque,
        max_normal_force_per_finger=args.max_normal_force,
        variance_threshold=args.variance_threshold,
        pre_grasp_preset=args.pre_grasp_preset,
        enable_phase4_ext=args.phase4_ext,
        load_gain=args.load_gain,
        ext_smoothing_alpha=args.ext_smoothing_alpha,
        ext_safety_margin_ratio=args.ext_safety_margin_ratio,
    )


def main() -> None:
    args = build_parser().parse_args()
    hand = DexHand()

    connected = hand.open(CommType.ETHERCAT, "auto")
    try:
        if not connected:
            print("Connection failed.")
            return

        if not hand.tactile_open():
            print("Failed to open tactile sensors.")
            return

        config = build_config(args)
        grasper = AdaptiveGrasper(hand=hand, config=config)
        if args.pre_grasp_preset == "two_finger_pinch":
            grasper._TORQUE_JOINTS = (
                JointId.THUMB_PIP,
                JointId.THUMB_MCP,
                JointId.FF_PIP,
                JointId.FF_MCP,
            )
            print("Strict two-finger torque mode enabled: THUMB + FF (MCP/PIP)")
        if args.pre_grasp_preset == "three_finger_pinch":
            grasper._TORQUE_JOINTS = (
                JointId.THUMB_PIP,
                JointId.THUMB_MCP,
                JointId.FF_PIP,
                JointId.FF_MCP,
                JointId.MF_PIP,
                JointId.MF_MCP,
            )
        print("Starting adaptive grasp...")
        print(
            f"Phase4-EXT={config.enable_phase4_ext}, "
            f"load_gain={config.load_gain}, alpha={config.ext_smoothing_alpha}, "
            f"safety_margin={config.ext_safety_margin_ratio}"
        )
        print(f"Pre-grasp preset={config.pre_grasp_preset} (DIP passive)")

        if not grasper.grasp():
            print(f"Grasp failed. state={grasper.get_state().value}")
            return

        print("Grasp started. Holding...")
        start = time.time()
        while (time.time() - start) < args.hold_time:
            elapsed = time.time() - start
            print(
                f"\rstate={grasper.get_state().value:<18} "
                f"torque={grasper.current_torque:>3} "
                f"elapsed={elapsed:>5.1f}s",
                end="",
                flush=True,
            )
            time.sleep(0.1)
        print()

        print("Releasing...")
        grasper.release()
        print("Done.")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
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
        time.sleep(0.2)


if __name__ == "__main__":
    main()
