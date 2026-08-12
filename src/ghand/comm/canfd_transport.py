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
read/write over CANFD frames. ZQWL CDC adapters use a serial backend.
"""

from __future__ import annotations

import logging
import os
import struct
import threading
import time

try:
    import serial
except ImportError:
    serial = None  # type: ignore[assignment]

logger = logging.getLogger("ghand.canfd_transport")

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
ZQWL_CANFD_PAYLOAD_LENGTHS = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64,
)

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


def _zqwl_dlc_to_length(dlc: int) -> int | None:
    """Translate ZQWL CANFD DLC byte value to payload length."""
    if dlc in ZQWL_CANFD_PAYLOAD_LENGTHS:
        return dlc
    return None


def _zqwl_length_to_dlc(length: int) -> int:
    """Return the nearest valid ZQWL CANFD payload length for *length* bytes."""
    for valid_length in ZQWL_CANFD_PAYLOAD_LENGTHS:
        if valid_length >= length:
            return valid_length
    return 64


# ---------------------------------------------------------------------------
# Transport class
# ---------------------------------------------------------------------------


class CanfdTransport:
    """Low-level CANFD transport using ZQWL CDC serial."""

    def __init__(
        self,
        can_index: int = 0,
        channel: str = "",
    ):
        self._can_index = can_index
        self._channel = channel
        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Device lifecycle
    # ------------------------------------------------------------------

    def open(self, abit_baud: int = 1_000_000, dbit_baud: int = 5_000_000) -> bool:
        """Open the CANFD device and start the CAN channel."""
        return self._open_zqwl_serial(abit_baud=abit_baud, dbit_baud=dbit_baud)

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
        logger.info("CANFD channel closed")
        return True

    # ------------------------------------------------------------------
    # Raw frame I/O
    # ------------------------------------------------------------------

    def send_frame(self, can_id: int, data: bytes) -> bool:
        """Transmit a single CANFD frame."""
        if self._serial is not None:
            if len(data) > 64:
                raise ValueError("CANFD frame payload cannot exceed 64 bytes")
            dlc_length = _zqwl_length_to_dlc(len(data))
            payload = data.ljust(dlc_length, b"\x00")
            info1 = dlc_length & 0x7F
            info1 |= (self._can_index & 0x01) << 7
            info2 = 0x01  # BRS enabled
            info2 |= ((self._can_index >> 1) & 0x03) << 3
            info2 |= 0x04  # Extended frame
            frame_id = (can_id & 0x1FFFFFFF) | 0x80000000  # CANFD protocol flag
            frame = (
                bytes([ZQWL_CANFD_HEAD, info1, info2])
                + frame_id.to_bytes(4, "big")
                + payload
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

        return False

    def recv_frame(self, timeout_ms: int = 100) -> tuple[int, bytes] | None:
        """Receive a single CANFD frame (blocking up to *timeout_ms*)."""
        if self._serial is not None:
            return self._recv_zqwl_frame(timeout_ms=timeout_ms)

        return None

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

        return []

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
