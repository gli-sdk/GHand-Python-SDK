import argparse
import csv
import logging
from datetime import datetime
from pathlib import Path
import sys
import time

# Ensure local "src" package is imported before site-packages.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xiaoyao import Joint, configure_logging
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig, AdaptiveGrasper
from xiaoyao.dexhand import CommType, DexHand, JointId, TactileSensorId
from xiaoyao.exceptions import DataReceiveError, DeviceDisconnectedError, DeviceFaultError, JointFaultError


# configure_logging(level=logging.INFO)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adaptive grasp demo.")
    parser.add_argument("--stiffness", type=float, default=0.3)
    parser.add_argument("--base_torque", type=int, default=30)
    parser.add_argument("--max-torque", type=int, default=80)
    parser.add_argument("--max-normal-force", type=float, default=0.5)
    parser.add_argument("--variance-threshold", type=float, default=0.06)
    parser.add_argument("--hold-time", type=float, default=20.0)
    parser.add_argument("--release-hold-time", type=float, default=20.0)
    parser.add_argument("--release-open-speed", type=int, default=50)
    parser.add_argument("--release-open-torque", type=int, default=50)
    parser.add_argument("--contact_threshold_z", type=float, default=0.8)
    parser.add_argument(
        "--pre-grasp-preset",
        type=str,
        default="three_finger_pinch",
        choices=["two_finger_pinch", "three_finger_pinch", "four_finger_grasp", "five_finger_grasp"],
        help="Pre-grasp preset from grasp table. DIP joints are passive and excluded.",
    )
    return parser


def build_config(args: argparse.Namespace) -> AdaptiveGraspConfig:
    return AdaptiveGraspConfig(
        stiffness=args.stiffness,
        base_torque=args.base_torque,
        max_torque=args.max_torque,
        max_normal_force_per_finger=args.max_normal_force,
        variance_threshold=args.variance_threshold,
        pre_grasp_preset=args.pre_grasp_preset,
        release_hold_time_s=args.release_hold_time,
        release_open_speed=args.release_open_speed,
        release_open_torque=args.release_open_torque,
    )


def _build_csv_header() -> list[str]:
    sensors = [
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
        TactileSensorId.RING_FINGER,
        TactileSensorId.LITTLE_FINGER,
    ]
    header = ["timestamp", "state", "torque"]
    for s in sensors:
        name = s.value
        header.extend([f"{name}_x", f"{name}_y", f"{name}_z"])
    return header


def _read_tactile_row(hand: DexHand, state: str, torque: int) -> dict[str, object]:
    row: dict[str, object] = {
        "timestamp": datetime.now().isoformat(),
        "state": state,
        "torque": torque,
    }
    try:
        data = hand.get_tactile_data()
    except Exception:
        data = {}
    for sid in [
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
        TactileSensorId.RING_FINGER,
        TactileSensorId.LITTLE_FINGER,
    ]:
        name = sid.value
        info = data.get(sid)
        if info is not None:
            row[f"{name}_x"] = info.get_force_x()
            row[f"{name}_y"] = info.get_force_y()
            row[f"{name}_z"] = info.get_force_z()
        else:
            row[f"{name}_x"] = 0.0
            row[f"{name}_y"] = 0.0
            row[f"{name}_z"] = 0.0
    return row


def main() -> None:
    args = build_parser().parse_args()
    hand = DexHand()

    connected = hand.open(CommType.ETHERCAT, "auto")
    csv_file = None
    csv_writer = None
    try:
        if not connected:
            print("Connection failed.")
            return

        if not hand.tactile_open():
            print("Failed to open tactile sensors.")
            return

        # 准备 CSV 输出目录
        dist_dir = ROOT / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        csv_path = dist_dir / f"tactile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        csv_writer = csv.DictWriter(csv_file, fieldnames=_build_csv_header())
        csv_writer.writeheader()
        print(f"Tactile data will be saved to: {csv_path}")

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
        if args.pre_grasp_preset == "four_finger_grasp":
            grasper._TORQUE_JOINTS = (
                JointId.THUMB_PIP,
                JointId.THUMB_MCP,
                JointId.FF_PIP,
                JointId.FF_MCP,
                JointId.MF_PIP,
                JointId.MF_MCP,
                JointId.RF_MCP,
                JointId.RF_PIP,
            )
        if args.pre_grasp_preset == "five_finger_grasp":
            grasper._TORQUE_JOINTS = (
                JointId.THUMB_PIP,
                JointId.THUMB_MCP,
                JointId.FF_PIP,
                JointId.FF_MCP,
                JointId.MF_PIP,
                JointId.MF_MCP,
                JointId.RF_MCP,
                JointId.RF_PIP,
                JointId.LF_MCP,
                JointId.LF_PIP,
            )
        print("Starting adaptive grasp...")
        print(
            f"release_hold_time_s={config.release_hold_time_s}, "
            f"release_open_speed={config.release_open_speed}, "
            f"release_open_torque={config.release_open_torque}"
        )
        print(f"Pre-grasp preset={config.pre_grasp_preset} (DIP passive)")

        if not grasper.grasp():
            print(f"Grasp failed. state={grasper.get_state().value}")
            return

        print("Grasp started. Holding...")
        start = time.time()
        while (time.time() - start) < args.hold_time:
            elapsed = time.time() - start
            state_val = grasper.get_state().value
            print(
                f"\rstate={state_val:<18} "
                f"torque={grasper.current_torque:>3} "
                f"elapsed={elapsed:>5.1f}s",
                end="",
                flush=True,
            )
            if csv_writer is not None:
                row = _read_tactile_row(hand, state_val, grasper.current_torque)
                csv_writer.writerow(row)
                csv_file.flush()
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
        if csv_file is not None:
            csv_file.close()
        hand.tactile_close()
        hand.close()
        time.sleep(0.2)


if __name__ == "__main__":
    main()
