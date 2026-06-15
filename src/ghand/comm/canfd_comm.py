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

"""CANFD communication implementation.

Wraps CanfdTransport and handles CANFD-specific connection state machine
(Node ID detection, connection establishment, keep-alive) and register-level
business APIs.
"""

from __future__ import annotations

import logging
import struct
import threading
import time
from pathlib import Path
from typing import Any

from ..types import (
    CtrlMode,
    ErrorCode,
    HandState,
    JointData,
    JointId,
    ProductConfig,
    State,
    TactileInfo,
)
from .canfd_transport import CanfdTransport, pack_arbitration, unpack_arbitration
from .icomm import IComm
from .modbus_codec import (
    HOLDING_REG_MAP,
    build_tactile_info,
    encode_joint_command,
    parse_device_name,
    parse_firmware_version,
    parse_hand_info,
    parse_hand_type,
    parse_hardware_version,
    parse_joint_data,
    parse_joints,
    parse_serial_number,
    parse_tactile_distributed,
    parse_tactile_resultant,
    parse_tactile_state_error,
    registers_to_bytes,
)

logger = logging.getLogger("ghand.canfd_comm")


class CanfdComm(IComm):
    """IComm implementation for CANFD."""

    def __init__(self, config: ProductConfig):
        self._config = config
        self._transport: CanfdTransport | None = None
        self._src_id = 0x0A  # master node id
        self._dst_id = 0x31  # slave node id (default)
        self._connected = False
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()
        self._callbacks: dict[int, tuple] = {}
        self._next_sub_id = 1
        self._lock = threading.Lock()

    def update_config(self, config: ProductConfig) -> None:
        """Update the cached product configuration."""
        self._config = config

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def search_adapters(self) -> list[str]:
        """Search for available ZLG CANFD adapters.

        Returns:
            List of adapter identifiers in the form "zlg-<dev_type>-<index>".
        """
        adapters: list[str] = []
        try:
            dll_path = CanfdTransport._resolve_dll_path("./drivers/zlgcan/zlgcan.dll")
            if Path(dll_path).exists():
                adapters.append("zlg-USBCANFD-100U-0")
            else:
                logger.warning("ZLG CANFD driver not found: %s", dll_path)
        except Exception as e:
            logger.error("Failed to detect ZLG CANFD adapter: %s", e)
        return adapters

    def connect(self, device_name: str) -> bool:
        """Connect to the specified CANFD device.

        Internally performs the full CANFD connection handshake:
        open device → init channel → Node ID detection → establish connection.

        Args:
            device_name: Adapter identifier (e.g. "zlg-USBCANFD-100U-0").

        Returns:
            True if the connection and handshake succeed.
        """
        try:
            if self._transport is None:
                self._transport = CanfdTransport()

            if not self._transport.open():
                logger.error("Failed to open CANFD transport")
                return False

            # # Listen for slave-initiated Node ID detection before establishing connection.
            # if not self._node_id_detection():
            #     logger.error("Node ID detection timeout for dst_id=0x%02X", self._dst_id)
            #     return False

            # Establish connection: function code 0x02, write connection timer=0.
            if not self._establish_connection():
                logger.error("Failed to establish CANFD connection")
                return False

            self._connected = True
            logger.info("CANFD device connected (%s)", device_name)
            return True
        except Exception as exc:
            logger.error("CANFD connect failed: %s", exc)
            if self._transport is not None:
                self._transport.close()
            return False

    def disconnect(self) -> bool:
        """Disconnect from the CANFD device."""
        self._stop_poll()
        self._callbacks.clear()
        if self._connected and self._transport is not None:
            try:
                self._delete_connection()
            except Exception:
                logger.exception("Error during connection deletion")
        if self._transport is not None:
            self._transport.close()
        self._connected = False
        logger.info("CANFD device disconnected")
        return True

    def is_connected(self) -> bool:
        """Return whether the CANFD device is connected."""
        return self._connected

    # ------------------------------------------------------------------
    # CANFD handshake helpers
    # ------------------------------------------------------------------

    def _node_id_detection(self) -> bool:
        """Listen for slave-initiated Node ID detection frames (FC 0x09).

        The slave actively broadcasts its Node ID upon startup.
        The master listens for these broadcasts to confirm device presence.
        """
        deadline = time.time() + 0.5  # 500ms listening window
        while time.time() < deadline:
            result = self._transport.recv_frame(timeout_ms=50)
            if result is None:
                continue

            resp_id, resp_data = result
            arb = unpack_arbitration(resp_id)

            # Slave-initiated Node ID broadcast: ack=1, func_code=0x09
            if arb["ack"] == 1 and arb["func_code"] == 0x09:
                if resp_data and len(resp_data) >= 1:
                    detected_id = resp_data[0]
                    if detected_id == self._dst_id:
                        logger.info("Detected slave Node ID 0x%02X", detected_id)
                        return True
                    else:
                        logger.debug("Ignored Node ID detection for 0x%02X", detected_id)

        logger.error("Node ID detection timeout for dst_id=0x%02X", self._dst_id)
        return False

    def _establish_connection(self) -> bool:
        """Send connection-establishment frame (FC 0x02), polling node IDs."""
        for dst_id in (0x31, 0x32):
            data = b"\x00\x31\x00\x01\x00\x00"
            can_id = pack_arbitration(
                self._src_id, dst_id, ack=0, func_code=0x02,
                start=1, end=1, toggle=0, seg_num=0,
            )
            self._transport.send_frame(can_id, data)

            # Wait for positive response.
            deadline = time.time() + 0.5
            while time.time() < deadline:
                result = self._transport.recv_frame(timeout_ms=50)
                if result is None:
                    continue
                resp_id, _ = result
                arb = unpack_arbitration(resp_id)
                if arb["ack"] == 1 and arb["dst_id"] == self._src_id and arb["src_id"] == dst_id:
                    if arb["func_code"] == 0x82:
                        break  # Exception: try next dst_id
                    if arb["func_code"] == 0x02:
                        self._dst_id = dst_id
                        return True
        return False

    def _delete_connection(self) -> None:
        """Send connection-deletion frame (FC 0x05)."""
        data = b"\x00\x30\x00\x02\x00\x00\x00\x00"
        can_id = pack_arbitration(
            self._src_id, self._dst_id, ack=0, func_code=0x05,
            start=1, end=1, toggle=0, seg_num=0,
        )
        self._transport.send_frame(can_id, data)

    # ------------------------------------------------------------------
    # Joint control
    # ------------------------------------------------------------------

    def move_joints(self, joints: list, mode: CtrlMode) -> bool:
        """Send joint control commands."""
        # Write mode register (high byte = mode, low byte = 0)
        mode_value = (mode.value << 8) & 0xFF00
        self._transport.write_registers(
            self._src_id, self._dst_id, 0x0010, struct.pack(">H", mode_value)
        )

        for joint in joints:
            joint_id = JointId(joint.id)
            if joint_id not in HOLDING_REG_MAP:
                continue
            base_addr = HOLDING_REG_MAP[joint_id]
            reg0, reg1 = encode_joint_command(joint)
            data = struct.pack(">HH", reg0, reg1)
            self._transport.write_registers(
                self._src_id, self._dst_id, base_addr, data
            )
        return True

    def stop(self) -> bool:
        """Send an immediate stop command."""
        self._transport.write_registers(
            self._src_id, self._dst_id, 0x0010, struct.pack(">H", 0x0001)
        )
        return True

    # ------------------------------------------------------------------
    # State retrieval
    # ------------------------------------------------------------------

    def get_joints(self) -> list:
        """Retrieve the current state of all valid joints."""
        if not self._config.valid_joints:
            return []
        max_id = max(j.value for j in self._config.valid_joints)
        count = (max_id + 1) * 3
        raw_bytes = self._transport.read_registers(
            self._src_id, self._dst_id, 0x1023, count, func_code=0x04
        )
        # Convert bytes back to uint16 register list for the shared codec.
        raw = list(struct.unpack(f">{count}H", raw_bytes[: count * 2]))
        return parse_joints(raw, self._config.valid_joints)

    def get_hand_info(self) -> HandState:
        """Retrieve high-level hand status."""
        raw_bytes = self._transport.read_registers(
            self._src_id, self._dst_id, 0x1021, 2, func_code=0x04
        )
        raw = list(struct.unpack(">2H", raw_bytes[:4]))
        return parse_hand_info(raw)

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data."""
        if not self._config.has_tactile:
            return {}
        # Read state + resultant forces (16 registers from 0x1080)
        raw_bytes = self._transport.read_registers(
            self._src_id, self._dst_id, 0x1080, 16, func_code=0x04
        )
        raw = list(struct.unpack(">16H", raw_bytes[:32]))
        tactile_state, _ = parse_tactile_state_error(raw)

        result = {}
        current_addr = 0x1080 + 16

        for region in self._config.tactile_regions:
            idx = region.id.value
            resultant = parse_tactile_resultant(raw, idx)
            state_bit = (tactile_state & (1 << idx)) != 0

            # Read distributed force for this region
            dist_regs = (region.count * 3 + 1) // 2
            dist_bytes = self._transport.read_registers(
                self._src_id, self._dst_id, current_addr, dist_regs, func_code=0x04
            )
            distributed = parse_tactile_distributed(dist_bytes, region.count)
            current_addr += dist_regs

            result[region.id] = build_tactile_info(
                state_bit, resultant, distributed
            )
        return result

    # ------------------------------------------------------------------
    # Device info reading
    # ------------------------------------------------------------------

    def _read_input_bytes(self, addr: int, count: int) -> bytes:
        """Helper to read input registers and return raw bytes."""
        return self._transport.read_registers(
            self._src_id, self._dst_id, addr, count, func_code=0x04
        )

    def get_device_name(self) -> str:
        return parse_device_name(self._read_input_bytes(0x1000, 8))

    def get_hardware_version(self) -> str:
        return parse_hardware_version(self._read_input_bytes(0x1008, 8))

    def get_firmware_version(self) -> str:
        return parse_firmware_version(self._read_input_bytes(0x1010, 8))

    def get_serial_number(self) -> int:
        return parse_serial_number(self._read_input_bytes(0x1018, 8))

    def get_hand_type(self) -> int:
        return parse_hand_type(self._read_input_bytes(0x1020, 1))

    def get_motor_driver_version(self) -> tuple:
        try:
            raw = self._read_input_bytes(0x2007, 3)
            regs = list(struct.unpack(">3H", raw[:6]))
            return tuple(regs)
        except Exception:
            return (0, 0, 0)

    # ------------------------------------------------------------------
    # Tactile sensor
    # ------------------------------------------------------------------

    def open_tactile(self) -> bool:
        return self._write_tactile_control(0x0100)

    def close_tactile(self) -> bool:
        return self._write_tactile_control(0x0200)

    def zero_tactile(self) -> bool:
        return self._write_tactile_control(0x0400)

    def _write_tactile_control(self, command: int) -> bool:
        self._transport.write_registers(
            self._src_id, self._dst_id, 0x002B, struct.pack(">H", command)
        )
        return True

    # ------------------------------------------------------------------
    # Device operations
    # ------------------------------------------------------------------

    def clear_fault(self) -> bool:
        self._transport.write_registers(
            self._src_id, self._dst_id, 0x0001, struct.pack(">H", 0x0100)
        )
        logger.info("Fault cleared")
        return True

    def init_joint(self) -> bool:
        self._transport.write_registers(
            self._src_id, self._dst_id, 0x0002, struct.pack(">H", 0x0001)
        )
        logger.info("Joint initialization completed")
        return True

    # ------------------------------------------------------------------
    # Subscription (polling-based)
    # ------------------------------------------------------------------

    def subscribe(self, callback, *args, **kwargs) -> int:
        """Subscribe to device data updates.

        The callback receives ``(hand_state, joints, *args, **kwargs)``.

        Args:
            callback: Callable invoked with ``(hand_state, joints)``.

        Returns:
            Subscription ID.
        """
        with self._lock:
            sub_id = self._next_sub_id
            self._next_sub_id += 1
            self._callbacks[sub_id] = (callback, args, kwargs)
            self._ensure_poll_started()
            return sub_id

    def unsubscribe(self, sub_id) -> bool:
        with self._lock:
            if sub_id in self._callbacks:
                del self._callbacks[sub_id]
                if not self._callbacks:
                    self._stop_poll()
                return True
            return False

    def _ensure_poll_started(self) -> None:
        if self._poll_thread is None or not self._poll_thread.is_alive():
            self._poll_stop.clear()
            self._poll_thread = threading.Thread(
                target=self._poll_loop, daemon=True
            )
            self._poll_thread.start()

    def _stop_poll(self) -> None:
        self._poll_stop.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=0.5)
        self._poll_thread = None

    def _poll_loop(self) -> None:
        while not self._poll_stop.is_set():
            try:
                if not self._connected:
                    time.sleep(0.01)
                    continue

                if not self._config.valid_joints:
                    time.sleep(0.01)
                    continue

                max_id = max(j.value for j in self._config.valid_joints)
                count = 2 + (max_id + 1) * 3
                raw_bytes = self._transport.read_registers(
                    self._src_id, self._dst_id, 0x1021, count, func_code=0x04
                )
                raw = list(struct.unpack(f">{count}H", raw_bytes[: count * 2]))
                hand_state = parse_hand_info(raw[:2])
                joints = parse_joints(raw[2:], self._config.valid_joints)

                with self._lock:
                    callbacks = list(self._callbacks.values())

                for cb, cb_args, cb_kwargs in callbacks:
                    try:
                        cb(hand_state, joints, *cb_args, **cb_kwargs)
                    except Exception:
                        logger.exception("Subscription callback error")
            except Exception:
                logger.exception("Poll loop error")

            time.sleep(0.01)
