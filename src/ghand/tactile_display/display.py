# SPDX-FileCopyrightText: 2026 GLITech
# SPDX-License-Identifier: Apache-2.0
"""Device operations and lifecycle for the tactile display."""

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from ghand import GHand, HandType
from .window import TactileWindow


class _SdkWorker(QObject):
    connected = Signal(bool, str)
    detected_side = Signal(str)
    command_finished = Signal(str, bool, str)
    shutdown_finished = Signal()

    def __init__(self, hand: GHand, display: TactileWindow) -> None:
        super().__init__()
        self.hand = hand
        self.display = display
        self.subscription_id = None
        self.tactile_opened = False

    @Slot()
    def initialize(self) -> None:
        try:
            ok = self.hand.is_connected()
            message = "Device connected" if ok else "Device not connected"
            if ok:
                hand_type = self.hand.get_hand_type()
                if hand_type == HandType.LEFT_HAND:
                    self.detected_side.emit("left")
                elif hand_type == HandType.RIGHT_HAND:
                    self.detected_side.emit("right")
            self.connected.emit(ok, message)
        except Exception as exc:
            self.connected.emit(False, f"Device initialization failed: {exc}")

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
            try:
                self._unsubscribe()
            finally:
                if self.tactile_opened:
                    self.hand.tactile_close()
        except Exception as exc:
            self.command_finished.emit("close", False, f"Tactile cleanup failed: {exc}")
        finally:
            self.shutdown_finished.emit()

    def _subscribe(self, generation: int) -> None:
        self.subscription_id = self.hand.subscribe(
            lambda data: self.display.update_tactile(getattr(data, "tactile", None), generation),
            interval_ms=20)

    def _unsubscribe(self) -> None:
        if self.subscription_id is not None:
            self.hand.unsubscribe(self.subscription_id); self.subscription_id = None


class TactileDisplay(TactileWindow):
    """Display and control tactile data for a connected, caller-owned GHand.

    Closing the window stops its subscription and closes tactile sensors.
    The caller remains responsible for closing the device connection.
    """
    shutdown_requested = Signal()

    def __init__(self, hand: GHand, side: str = "right") -> None:
        super().__init__(side)
        self.hand = hand
        self._closing = self._allow_close = False
        self._thread = self._worker = None
        self._start_worker()

    def _start_worker(self) -> None:
        self._buttons(True); self._thread = QThread(self)
        self._worker = _SdkWorker(self.hand, self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.initialize); self.open_requested.connect(self._worker.open_tactile)
        self.close_requested.connect(self._worker.close_tactile); self.zero_requested.connect(self._worker.zero_tactile)
        self.shutdown_requested.connect(self._worker.shutdown); self._worker.connected.connect(self.set_connected)
        self._worker.detected_side.connect(self.set_side)
        self._worker.command_finished.connect(self.set_command_result)
        self._thread.finished.connect(self._worker.deleteLater)
        self._worker.shutdown_finished.connect(self._thread.quit); self._thread.finished.connect(self._finish_close)
        self.set_status("Initializing tactile display..."); self._thread.start()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._allow_close:
            super().closeEvent(event); return
        if not self._closing:
            self._closing = True; self._refresh_timer.stop(); self._buttons(True); self.invalidate()
            self.set_status("Cleaning up tactile subscription..."); self.shutdown_requested.emit()
        event.ignore()

    @Slot()
    def _finish_close(self) -> None:
        self._allow_close = True; QTimer.singleShot(0, self.close)

