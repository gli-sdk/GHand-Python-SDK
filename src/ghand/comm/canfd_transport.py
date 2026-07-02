# Copyright 2026 GLITech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CANFD transport layer wrapping ZLG USB-CANFD devices.

Handles arbitration-field packing, segmented transfer, and register-level
read/write over CANFD frames.  The ZLG ``zlgcan.dll`` is loaded via
``ctypes`` on Windows.
"""

from __future__ import annotations

import ctypes
import logging
import os
import platform
import struct
import threading
import time
from pathlib import Path
from typing import Callable, Literal

logger = logging.getLogger("ghand.canfd_transport")

# ---------------------------------------------------------------------------
# ZLG ctypes structures (mirrored from zlgcan.py)
# ---------------------------------------------------------------------------

ZCAN_STATUS_OK = 1
ZCAN_TYPE_CANFD = ctypes.c_uint(1)


class _ZCAN_CHANNEL_CANFD_INIT_CONFIG(ctypes.Structure):
    _fields_ = [
        ("acc_code", ctypes.c_uint),
        ("acc_mask", ctypes.c_uint),
        ("abit_timing", ctypes.c_uint),
        ("dbit_timing", ctypes.c_uint),
        ("brp", ctypes.c_uint),
        ("filter", ctypes.c_ubyte),
        ("mode", ctypes.c_ubyte),
        ("pad", ctypes.c_ushort),
        ("reserved", ctypes.c_uint),
    ]


class _ZCAN_CHANNEL_INIT_CONFIG(ctypes.Union):
    _fields_ = [("canfd", _ZCAN_CHANNEL_CANFD_INIT_CONFIG)]


class ZCAN_CHANNEL_INIT_CONFIG(ctypes.Structure):
    _fields_ = [("can_type", ctypes.c_uint), ("config", _ZCAN_CHANNEL_INIT_CONFIG)]


class ZCAN_CANFD_FRAME(ctypes.Structure):
    _fields_ = [
        ("can_id", ctypes.c_uint, 29),
        ("err", ctypes.c_uint, 1),
        ("rtr", ctypes.c_uint, 1),
        ("eff", ctypes.c_uint, 1),
        ("len", ctypes.c_ubyte),
        ("brs", ctypes.c_ubyte, 1),
        ("esi", ctypes.c_ubyte, 1),
        ("__res", ctypes.c_ubyte, 6),
        ("__res0", ctypes.c_ubyte),
        ("__res1", ctypes.c_ubyte),
        ("data", ctypes.c_ubyte * 64),
    ]


class ZCAN_TransmitFD_Data(ctypes.Structure):
    _fields_ = [("frame", ZCAN_CANFD_FRAME), ("transmit_type", ctypes.c_uint)]


class ZCAN_ReceiveFD_Data(ctypes.Structure):
    _fields_ = [("frame", ZCAN_CANFD_FRAME), ("timestamp", ctypes.c_ulonglong)]


# ---------------------------------------------------------------------------
# Arbitration helpers
# ---------------------------------------------------------------------------


def pack_arbitration(
    src_id: int,
    dst_id: int,
    ack: int,
    func_code: int,
    start: int = 1,
    end: int = 1,
    toggle: int = 0,
    seg_num: int = 0,
) -> int:
    """Pack CANFD extended-frame arbitration field (29 bits)."""
    return (
        (src_id & 0x3F) << 23
        | (dst_id & 0x3F) << 17
        | (ack & 0x01) << 16
        | (func_code & 0xFF) << 8
        | (start & 0x01) << 7
        | (end & 0x01) << 6
        | (toggle & 0x01) << 5
        | (seg_num & 0x1F)
    )


def unpack_arbitration(can_id: int) -> dict:
    """Unpack 29-bit arbitration field."""
    return {
        "src_id": (can_id >> 23) & 0x3F,
        "dst_id": (can_id >> 17) & 0x3F,
        "ack": (can_id >> 16) & 0x01,
        "func_code": (can_id >> 8) & 0xFF,
        "start": (can_id >> 7) & 0x01,
        "end": (can_id >> 6) & 0x01,
        "toggle": (can_id >> 5) & 0x01,
        "seg_num": can_id & 0x1F,
    }


# ---------------------------------------------------------------------------
# Transport class
# ---------------------------------------------------------------------------


class CanfdTransport:
    """Low-level CANFD transport using ZLG USB-CANFD adapters."""

    # Common ZLG device types
    ZCAN_USBCANFD_100U = 42
    ZCAN_USBCANFD_200U = 41
    ZCAN_USBCANFD_400U = 201
    ZCAN_USBCANFD_MINI = 43

    @staticmethod
    def _resolve_dll_path(user_path: str | None) -> str:
        """Resolve the path to zlgcan.dll.

        Search order:
        1. User-provided path
        2. ``ZLG_DLL_PATH`` environment variable
        3. Project directory ``drivers/zlgcan/zlgcan.dll``
        4. Current working directory ``./zlgcan.dll``
        """
        if user_path is not None:
            return user_path

        env_path = os.environ.get("ZLG_DLL_PATH")
        if env_path:
            return env_path

        # Project bundled driver path: try importlib.resources first, then fallback
        try:
            import importlib.resources as resources
            with resources.path("ghand.drivers.zlgcan", "zlgcan.dll") as p:
                if p.exists():
                    return str(p)
        except (ImportError, ModuleNotFoundError, FileNotFoundError):
            pass

        # Fallback: 4 levels up from this file -> project root (source mode)
        project_dll = (
            Path(__file__).resolve().parents[3] / "drivers" / "zlgcan" / "zlgcan.dll"
        )
        if project_dll.exists():
            return str(project_dll)

        return "./zlgcan.dll"

    def __init__(
        self,
        device_type: int = ZCAN_USBCANFD_100U,
        device_index: int = 0,
        can_index: int = 0,
        dll_path: str | None = None,
    ):
        self._device_type = device_type
        self._device_index = device_index
        self._can_index = can_index
        self._dll: ctypes.CDLL | None = None
        self._dev_handle = 0
        self._chn_handle = 0
        self._lock = threading.Lock()
        self._dll_path: str | None = None
        self._user_dll_path: str | None = dll_path

        if platform.system() != "Windows":
            raise OSError("ZLG CANFD is only supported on Windows")

    def _load_dll(self) -> None:
        """Lazy-load the ZLG CANFD DLL."""
        if self._dll is not None:
            return
        dll = self._resolve_dll_path(self._user_dll_path)
        try:
            self._dll = ctypes.windll.LoadLibrary(dll)
        except OSError as exc:
            raise OSError(
                f"Failed to load zlgcan.dll from {dll}. "
                "Ensure the ZLG CAN driver is installed. "
                f"Place zlgcan.dll and kerneldlls/ in '{Path(__file__).resolve().parents[3] / 'drivers' / 'zlgcan'}' "
                "or set the ZLG_DLL_PATH environment variable."
            ) from exc

    # ------------------------------------------------------------------
    # Device lifecycle
    # ------------------------------------------------------------------

    def open(self, abit_baud: int = 1_000_000, dbit_baud: int = 5_000_000) -> bool:
        """Open the ZLG device and start the CAN channel."""
        if self._dev_handle:
            return True

        self._load_dll()

        self._dll.ZCAN_OpenDevice.restype = ctypes.c_longlong
        self._dev_handle = self._dll.ZCAN_OpenDevice(
            ctypes.c_uint(self._device_type),
            ctypes.c_uint(self._device_index),
            ctypes.c_uint(0),
        )
        if not self._dev_handle:
            logger.error("ZCAN_OpenDevice failed")
            return False

        # Configure baud rates via property interface
        dev_h = ctypes.c_ulonglong(self._dev_handle)
        self._dll.ZCAN_SetValue.restype = ctypes.c_longlong
        self._dll.ZCAN_SetValue(
            dev_h,
            ctypes.c_char_p(b"0/canfd_standard"),
            ctypes.c_char_p(b"0"),
        )
        self._dll.ZCAN_SetValue(
            dev_h,
            ctypes.c_char_p(b"0/canfd_abit_baud_rate"),
            ctypes.c_char_p(f"{abit_baud},75".encode()),
        )
        self._dll.ZCAN_SetValue(
            dev_h,
            ctypes.c_char_p(b"0/canfd_dbit_baud_rate"),
            ctypes.c_char_p(f"{dbit_baud},75".encode()),
        )
        self._dll.ZCAN_SetValue(
            dev_h,
            ctypes.c_char_p(b"0/filter_clear"),
            ctypes.c_char_p(b"0"),
        )

        cfg = ZCAN_CHANNEL_INIT_CONFIG()
        cfg.can_type = ZCAN_TYPE_CANFD
        cfg.config.canfd.filter = 0
        cfg.config.canfd.acc_code = 0
        cfg.config.canfd.acc_mask = 0xFFFFFFFF
        cfg.config.canfd.mode = 0

        self._dll.ZCAN_InitCAN.restype = ctypes.c_longlong
        self._chn_handle = self._dll.ZCAN_InitCAN(
            ctypes.c_longlong(self._dev_handle),
            ctypes.c_uint(self._can_index),
            ctypes.byref(cfg),
        )
        if not self._chn_handle:
            logger.error("ZCAN_InitCAN failed")
            self._dll.ZCAN_CloseDevice(ctypes.c_longlong(self._dev_handle))
            self._dev_handle = 0
            return False

        self._dll.ZCAN_StartCAN.restype = ctypes.c_longlong
        ret = self._dll.ZCAN_StartCAN(ctypes.c_ulonglong(self._chn_handle))
        if ret != ZCAN_STATUS_OK:
            logger.error("ZCAN_StartCAN failed: %s", ret)
            self._dll.ZCAN_ResetCAN(ctypes.c_ulonglong(self._chn_handle))
            self._dll.ZCAN_CloseDevice(ctypes.c_longlong(self._dev_handle))
            self._chn_handle = 0
            self._dev_handle = 0
            return False

        logger.info("CANFD channel opened (abit=%s, dbit=%s)", abit_baud, dbit_baud)
        return True

    def close(self) -> bool:
        """Stop the channel and close the device."""
        if self._chn_handle:
            self._dll.ZCAN_ResetCAN(ctypes.c_ulonglong(self._chn_handle))
            self._chn_handle = 0
        if self._dev_handle:
            self._dll.ZCAN_CloseDevice(ctypes.c_longlong(self._dev_handle))
            self._dev_handle = 0
        logger.info("CANFD channel closed")
        return True

    # ------------------------------------------------------------------
    # Raw frame I/O
    # ------------------------------------------------------------------

    # CANFD valid data lengths (DLC mapping)
    _CANFD_LENGTHS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64)

    def send_frame(self, can_id: int, data: bytes) -> bool:
        """Transmit a single CANFD frame."""
        if not self._chn_handle:
            return False

        # Pad data to nearest valid CANFD length
        length = len(data)
        for valid_len in self._CANFD_LENGTHS:
            if valid_len >= length:
                length = valid_len
                break

        msg = ZCAN_TransmitFD_Data()
        msg.transmit_type = 0
        msg.frame.eff = 1
        msg.frame.rtr = 0
        msg.frame.brs = 1
        msg.frame.can_id = can_id
        msg.frame.len = length
        for i in range(length):
            msg.frame.data[i] = data[i] if i < len(data) else 0

        handle = ctypes.c_ulonglong(self._chn_handle)
        ret = self._dll.ZCAN_TransmitFD(handle, ctypes.byref(msg), 1)
        return ret == 1

    def recv_frame(self, timeout_ms: int = 100) -> tuple[int, bytes] | None:
        """Receive a single CANFD frame (blocking up to *timeout_ms*)."""
        if not self._chn_handle:
            return None

        handle = ctypes.c_ulonglong(self._chn_handle)
        rcv = ZCAN_ReceiveFD_Data()
        ret = self._dll.ZCAN_ReceiveFD(handle, ctypes.byref(rcv), 1, ctypes.c_int(timeout_ms))
        if ret <= 0:
            return None

        data = bytes(rcv.frame.data[: rcv.frame.len])
        return rcv.frame.can_id, data

    def recv_frames(self, max_frames: int = 100, timeout_ms: int = 100) -> list[tuple[int, bytes]]:
        """Receive up to *max_frames* CANFD frames."""
        if not self._chn_handle:
            return []

        handle = ctypes.c_ulonglong(self._chn_handle)
        buf = (ZCAN_ReceiveFD_Data * max_frames)()
        ret = self._dll.ZCAN_ReceiveFD(handle, ctypes.byref(buf), max_frames, ctypes.c_int(timeout_ms))
        if ret <= 0:
            return []

        results = []
        for i in range(ret):
            frame = buf[i].frame
            data = bytes(frame.data[: frame.len])
            results.append((frame.can_id, data))
        return results

    # ------------------------------------------------------------------
    # Segmented register transfer
    # ------------------------------------------------------------------

    def read_registers(
        self,
        src_id: int,
        dst_id: int,
        addr: int,
        count: int,
        func_code: int = 0x03,
        timeout_ms: int = 500,
    ) -> bytes:
        """Read *count* registers starting at *addr*.

        Automatically handles multi-frame segmented responses.
        """
        # Command frame data field: AddrHi, AddrLo, CountHi, CountLo
        cmd_data = struct.pack(">HH", addr, count)
        can_id = pack_arbitration(src_id, dst_id, ack=0, func_code=func_code)

        with self._lock:
            if not self.send_frame(can_id, cmd_data):
                raise ConnectionError("Failed to send read command frame")

            # Gather response segments
            segments: dict[int, bytes] = {}
            start_time = time.time()
            while True:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms >= timeout_ms:
                    raise TimeoutError("Segmented read timeout")

                remaining = int(timeout_ms - elapsed_ms)
                result = self.recv_frame(timeout_ms=max(remaining, 10))
                if result is None:
                    continue

                resp_id, resp_data = result
                arb = unpack_arbitration(resp_id)

                # Filter: must be a response to us from the target
                if arb["ack"] != 1:
                    continue
                if arb["dst_id"] != src_id:
                    continue
                if arb["src_id"] != dst_id:
                    continue

                # Exception response?
                if arb["func_code"] == 0x80 | func_code:
                    error_code = resp_data[0] if resp_data else 0xFF
                    raise RuntimeError(f"Modbus exception: {error_code:#x}")

                if arb["func_code"] != func_code:
                    continue

                # Single-frame response (strip Modbus byte-count prefix)
                if arb["start"] == 1 and arb["end"] == 1:
                    payload = resp_data[1:] if resp_data else resp_data
                    return payload[: count * 2]

                # Multi-frame response: first segment carries byte-count prefix
                seg_num = arb["seg_num"]
                if seg_num == 0 and resp_data:
                    resp_data = resp_data[1:]
                segments[seg_num] = resp_data
                if arb["end"] == 1:
                    break

            # Reassemble
            assembled = b"".join(segments[i] for i in sorted(segments))
            return assembled[: count * 2]

    def write_registers(
        self,
        src_id: int,
        dst_id: int,
        addr: int,
        data: bytes,
        timeout_ms: int = 5000,
    ) -> bool:
        """Write register data starting at *addr*.

        Automatically selects function code 0x06 for a single register (2 bytes)
        and 0x10 for multiple registers.  Multi-frame segmented transmission is
        used when the payload exceeds 64 bytes.
        """
        if len(data) == 2:
            # Single register write (function code 0x06)
            func_code = 0x06
            payload = struct.pack(">HH", addr, struct.unpack(">H", data)[0])
        else:
            # Multiple register write (function code 0x10)
            func_code = 0x10
            count = len(data) // 2
            payload = struct.pack(">HHB", addr, count, len(data)) + data

        with self._lock:
            # Segmented transmit (single-frame payload is just one segment)
            seg_size = 64
            num_segs = (len(payload) + seg_size - 1) // seg_size
            for seg_idx in range(num_segs):
                start = seg_idx == 0
                end = seg_idx == num_segs - 1
                toggle = seg_idx % 2
                seg_data = payload[seg_idx * seg_size : (seg_idx + 1) * seg_size]

                can_id = pack_arbitration(
                    src_id, dst_id, ack=0, func_code=func_code,
                    start=int(start), end=int(end), toggle=toggle, seg_num=seg_idx,
                )
                if not self.send_frame(can_id, seg_data):
                    raise ConnectionError(f"Failed to send write segment {seg_idx}")

            # Wait for single-frame response
            start_time = time.time()
            while True:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms >= timeout_ms:
                    raise TimeoutError("Write response timeout")

                remaining = int(timeout_ms - elapsed_ms)
                result = self.recv_frame(timeout_ms=max(remaining, 10))
                if result is None:
                    continue

                resp_id, resp_data = result
                arb = unpack_arbitration(resp_id)
                if arb["ack"] != 1 or arb["dst_id"] != src_id or arb["src_id"] != dst_id:
                    continue

                if arb["func_code"] == 0x80 | func_code:
                    error_code = resp_data[0] if resp_data else 0xFF
                    raise RuntimeError(f"Modbus exception: {error_code:#x}")

                if arb["func_code"] == func_code and arb["start"] == 1 and arb["end"] == 1:
                    return True
