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

"""CANFD transport layer wrapping CANFD devices.

Handles arbitration-field packing, segmented transfer, and register-level
read/write over CANFD frames. On Windows the ZLG ``zlgcan.dll`` is loaded via
``ctypes``; on Linux SocketCAN is used directly.
"""

from __future__ import annotations

import ctypes
import logging
import os
import platform
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Callable, Literal

try:
    import serial
except ImportError:
    serial = None  # type: ignore[assignment]

logger = logging.getLogger("ghand.canfd_transport")

CAN_EFF_FLAG = 0x80000000
CAN_RAW_FD_FRAMES = 5
CANFD_BRS = 0x01
CAN_FRAME_FORMAT = "=IB3x8s"
CAN_FRAME_SIZE = struct.calcsize(CAN_FRAME_FORMAT)
CANFD_FRAME_FORMAT = "=IBB2x64s"
CANFD_FRAME_SIZE = struct.calcsize(CANFD_FRAME_FORMAT)

ZQWL_CONFIG_HEAD = b"\x49\x3B"
ZQWL_CONFIG_TAIL = b"\x45\x2E"
ZQWL_CANFD_HEAD = 0x5A
ZQWL_CANFD_TAIL = 0xA5
ZQWL_HEARTBEAT_1_2_CHANNEL = 0xFF
ZQWL_HEARTBEAT_4_CHANNEL = 0xFE
ZQWL_DEFAULT_SERIAL_BAUDRATE = 2_000_000
ZQWL_COMMON_BITRATE_CODES = {
    1_000_000: 0x0,
    800_000: 0x1,
    500_000: 0x2,
    400_000: 0x3,
    250_000: 0x4,
    200_000: 0x5,
    125_000: 0x6,
    100_000: 0x7,
    50_000: 0x8,
    40_000: 0x9,
    25_000: 0xA,
    20_000: 0xB,
    15_000: 0xC,
    10_000: 0xD,
    5_000: 0xE,
}
ZQWL_COMMON_DBITRATE_CODES = {
    5_000_000: 0x0,
    4_000_000: 0x1,
    2_000_000: 0x2,
    1_000_000: 0x3,
    800_000: 0x4,
    500_000: 0x5,
    400_000: 0x6,
    250_000: 0x7,
    200_000: 0x8,
    125_000: 0x9,
    100_000: 0xA,
}

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


def _unpack_socketcan_frame(frame: bytes) -> tuple[int, bytes] | None:
    """Unpack either a CAN FD or classic CAN frame from a SocketCAN socket."""
    if len(frame) == CANFD_FRAME_SIZE:
        can_id, length, _flags, data = struct.unpack(CANFD_FRAME_FORMAT, frame)
        return can_id & 0x1FFFFFFF, data[:length]
    if len(frame) == CAN_FRAME_SIZE:
        can_id, length, data = struct.unpack(CAN_FRAME_FORMAT, frame)
        return can_id & 0x1FFFFFFF, data[:length]
    logger.debug("Ignored unexpected SocketCAN frame size: %s", len(frame))
    return None


def _zqwl_dlc_to_length(dlc: int) -> int | None:
    """Translate ZQWL CANFD DLC byte value to payload length."""
    if 0 <= dlc <= 8:
        return dlc
    if dlc in (12, 16, 20, 24, 32, 48, 64):
        return dlc
    return None


# ---------------------------------------------------------------------------
# Transport class
# ---------------------------------------------------------------------------


class CanfdTransport:
    """Low-level CANFD transport using ZLG on Windows or SocketCAN on Linux."""

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
        channel: str = "can0",
    ):
        self._device_type = device_type
        self._device_index = device_index
        self._can_index = can_index
        self._channel = channel
        self._backend = "zlg" if platform.system() == "Windows" else "socketcan"
        self._dll: ctypes.CDLL | None = None
        self._dev_handle = 0
        self._chn_handle = 0
        self._sock: socket.socket | None = None
        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()
        self._dll_path: str | None = None
        self._user_dll_path: str | None = dll_path

        if platform.system() == "Linux" and channel.startswith("/dev/"):
            self._backend = "zqwl_serial"
        if self._backend != "zlg" and platform.system() != "Linux":
            raise OSError("CANFD is supported on Windows (ZLG) and Linux")

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
        """Open the CANFD device and start the CAN channel."""
        if self._backend == "zqwl_serial":
            return self._open_zqwl_serial(abit_baud=abit_baud, dbit_baud=dbit_baud)
        if self._backend == "socketcan":
            return self._open_socketcan(abit_baud=abit_baud, dbit_baud=dbit_baud)

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

    def _open_socketcan(self, abit_baud: int, dbit_baud: int) -> bool:
        """Open a Linux SocketCAN CAN FD network interface."""
        if self._sock is not None:
            return True
        try:
            sock = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
            sock.setsockopt(socket.SOL_CAN_RAW, CAN_RAW_FD_FRAMES, 1)
            sock.settimeout(0.1)
            sock.bind((self._channel,))
            self._sock = sock
            logger.info(
                "SocketCAN CANFD channel opened (%s, abit=%s, dbit=%s)",
                self._channel,
                abit_baud,
                dbit_baud,
            )
            return True
        except OSError as exc:
            logger.error(
                "Failed to open SocketCAN interface %s: %s. "
                "Ensure the interface exists and is configured for CAN FD, for example: "
                "ip link set %s up type can bitrate %s dbitrate %s fd on",
                self._channel,
                exc,
                self._channel,
                abit_baud,
                dbit_baud,
            )
            self._sock = None
            return False

    def _open_zqwl_serial(self, abit_baud: int, dbit_baud: int) -> bool:
        """Open a ZQWL USBCANFD CDC serial adapter."""
        if self._serial is not None:
            return True
        if serial is None:
            logger.error("pyserial not available, cannot open ZQWL CANFD adapter")
            return False

        try:
            ser = serial.Serial(
                port=self._channel,
                baudrate=int(os.environ.get("ZQWL_CANFD_SERIAL_BAUDRATE", ZQWL_DEFAULT_SERIAL_BAUDRATE)),
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=0.02,
                write_timeout=1.0,
            )
            self._serial = ser
            self._configure_zqwl_channel(abit_baud=abit_baud, dbit_baud=dbit_baud)
            logger.info(
                "ZQWL CANFD serial channel opened (%s, abit=%s, dbit=%s)",
                self._channel,
                abit_baud,
                dbit_baud,
            )
            return True
        except Exception as exc:
            logger.error("Failed to open ZQWL CANFD serial adapter %s: %s", self._channel, exc)
            if self._serial is not None:
                self._serial.close()
                self._serial = None
            return False

    def _write_zqwl_config(self, func_code: int, write: bool, data: bytes = b"") -> None:
        """Write one 22-byte ZQWL configuration command."""
        if self._serial is None:
            raise RuntimeError("ZQWL serial adapter not open")
        payload = data[:16].ljust(16, b"\x00")
        cmd = (
            ZQWL_CONFIG_HEAD
            + bytes([func_code & 0xFF, 0x57 if write else 0x52])
            + payload
            + ZQWL_CONFIG_TAIL
        )
        self._serial.write(cmd)
        self._serial.flush()

    def _configure_zqwl_channel(self, abit_baud: int, dbit_baud: int) -> None:
        """Configure CAN0 for common CANFD 1M/5M style operation."""
        abit_code = ZQWL_COMMON_BITRATE_CODES.get(abit_baud)
        dbit_code = ZQWL_COMMON_DBITRATE_CODES.get(dbit_baud)
        if abit_code is None or dbit_code is None:
            raise ValueError(
                f"Unsupported ZQWL common bitrate pair: abit={abit_baud}, dbit={dbit_baud}"
            )

        bitrate_code = ((abit_code & 0x0F) << 4) | (dbit_code & 0x0F)
        # Function 0x42: CAN parameter; data[0]=CAN channel, data[1]=custom flag,
        # data[2]=common arbitration/data bitrate code.
        self._write_zqwl_config(0x42, True, bytes([self._can_index & 0xFF, 0x00, bitrate_code]))
        # Function 0x44: apply parameters and open CAN0/CAN1.
        control = bytearray(16)
        control[0] = 0x01
        if self._can_index == 0:
            control[2] = 0x01
        elif self._can_index == 1:
            control[3] = 0x01
        else:
            raise ValueError("ZQWL serial backend currently supports CAN0/CAN1")
        self._write_zqwl_config(0x44, True, bytes(control))

    def close(self) -> bool:
        """Stop the channel and close the device."""
        if self._serial is not None:
            self._serial.close()
            self._serial = None
            logger.info("ZQWL CANFD serial channel closed")
            return True
        if self._sock is not None:
            self._sock.close()
            self._sock = None
            logger.info("SocketCAN CANFD channel closed")
            return True

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
        if self._serial is not None:
            if len(data) > 64:
                raise ValueError("CANFD frame payload cannot exceed 64 bytes")
            info1 = len(data) & 0x7F
            info1 |= (self._can_index & 0x01) << 7
            info2 = 0x01  # BRS enabled
            info2 |= ((self._can_index >> 1) & 0x03) << 3
            info2 |= 0x04  # Extended frame
            frame_id = (can_id & 0x1FFFFFFF) | 0x80000000  # CANFD protocol flag
            frame = (
                bytes([ZQWL_CANFD_HEAD, info1, info2])
                + frame_id.to_bytes(4, "big")
                + data
                + bytes([ZQWL_CANFD_TAIL])
            )
            try:
                logger.debug(
                    "Sending ZQWL frame id=%#x info1=%#x info2=%#x data=%s",
                    frame_id,
                    info1,
                    info2,
                    data.hex(" "),
                )
                self._serial.write(frame)
                self._serial.flush()
                return True
            except Exception as exc:
                logger.error("ZQWL CANFD serial transmit failed: %s", exc)
                return False

        if self._sock is not None:
            if len(data) > 64:
                raise ValueError("CANFD frame payload cannot exceed 64 bytes")
            frame = struct.pack(
                CANFD_FRAME_FORMAT,
                can_id | CAN_EFF_FLAG,
                len(data),
                CANFD_BRS,
                data.ljust(64, b"\x00"),
            )
            try:
                return self._sock.send(frame) == CANFD_FRAME_SIZE
            except OSError as exc:
                logger.error("SocketCAN transmit failed: %s", exc)
                return False

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
        if self._serial is not None:
            return self._recv_zqwl_frame(timeout_ms=timeout_ms)

        if self._sock is not None:
            self._sock.settimeout(timeout_ms / 1000)
            try:
                frame = self._sock.recv(CANFD_FRAME_SIZE)
            except socket.timeout:
                return None
            except OSError as exc:
                logger.error("SocketCAN receive failed: %s", exc)
                return None
            return _unpack_socketcan_frame(frame)

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
        if self._serial is not None:
            results = []
            deadline = time.time() + timeout_ms / 1000
            while len(results) < max_frames:
                remaining_ms = int((deadline - time.time()) * 1000)
                if remaining_ms <= 0:
                    break
                parsed = self._recv_zqwl_frame(timeout_ms=remaining_ms)
                if parsed is not None:
                    results.append(parsed)
            return results

        if self._sock is not None:
            results = []
            deadline = time.time() + timeout_ms / 1000
            while len(results) < max_frames:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._sock.settimeout(remaining)
                try:
                    frame = self._sock.recv(CANFD_FRAME_SIZE)
                except socket.timeout:
                    break
                except OSError as exc:
                    logger.error("SocketCAN receive failed: %s", exc)
                    break
                parsed = _unpack_socketcan_frame(frame)
                if parsed is not None:
                    results.append(parsed)
            return results

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

    def _recv_zqwl_frame(self, timeout_ms: int = 100) -> tuple[int, bytes] | None:
        """Receive one CANFD data frame from a ZQWL serial adapter."""
        if self._serial is None:
            return None

        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            b = self._serial.read(1)
            if not b:
                continue
            first = b[0]
            if first != ZQWL_CANFD_HEAD:
                continue

            info1_raw = self._serial.read(1)
            if not info1_raw:
                continue
            info1 = info1_raw[0]
            if info1 in (ZQWL_HEARTBEAT_1_2_CHANNEL, ZQWL_HEARTBEAT_4_CHANNEL):
                heartbeat_len = 15 if info1 == ZQWL_HEARTBEAT_1_2_CHANNEL else 30
                heartbeat = self._serial.read(heartbeat_len)
                logger.debug("Ignored ZQWL heartbeat: %s", heartbeat.hex(" "))
                continue

            info2_id = self._serial.read(5)
            if len(info2_id) != 5:
                continue
            info2 = info2_id[0]
            length = _zqwl_dlc_to_length(info1 & 0x7F)
            if length is None:
                logger.debug("Ignored ZQWL frame with invalid DLC: %s", info1 & 0x7F)
                continue

            payload_tail = self._serial.read(length + 1)
            if len(payload_tail) != length + 1:
                continue
            if payload_tail[-1] != ZQWL_CANFD_TAIL:
                logger.debug("Ignored ZQWL frame with invalid tail")
                continue

            frame_id = int.from_bytes(info2_id[1:5], "big")
            is_canfd = (frame_id & 0x80000000) != 0
            is_extended = (info2 & 0x04) != 0
            logger.debug(
                "Received ZQWL frame id=%#x info1=%#x info2=%#x len=%s data=%s",
                frame_id,
                info1,
                info2,
                length,
                payload_tail[:-1].hex(" "),
            )
            if not is_canfd or not is_extended:
                continue
            return frame_id & 0x1FFFFFFF, payload_tail[:-1]
        return None

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
