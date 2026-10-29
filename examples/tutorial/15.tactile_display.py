# SPDX-FileCopyrightText: 2026 GLITech
# SPDX-License-Identifier: Apache-2.0
"""Tutorial 13: display tactile data with example-owned device lifecycle.

Run directly for GHand5 + EtherCAT; edit the connection settings in main().
Install GUI dependencies with pip install "ghand_python_sdk[tactile-display]".
The SDK display window only renders data; this example owns the connection,
subscription, tactile commands, worker thread, and shutdown.
"""

import signal
import sys
from typing import Callable

from ghand.types import CommType, HandType, ProductType


if __name__ == "__main__":
    try:
        import PySide6
        import pyqtgraph
    except ModuleNotFoundError as exc:
        if exc.name not in {"PySide6", "pyqtgraph"}:
            raise
        print('Missing optional dependencies for tactile display. Run: python -m pip install "ghand_python_sdk[tactile-display]"',
              file=sys.stderr)
        raise SystemExit(1)

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

from ghand.tactile_display.window import TactileWindow


class _SdkWorker(QObject):
    connected = Signal(bool, str)
    detected_side = Signal(str)
    command_finished = Signal(str, bool, str)
    shutdown_finished = Signal()

    def __init__(self, product: str, comm: str, device_id: str, display: TactileWindow,
                 hand_factory: Callable | None = None) -> None:
        super().__init__()
        self.product, self.comm, self.device_id = product, comm, device_id
        self.display, self.hand_factory = display, hand_factory
        self.hand = None
        self.subscription_id = None
        self.tactile_opened = False

    @Slot()
    def connect_device(self) -> None:
        try:
            if self.hand_factory is None:
                from ghand import GHand
                self.hand_factory = GHand
            self.hand = self.hand_factory(ProductType[self.product], CommType[self.comm])
            ok = bool(self.hand.open(self.device_id))
            message = "Device connected" if ok else "Device connection failed"
            if ok:
                try:
                    hand_type = self.hand.get_hand_type()
                except Exception:
                    hand_type = HandType.NONE
                if hand_type == HandType.LEFT_HAND:
                    self.detected_side.emit("left")
                elif hand_type == HandType.RIGHT_HAND:
                    self.detected_side.emit("right")
                else:
                    message += "; hand side unavailable, keeping the initial display side"
            self.connected.emit(ok, message)
        except Exception as exc:
            self.connected.emit(False, f"Device connection failed: {exc}")

    @Slot(int)
    def open_tactile(self, generation: int) -> None:
        if self.hand is None:
            self.command_finished.emit("open", False, "Device not connected"); return
        if self.subscription_id is not None:
            self.command_finished.emit("open", True, "Tactile opened"); return
        try:
            if not self.hand.tactile_open():
                self.command_finished.emit("open", False, "Failed to open tactile"); return
            self.tactile_opened = True
            self._subscribe(generation)
            self.command_finished.emit("open", True, "Tactile opened")
        except Exception as exc:
            try:
                self.hand.tactile_close()
            except Exception:
                pass
            self.tactile_opened = False; self.subscription_id = None
            self.command_finished.emit("open", False, f"Failed to open tactile: {exc}")

    @Slot()
    def close_tactile(self) -> None:
        try:
            self._unsubscribe()
            ok = bool(self.hand and self.hand.tactile_close())
            if ok:
                self.tactile_opened = False
            self.command_finished.emit("close", ok, "Tactile closed" if ok else "Failed to close tactile")
        except Exception as exc:
            self.command_finished.emit("close", False, f"Failed to close tactile: {exc}")

    @Slot()
    def zero_tactile(self) -> None:
        if self.hand is None or not self.tactile_opened:
            self.command_finished.emit("zero", False, "Tactile not opened"); return
        old_generation = self.display.data_generation
        try:
            self._unsubscribe()
            ok = bool(self.hand.tactile_zero())
            self._subscribe(self.display.clear() if ok else old_generation)
            self.command_finished.emit("zero", ok, "Tactile zeroed" if ok else "Failed to zero tactile")
        except Exception as exc:
            if self.subscription_id is None:
                try:
                    self._subscribe(old_generation)
                except Exception:
                    pass
            self.command_finished.emit("zero", False, f"Failed to zero tactile: {exc}")

    @Slot()
    def shutdown(self) -> None:
        try:
            if self.hand:
                self._unsubscribe()
                if self.tactile_opened:
                    try:
                        self.hand.tactile_close()
                    except Exception:
                        pass
                self.hand.close()
        finally:
            self.shutdown_finished.emit()

    def _subscribe(self, generation: int) -> None:
        self.subscription_id = self.hand.subscribe(
            lambda data: self.display.update_tactile(getattr(data, "tactile", None), generation),
            interval_ms=20)

    def _unsubscribe(self) -> None:
        if self.subscription_id is not None:
            self.hand.unsubscribe(self.subscription_id); self.subscription_id = None


class TactileExampleWindow(TactileWindow):
    connect_requested = Signal()
    shutdown_requested = Signal()

    def __init__(self, product: str, comm: str, device_id: str) -> None:
        super().__init__()
        self.product, self.comm, self.device_id = product, comm, device_id
        self._closing = self._allow_close = False
        self._thread = self._worker = None
        self._start_worker()

    def _start_worker(self) -> None:
        self._buttons(True); self._thread = QThread(self)
        self._worker = _SdkWorker(self.product, self.comm, self.device_id, self)
        self._worker.moveToThread(self._thread)
        self.connect_requested.connect(self._worker.connect_device); self.open_requested.connect(self._worker.open_tactile)
        self.close_requested.connect(self._worker.close_tactile); self.zero_requested.connect(self._worker.zero_tactile)
        self.shutdown_requested.connect(self._worker.shutdown); self._worker.connected.connect(self.set_connected)
        self._worker.detected_side.connect(self.set_side)
        self._worker.command_finished.connect(self.set_command_result)
        self._worker.shutdown_finished.connect(self._thread.quit); self._thread.finished.connect(self._finish_close)
        self._thread.start(); self.connect_requested.emit(); self.set_status("Connecting to device…")

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._allow_close:
            super().closeEvent(event); return
        if not self._closing:
            self._closing = True; self._refresh_timer.stop(); self._buttons(True); self.invalidate()
            self.set_status("Cleaning up subscription and disconnecting device…"); self.shutdown_requested.emit()
        event.ignore()

    @Slot()
    def _finish_close(self) -> None:
        self._allow_close = True; QTimer.singleShot(0, self.close)

def main() -> int:
    app = QApplication([sys.argv[0]])
    window = TactileExampleWindow("GHand5", "ETHERCAT", "auto")
    signal.signal(signal.SIGINT, lambda *_: window.close())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
