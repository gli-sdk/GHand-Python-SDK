import argparse
import csv
import logging
from datetime import datetime
from pathlib import Path
import sys
import time
from typing import Optional


_logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xiaoyao import Joint, configure_logging
from xiaoyao.adaptive_grasp import (
    AdaptiveGraspConfig,
    AdaptiveGrasper,
    ObjectProfileRegistry,
)
from xiaoyao.dexhand import CommType, DexHand, TactileSensorId
from xiaoyao.exceptions import (
    DataReceiveError,
    DeviceDisconnectedError,
    DeviceFaultError,
    JointFaultError,
)


class TactileLogger:
    """Encapsulates CSV logging for tactile sensor data."""

    _SENSORS = [
        TactileSensorId.THUMB,
        TactileSensorId.FOREFINGER,
        TactileSensorId.MIDDLE_FINGER,
        TactileSensorId.RING_FINGER,
        TactileSensorId.LITTLE_FINGER,
    ]

    def __init__(self, hand: DexHand, output_dir: Path) -> None:
        self.hand = hand
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / f"tactile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._file = open(csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self._build_header())
        self._writer.writeheader()
        self.csv_path = csv_path

    def _build_header(self) -> list[str]:
        header = ["timestamp", "state", "torque"]
        for s in self._SENSORS:
            name = s.value
            header.extend([f"{name}_x", f"{name}_y", f"{name}_z"])
        return header

    def write_row(self, state: str, torque: int) -> None:
        row: dict[str, object] = {
            "timestamp": datetime.now().isoformat(),
            "state": state,
            "torque": torque,
        }
        try:
            data = self.hand.get_tactile_data()
        except Exception:
            _logger.exception("Failed to get tactile data")
            data = {}
        for sid in self._SENSORS:
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
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Adaptive grasp demo.")
    parser.add_argument(
        "--pre-grasp-preset",
        type=str,
        default="two_finger_pinch",
        choices=["two_finger_pinch", "three_finger_pinch", "four_finger_grasp", "five_finger_grasp"],
        help="Pre-grasp preset from grasp table. DIP joints are passive and excluded.",
    )
    parser.add_argument(
        "--object",
        type=str,
        default=None,
        choices=ObjectProfileRegistry.list_names(),
        help="Object profile from registry for force planning.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print per-finger tactile analysis during adaptive hold.",
    )
    return parser


HOLD_TIME_S = 5.0


def _print_verbose(grasper: AdaptiveGrasper) -> None:
    analysis = grasper.last_tactile_analysis
    decisions = grasper.last_force_decisions
    if analysis is None or not analysis.per_finger:
        return

    parts = []
    for finger in sorted(analysis.per_finger.keys(), key=lambda f: f.value):
        p = analysis.per_finger[finger]
        d = decisions.get(finger) if decisions else None
        ctrl = f"{d.control_u:+.3f}" if d else "N/A"
        parts.append(
            f"{finger.value:10s} s={p.s_total:.2f} fz={p.fz:.2f}N u={ctrl}"
        )
    print(" | ".join(parts))


def main() -> None:
    args = build_parser().parse_args()
    hand = DexHand()

    connected = hand.open(CommType.ETHERCAT, "auto")
    logger: Optional[TactileLogger] = None
    try:
        if not connected:
            print("Connection failed.")
            return

        if not hand.tactile_open():
            print("Failed to open tactile sensors.")
            return

        dist_dir = ROOT / "dist"
        logger = TactileLogger(hand, dist_dir)
        print(f"Tactile data will be saved to: {logger.csv_path}")

        config = AdaptiveGraspConfig(pre_grasp_preset=args.pre_grasp_preset)
        grasper = AdaptiveGrasper(hand=hand, config=config)

        object_profile = None
        if args.object:
            object_profile = ObjectProfileRegistry.get(args.object)
            if object_profile:
                print(
                    f"Object profile: {args.object} "
                    f"({object_profile.material}, {object_profile.weight_kg}kg)"
                )

        print("Starting adaptive grasp...")
        print(
            f"release_hold_time_s={config.release_hold_time_s}, "
            f"release_open_speed={config.release_open_speed}, "
            f"release_open_torque={config.release_open_torque}"
        )
        print(f"Pre-grasp preset={config.pre_grasp_preset} (DIP passive)")

        if not grasper.grasp_core(object_profile=object_profile):
            print(f"Grasp failed. state={grasper.get_state().value}")
            return

        print("Grasp started. Holding...")
        start = time.time()
        while (time.time() - start) < HOLD_TIME_S:
            elapsed = time.time() - start
            state_val = grasper.get_state().value
            status_line = (
                f"state={state_val:<18} "
                f"torque={grasper.current_torque:>3} "
                f"elapsed={elapsed:>5.1f}s"
            )
            if args.verbose:
                print(status_line)
                _print_verbose(grasper)
            else:
                print(f"\r{status_line}", end="", flush=True)
            logger.write_row(state_val, grasper.current_torque)
            time.sleep(0.1)
        if not args.verbose:
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
        if logger is not None:
            logger.close()
        hand.tactile_close()
        hand.close()
        time.sleep(0.2)  # wait for hardware teardown


if __name__ == "__main__":
    main()
