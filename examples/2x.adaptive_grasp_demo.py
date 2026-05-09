import argparse
import csv
import logging
from datetime import datetime
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
    AdaptiveGraspConfig,
    AdaptiveGrasper,
    GraspState,
)
from xiaoyao.adaptive_grasp.torque_hold_planner import TorqueHoldDecision
from xiaoyao.dexhand import CommType, DexHand, TactileSensorId
from xiaoyao.exceptions import (
    DataReceiveError,
    DeviceDisconnectedError,
    DeviceFaultError,
    JointFaultError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the adaptive grasp demo.")
    parser.add_argument("--base_torque", "--base-torque", type=int, default=5)
    parser.add_argument("--phase-closing-torque", type=int, default=10)
    parser.add_argument("--max_torque", "--max-torque", type=int, default=80)
    parser.add_argument("--contact_threshold_z", "--contact-threshold-z", type=float, default=0.2)
    parser.add_argument("--pre_grasp_preset", "--pre-grasp-preset", default="three_finger_pinch")
    parser.add_argument("--hold_time", "--hold-time", type=float, default=50.0)
    parser.add_argument("--default_object", dest="object", default="glass")
    parser.add_argument(
        "--hold-command-mode",
        choices=("position", "torque"),
        default="position",
        help="Command mode used in adaptive hold.",
    )
    parser.add_argument("--adaptive-hold-torque", type=int, default=6)
    parser.add_argument(
        "--no-release-on-interrupt",
        action="store_true",
        help="Do not call release() when interrupted with Ctrl+C.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def build_config(args: argparse.Namespace) -> AdaptiveGraspConfig:
    kwargs = {
        "base_torque": args.base_torque,
        "phase_closing_torque": args.phase_closing_torque,
        "max_torque": args.max_torque,
        "contact_threshold_z": args.contact_threshold_z,
        "pre_grasp_preset": args.pre_grasp_preset,
        "release_hold_time_s": args.hold_time,
        "adaptive_hold_command_mode": args.hold_command_mode,
        "adaptive_hold_torque": args.adaptive_hold_torque,
    }
    if args.object is not None:
        kwargs["default_object"] = args.object
    return AdaptiveGraspConfig(**kwargs)


def _format_optional_float(name: str, value: Optional[float]) -> str:
    if value is None:
        return f"{name}=NA"
    return f"{name}={value:.2f}"


def format_hold_status(
    state: str,
    torque: int,
    mode: str,
    total_fz: Optional[float],
    slip_risk: Optional[float],
    slip_confirmed: Optional[bool],
    torque_decision: Optional[TorqueHoldDecision],
) -> str:
    parts = [
        f"state={state:<18}",
        f"mode={mode}",
        f"torque={torque:>3}",
        _format_optional_float("total_fz", total_fz),
        _format_optional_float("slip_risk", slip_risk),
    ]
    if slip_confirmed is not None:
        parts.append(f"slip_confirmed={slip_confirmed}")
    if torque_decision is not None:
        parts.append(f"F_ref_total={torque_decision.F_ref_total:.2f}")
        finger_torques = ", ".join(
            f"{finger.name}={value:.2f}"
            for finger, value in sorted(
                torque_decision.finger_torques.items(),
                key=lambda item: item[0].name,
            )
        )
        if finger_torques:
            parts.append(f"finger_torques=[{finger_torques}]")
    return "; ".join(parts)


def print_hold_status(
    state: str,
    torque: int,
    mode: str = "",
    total_fz: Optional[float] = None,
    slip_risk: Optional[float] = None,
    slip_confirmed: Optional[bool] = None,
    torque_decision: Optional[TorqueHoldDecision] = None,
) -> None:
    if not mode and total_fz is None and slip_risk is None and torque_decision is None:
        status_line = f"state={state:<18}; torque={torque:>3}"
    else:
        status_line = format_hold_status(
            state=state,
            torque=torque,
            mode=mode,
            total_fz=total_fz,
            slip_risk=slip_risk,
            slip_confirmed=slip_confirmed,
            torque_decision=torque_decision,
        )
    print(status_line, flush=True)


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


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    hand = DexHand()
    grasper: Optional[AdaptiveGrasper] = None

    connected = hand.open(CommType.ETHERCAT, "auto")
    logger: Optional[TactileLogger] = None
    try:
        if not connected:
            print("Connection failed.")
            return

        if not hand.tactile_open():
            print("Failed to open tactile sensors.")
            return
        # time.sleep(1)
        # hand.tactile_zero()
        # time.sleep(0.5)

        dist_dir = ROOT / "dist"
        logger = TactileLogger(hand, dist_dir)
        print(f"Tactile data will be saved to: {logger.csv_path}")

        config = build_config(args)
        grasper = AdaptiveGrasper(hand=hand, config=config)

        print("Starting adaptive grasp...")
        print(
            f"release_hold_time_s={config.release_hold_time_s}, "
            f"release_open_speed={config.release_open_speed}, "
            f"release_open_torque={config.release_open_torque}, "
            f"adaptive_hold_command_mode={config.adaptive_hold_command_mode}, "
            f"adaptive_hold_torque={config.adaptive_hold_torque}"
        )
        print(f"Pre-grasp preset={config.pre_grasp_preset} (DIP passive)")

        grasp_ok = grasper.grasp_core()
        if not grasp_ok:
            print(f"Grasp failed at the state={grasper.get_state().value}")
            return

        print("Holding object...")
        while grasper.get_state() == GraspState.ADAPTIVE_HOLD:
            state_val = grasper.get_state().value
            analysis = grasper.last_tactile_analysis
            print_hold_status(
                state_val,
                grasper.current_torque,
                mode=config.adaptive_hold_command_mode,
                total_fz=analysis.total_fz if analysis is not None else None,
                slip_risk=analysis.slip_risk if analysis is not None else None,
                slip_confirmed=analysis.slip_confirmed if analysis is not None else None,
                torque_decision=grasper.last_torque_hold_decision,
            )
            # logger.write_row(state_val, grasper.current_torque)
            grasper.poll_visualizer()
            time.sleep(0.1)
        print(f"Final state: {grasper.get_state().value}")

        grasper.release()
        grasper.wait_for_visualizer_close()
        print("Grasp Done.")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        if grasper is not None and not args.no_release_on_interrupt:
            print("Releasing hand...")
            grasper.release()
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
