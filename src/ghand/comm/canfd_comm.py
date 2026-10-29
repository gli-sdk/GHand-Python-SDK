# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

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
import platform
import struct
import threading
import time
from pathlib import Path
from typing import Any

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None  # type: ignore[assignment]

from .._product_config import ProductConfig
from ..types import (
    CANFDBitTiming,
    RS485BaudRate,
    JointId,
    HandControlMode,
    JointControlState,
    HandData,
    HandRuntimeState,
    JointData,
    TactileData,
)
from .canfd_transport import CanfdTransport, pack_arbitration, unpack_arbitration
from .icomm import IComm
from .modbus_codec import (
    BAUDRATE_CONFIG_REGISTER,
    CONN_STATE_CONNECTED,
    CONN_STATE_ERROR,
    MAILBOX_BUSY,
    MAILBOX_FAILED,
    MAILBOX_INVALID,
    MAILBOX_OK,
    REG_CLEAR_FAULT,
    REG_CONNECTION_CONTROL,
    REG_CONNECTION_STATUS,
    REG_DEVICE_NAME,
    REG_FAULT_CLEAR_STATUS,
    REG_FIRMWARE_VERSION,
    REG_HAND_TYPE,
    REG_IN_FIRMWARE_PACKAGE_VER,
    REG_IN_THUMB_TACTILE_VER,
    REG_IN_FINGER_TACTILE_VER,
    REG_IN_MOTOR_DRV_VER,
    REG_IN_POSITION_SENSOR_VER,
    REG_IN_TACTILE_SENSOR_VER,
    REG_HAND_STATE_MACHINE,
    REG_HOST_CONN_STATE,
    REG_MODIFY_BAUD_STATUS,
    REG_MODIFY_ID_STATUS,
    REG_SERIAL_NUMBER,
    REG_SLAVE_ID,
    REG_TACTILE_CTRL_STATUS,
    build_tactile_info,
    encode_hand_command_frame,
    encode_hand_control,
    encode_joint_mode_stop,
    get_joint_input_span,
    get_modbus_profile,
    parse_device_name,
    parse_hand_info,
    parse_hand_state_machine,
    parse_hand_type,
    parse_ascii_serial_number,
    parse_packed_firmware_version,
    parse_joints,
    parse_tactile_distributed,
    parse_tactile_resultant,
    parse_tactile_state_error,
    registers_to_bytes,
    registers_to_bytes_low_high,
)
# CANFD baud rate gear map per protocol documentation.
# Writing a gear value to BAUDRATE_CONFIG_REGISTER selects both the arbitration
# phase bitrate/data-phase bitrate and their sample points; the new
# configuration takes effect after the next power-up.
CANFD_BAUDRATE_GEAR_MAP: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {
    # gear: ((arbitration_baud, arbitration_sample_point), (data_baud, data_sample_point))
    0x00: ((500_000, 80), (800_000, 80)),
    0x01: ((500_000, 80), (1_000_000, 75)),
    0x02: ((500_000, 80), (2_000_000, 80)),
    0x03: ((500_000, 80), (4_000_000, 80)),
    0x04: ((1_000_000, 75), (1_000_000, 75)),
    0x05: ((1_000_000, 75), (2_000_000, 80)),
    0x06: ((1_000_000, 75), (4_000_000, 80)),
    0x07: ((1_000_000, 75), (5_000_000, 75)),
}
CANFD_DEFAULT_BAUDRATE_GEAR = 0x07

logger = logging.getLogger("ghand.canfd_comm")


class CanfdComm(IComm):
    """IComm implementation for CANFD."""

    _DELETE_CONNECTION_SETTLE_SEC = 0.1
    _MIN_REOPEN_INTERVAL_SEC = 0.5
    _DEFAULT_POLL_INTERVAL_SEC = 0.03
    _KEEPALIVE_INTERVAL_SEC = 0.2
    _KEEPALIVE_TIMEOUT_MS = 300
    # Connection watchdog written at connect time. It must stay well above the
    # transport request timeout so a single lost response cannot starve the
    # keep-alive long enough for the device to drop the session.
    _CONNECTION_WATCHDOG_MS = 3000
    _DEFAULT_BAUDRATE_GEAR = CANFD_DEFAULT_BAUDRATE_GEAR
    COMMON_BAUDRATE_GEARS = tuple(sorted(CANFD_BAUDRATE_GEAR_MAP.keys(), reverse=True))

    def __init__(self, config: ProductConfig):
        self._config = config
        self._profile = get_modbus_profile(config)
        self._hand_mode = HandControlMode.POSITION
        self._joint_modes = {
            joint_id: HandControlMode.POSITION.value
            for joint_id in self._profile.joint_control_addresses
        }
        self._transport: CanfdTransport | None = None
        self._src_id = 0x0A  # master node id
        self._slave_id = 0x00
        self._connection_watchdog_ms = self._CONNECTION_WATCHDOG_MS
        self._connected = False
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()
        self._keepalive_thread: threading.Thread | None = None
        self._keepalive_stop = threading.Event()
        self._callbacks: dict[int, tuple] = {}
        self._next_sub_id = 1
        self._lock = threading.Lock()
        self._last_disconnect_at = 0.0
        self._poll_interval_sec = self._DEFAULT_POLL_INTERVAL_SEC

    def update_config(self, config: ProductConfig) -> None:
        """Update the cached product configuration."""
        self._config = config
        self._profile = get_modbus_profile(config)
        self._hand_mode = HandControlMode.POSITION
        self._joint_modes = {
            joint_id: HandControlMode.POSITION.value
            for joint_id in self._profile.joint_control_addresses
        }

    def _cleanup_failed_connect(self) -> None:
        """Release transport state left by a failed connection attempt."""
        self._connected = False
        if self._transport is None:
            return
        try:
            self._transport.close()
        except Exception:
            logger.exception("Error while cleaning up failed CANFD connection")
        finally:
            self._transport = None
            self._last_disconnect_at = time.monotonic()

    def _wait_for_reopen_window(self) -> None:
        """Avoid reopening before the adapter driver has released the handle."""
        if self._last_disconnect_at <= 0:
            return

        elapsed = time.monotonic() - self._last_disconnect_at
        remaining = self._MIN_REOPEN_INTERVAL_SEC - elapsed
        if remaining > 0:
            logger.debug("Waiting %.3fs before reopening CANFD transport", remaining)
            time.sleep(remaining)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def search_adapters(self) -> list[str]:
        """Search for available CANFD adapters.

        Returns:
            List of adapter identifiers. Linux returns ZQWL CDC serial adapters
            such as ``/dev/ttyACM0``; Windows returns ZQWL CDC serial ports
            such as ``COM3``.
        """
        adapters: list[str] = []
        if list_ports is not None:
            for port in list_ports.comports():
                if port.vid == 0x3562 and port.pid in (0x0100, 0x0101, 0x0105):
                    adapters.append(port.device)

        if platform.system() == "Linux":
            adapters.extend(str(path) for path in Path("/dev/serial/by-id").glob("*ZQWL*"))
            adapters.extend(str(path) for path in Path("/dev").glob("ttyACM*"))

        if not adapters:
            logger.warning("No ZQWL CANFD CDC serial adapters found")
        return sorted(dict.fromkeys(adapters))

    def _create_transport(self, device_name: str) -> CanfdTransport:
        """Create the platform-specific CANFD transport for *device_name*."""
        if device_name:
            return CanfdTransport(channel=device_name)
        return CanfdTransport()

    def connect(
        self,
        device_name: str,
        slave_id: int | None = None,
        baudrate: RS485BaudRate | CANFDBitTiming | None = None,
    ) -> bool:
        """Connect to the specified CANFD device.

        Internally performs the full CANFD connection handshake:
        open device → init channel → Node ID detection → establish connection.

        Args:
            device_name: ZQWL CDC serial device name (e.g. "COM3" or "/dev/ttyACM0").
            slave_id: Optional target slave ID. If provided, only this ID is
                used; otherwise the connection polls 0x31 and 0x32.
            baudrate: Baud rate gear value. The gear selects both the
                arbitration and data phase bitrates. Defaults to gear 0x07
                (1 Mbps arbitration, 5 Mbps data).

        Returns:
            True if the connection and handshake succeed.
        """
        if self._connected:
            return True

        try:
            self._wait_for_reopen_window()
            if self._transport is None:
                self._transport = self._create_transport(device_name)

            gear = (baudrate if baudrate is not None else self._DEFAULT_BAUDRATE_GEAR)
            pair = CANFD_BAUDRATE_GEAR_MAP.get(gear)
            if pair is None:
                logger.error("Invalid CANFD baudrate gear: %s", baudrate)
                self._cleanup_failed_connect()
                return False
            (abit_baud, abit_sample), (dbit_baud, dbit_sample) = pair
            logger.info(
                "Trying CANFD connection at %s with gear=0x%02X (abit=%s/%s%%, dbit=%s/%s%%)",
                device_name,
                gear,
                abit_baud,
                abit_sample,
                dbit_baud,
                dbit_sample,
            )
            if not self._transport.open(
                    abit_baud=abit_baud,
                    dbit_baud=dbit_baud,
                    abit_sample=abit_sample,
                    dbit_sample=dbit_sample,
            ):
                logger.error("Failed to open CANFD transport at gear=0x%02X", gear)
                self._cleanup_failed_connect()
                return False

            # Detect the node with FC44, then establish the connection via 0x0000.
            if not self._establish_connection(slave_id):
                logger.error("Failed to establish CANFD connection at gear=0x%02X", gear)
                self._cleanup_failed_connect()
                return False

            self._connected = True
            with self._lock:
                self._start_keepalive_locked()
            logger.info(
                "CANFD device connected (%s, slave_id=0x%02X, gear=0x%02X, abit=%s/%s%%, dbit=%s/%s%%)",
                device_name,
                self._slave_id,
                gear,
                abit_baud,
                abit_sample,
                dbit_baud,
                dbit_sample,
            )
            return True
        except Exception as exc:
            logger.error("CANFD connect failed: %s", exc)
            self._cleanup_failed_connect()
            return False

    def disconnect(self) -> bool:
        """Disconnect from the CANFD device."""
        with self._lock:
            poll_thread = self._stop_poll_locked()
            keepalive_thread = self._stop_keepalive_locked()
            self._callbacks.clear()
            self._recompute_poll_interval_locked()
        self._join_poll_thread(keepalive_thread)
        self._join_poll_thread(poll_thread)
        delete_sent = False
        if self._connected and self._transport is not None:
            try:
                self._delete_connection()
                delete_sent = True
            except Exception:
                logger.exception("Error during connection deletion")
        if delete_sent:
            time.sleep(self._DELETE_CONNECTION_SETTLE_SEC)
        if self._transport is not None:
            try:
                self._transport.close()
            except Exception:
                logger.exception("Error while closing CANFD transport")
            finally:
                self._transport = None
                self._last_disconnect_at = time.monotonic()
        self._connected = False
        self._slave_id = 0x00
        logger.info("CANFD device disconnected")
        return True

    def is_connected(self) -> bool:
        """Return whether the CANFD device is connected."""
        return self._connected

    def _ensure_transport(self) -> CanfdTransport:
        if self._transport is None:
            raise RuntimeError("Device is not connected")
        return self._transport

    def _start_keepalive_locked(self) -> None:
        """Start the keep-alive thread if it is not already running."""
        if self._keepalive_thread is None or not self._keepalive_thread.is_alive():
            stop_event = threading.Event()
            keepalive_thread = threading.Thread(target=self._keepalive_loop,
                                                args=(stop_event, ),
                                                daemon=True)
            self._keepalive_stop = stop_event
            self._keepalive_thread = keepalive_thread
            keepalive_thread.start()

    def _stop_keepalive_locked(self):
        self._keepalive_stop.set()
        keepalive_thread = self._keepalive_thread
        self._keepalive_thread = None
        return keepalive_thread

    def _keepalive_loop(self, stop_event: threading.Event) -> None:
        """Read the connection state periodically to keep an idle master connected.

        The device drops the connection when no frame arrives within its watchdog
        window (0x0001~0x0002, 500 ms by default), so an app that idles between
        API calls would otherwise lose the link. Keep sending during subscriptions
        because polling intervals and callbacks can exceed the watchdog window.
        """
        while not stop_event.wait(self._KEEPALIVE_INTERVAL_SEC):
            if not self._connected or self._transport is None:
                break
            try:
                self._transport.read_registers(
                    self._src_id,
                    self._slave_id,
                    REG_HOST_CONN_STATE,
                    1,
                    func_code=0x04,
                    timeout_ms=self._KEEPALIVE_TIMEOUT_MS,
                )
            except Exception as exc:
                logger.debug("CANFD keep-alive read failed: %s", exc)

    def _establish_connection(self, slave_id: int | None = None) -> bool:
        """Detect node ID with FC44, then write 1 to connection control."""
        slave_ids = [slave_id] if slave_id is not None else [0x31, 0x32]
        candidates = [node_id for node_id in dict.fromkeys(slave_ids) if node_id is not None]

        # devices announce their node ID after power-up with a spontaneous
        # FC44 frame: Src=Target=Node ID, ACK=0.
        deadline = time.time() + 0.5
        while time.time() < deadline:
            result = self._transport.recv_frame(timeout_ms=50)
            if result is None:
                continue
            resp_id, _ = result
            arb = unpack_arbitration(resp_id)
            if (arb["ack"] == 0 and arb["func_code"] == 0x44 and arb["src_id"] == arb["dst_id"]
                    and arb["src_id"] in candidates):
                if self._write_connection_control(
                        arb["src_id"],
                        1,
                        connection_timer_ms=self._connection_watchdog_ms,
                ):
                    return self._verify_connection()
                return False

        # If the device has already left the power-up detection window, actively
        # probe allowed node IDs with FC44.
        for slave_id in candidates:
            can_id = pack_arbitration(
                self._src_id,
                slave_id,
                ack=0,
                func_code=0x44,
                start=1,
                end=1,
                toggle=0,
                seg_num=0,
            )
            # firmware answers FC44 only when PDU[4] equals its own node ID.
            probe = struct.pack(">HH", 0x0000, 1) + bytes([slave_id, 0, 0, 0])
            if not self._transport.send_frame(can_id, probe):
                continue

            # Wait for the FC44 response from this node.
            deadline = time.time() + 0.5
            while time.time() < deadline:
                result = self._transport.recv_frame(timeout_ms=50)
                if result is None:
                    continue
                resp_id, _ = result
                arb = unpack_arbitration(resp_id)
                if arb["ack"] == 1 and arb["dst_id"] == self._src_id and arb["src_id"] == slave_id:
                    if arb["func_code"] == 0xC4:
                        break  # Exception: try next dst_id
                    if arb["func_code"] == 0x44:
                        if self._write_connection_control(
                                slave_id,
                                1,
                                connection_timer_ms=self._connection_watchdog_ms,
                        ):
                            return self._verify_connection()
                        break
        return False

    def _verify_connection(self) -> bool:
        """Confirm the connect command via link state and command mailbox."""
        if not self._wait_connection_state():
            return False
        return self._wait_command_result(REG_CONNECTION_STATUS)

    def _read_input_word(self, address: int, device_id: int | None = None) -> int | None:
        """Read one input register; None when the device does not answer."""
        target_id = self._slave_id if device_id is None else device_id
        try:
            raw = self._transport.read_registers(self._src_id,
                                                 target_id,
                                                 address,
                                                 1,
                                                 func_code=0x04)
        except Exception:
            return None
        if len(raw) < 2:
            return None
        return struct.unpack(">H", raw[:2])[0]

    def _wait_connection_state(self, timeout_sec: float = 2.0, interval_sec: float = 0.05) -> bool:
        """Poll the host connection state until the device reports connected."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            state = self._read_input_word(REG_HOST_CONN_STATE)
            if state is not None:
                if state & 0xFF == CONN_STATE_CONNECTED:
                    return True
                if state & 0xFF == CONN_STATE_ERROR:
                    return False
            time.sleep(interval_sec)
        return False

    def _wait_command_result(
        self,
        address: int,
        device_id: int | None = None,
        timeout_sec: float = 2.0,
        interval_sec: float = 0.05,
    ) -> bool:
        """Poll a command mailbox until the device reports success or failure."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            value = self._read_input_word(address, device_id=device_id)
            if value is not None:
                if value == MAILBOX_OK:
                    return True
                if value in (MAILBOX_FAILED, MAILBOX_INVALID):
                    return False
            time.sleep(interval_sec)
        return False

    def _write_connection_control(
        self,
        slave_id: int,
        value: int,
        timeout_ms: int = 5000,
        connection_timer_ms: int | None = None,
    ) -> bool:
        if connection_timer_ms is None:
            payload = struct.pack(">H", value)
        else:
            # 0x0001 holds the high 16 bits and 0x0002 the low 16 bits; both are
            # written with the connection control in one FC10 frame.
            payload = struct.pack(
                ">HHH",
                value,
                (connection_timer_ms >> 16) & 0xFFFF,
                connection_timer_ms & 0xFFFF,
            )
        if not self._ensure_transport().write_registers(
                self._src_id,
                slave_id,
                REG_CONNECTION_CONTROL,
                payload,
                timeout_ms=timeout_ms,
        ):
            return False
        self._slave_id = slave_id
        return True

    def _delete_connection(self) -> None:
        """Write 2 to the connection-control register."""
        self._write_connection_control(self._slave_id, 2, timeout_ms=2000)

    def set_slave_id(self, slave_id: int) -> bool:
        """Write a new CANFD node/slave ID to holding register 0x0003.

        The register carries the target ID in the high byte and the execute
        bit in the low byte; the new node ID answers as soon as it is applied.
        """
        if not self.is_connected():
            raise RuntimeError("Device is not connected")
        try:
            self._ensure_transport().write_registers(
                self._src_id,
                self._slave_id,
                REG_SLAVE_ID,
                struct.pack(">H", (slave_id << 8) | 0x01),
            )
            if not self._wait_command_result(REG_MODIFY_ID_STATUS, device_id=slave_id):
                logger.error("Device rejected CANFD node ID 0x%02X", slave_id)
                return False
        except Exception as exc:
            logger.error("Failed to set CANFD slave ID to 0x%02X: %s", slave_id, exc)
            return False
        self._slave_id = slave_id
        return True

    def set_baudrate(self, baudrate: int) -> bool:
        """Write the baud rate gear to holding register 0x0004.

        The value is saved to Flash and takes effect after the next power-up.
        For CANFD the gear selects both the arbitration phase bitrate/data-phase
        bitrate and their sample points.

        Args:
            baudrate: Gear stored in the register's high byte; the low
                byte is 0x01 to execute the configuration.
                Each entry below lists arbitration bitrate/sample point,
                followed by data bitrate/sample point:
                0x00: 500 Kbit/s at 80%, 800 Kbit/s at 80%.
                0x01: 500 Kbit/s at 80%, 1 Mbit/s at 75%.
                0x02: 500 Kbit/s at 80%, 2 Mbit/s at 80%.
                0x03: 500 Kbit/s at 80%, 4 Mbit/s at 80%.
                0x04: 1 Mbit/s at 75%, 1 Mbit/s at 75%.
                0x05: 1 Mbit/s at 75%, 2 Mbit/s at 80%.
                0x06: 1 Mbit/s at 75%, 4 Mbit/s at 80%.
                0x07: 1 Mbit/s at 75%, 5 Mbit/s at 75%.
                Values outside 0x00 through 0x07 are rejected by the SDK.

        Returns:
            True if the device accepted the configuration.
        """
        if not self.is_connected():
            raise RuntimeError("Device is not connected")
        gear = baudrate
        if gear not in CANFD_BAUDRATE_GEAR_MAP:
            logger.error("Invalid CANFD baudrate gear: %s", gear)
            return False
        try:
            self._ensure_transport().write_registers(
                self._src_id,
                self._slave_id,
                BAUDRATE_CONFIG_REGISTER,
                struct.pack(">H", (gear << 8) | 0x01),
            )
        except Exception as exc:
            logger.error("Failed to set CANFD baudrate config to gear 0x%02X: %s", gear, exc)
            return False
        return self._wait_command_result(REG_MODIFY_BAUD_STATUS)

    # ------------------------------------------------------------------
    # Joint control
    # ------------------------------------------------------------------

    def move_joints(self, joints: list, mode: HandControlMode) -> bool:
        """Send joint control commands."""
        if not self.is_connected():
            logger.error("Cannot move joints: CANFD device is not connected")
            return False

        address, registers, updated_modes = encode_hand_command_frame(joints, mode, self._profile,
                                                                      self._joint_modes)
        logger.debug(
            "CANFD write whole-hand command addr=0x%04X count=%d",
            address,
            len(registers),
        )
        try:
            self._ensure_transport().write_registers(
                self._src_id,
                self._slave_id,
                address,
                struct.pack(f">{len(registers)}H", *registers),
            )
        except Exception:
            logger.exception("Failed to write CANFD whole-hand command")
            raise
        self._hand_mode = mode
        self._joint_modes.update(updated_modes)
        return True

    def _set_hand_enabled(self, enabled: bool) -> bool:
        if self._profile.mode_register is None:
            return False
        self._ensure_transport().write_registers(
            self._src_id,
            self._slave_id,
            self._profile.mode_register,
            struct.pack(">H", encode_hand_control(self._hand_mode, enabled)),
        )
        return True

    def disable_hand(self) -> bool:
        """Disable all active joints at the hand-control level."""
        return self._set_hand_enabled(False)

    def stop(self) -> bool:
        """Send an immediate stop command."""
        if not self._set_hand_enabled(True):
            return False
        for joint_id, base_addr in self._profile.joint_control_addresses.items():
            self._ensure_transport().write_registers(
                self._src_id,
                self._slave_id,
                base_addr,
                struct.pack(
                    ">H",
                    encode_joint_mode_stop(
                        self._joint_modes.get(joint_id, HandControlMode.POSITION.value),
                        JointControlState.STOPPED,
                    ),
                ),
            )
        return True

    # ------------------------------------------------------------------
    # State retrieval
    # ------------------------------------------------------------------

    def get_joints(self) -> list:
        """Retrieve the current state of all joints."""
        if not self._config.all_joints:
            return []
        start, count = get_joint_input_span(self._config.all_joints, self._profile)
        if count == 0:
            return []
        raw_bytes = self._ensure_transport().read_registers(self._src_id,
                                                            self._slave_id,
                                                            start,
                                                            count,
                                                            func_code=0x04)
        # Convert bytes back to uint16 register list for the shared codec.
        raw = list(struct.unpack(f">{count}H", raw_bytes[:count * 2]))
        return parse_joints(raw, self._config.all_joints, self._profile, start)

    def get_hand_info(self) -> HandData:
        """Retrieve high-level hand status."""
        raw_bytes = self._ensure_transport().read_registers(
            self._src_id,
            self._slave_id,
            self._profile.hand_info_address,
            14,
            func_code=0x04,
        )
        raw = list(struct.unpack(">14H", raw_bytes[:28]))
        return parse_hand_info(raw)

    def get_hand_state_machine(self) -> HandRuntimeState | int:
        """Retrieve the Modbus whole-hand runtime state."""
        raw_bytes = self._ensure_transport().read_registers(
            self._src_id,
            self._slave_id,
            REG_HAND_STATE_MACHINE,
            1,
            func_code=0x04,
        )
        raw = list(struct.unpack(">H", raw_bytes[:2]))
        return parse_hand_state_machine(raw)

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data."""
        if not self._config.has_tactile:
            return {}
        # Read state + resultant forces (16 registers from 0x1110)
        raw_bytes = self._ensure_transport().read_registers(
            self._src_id,
            self._slave_id,
            self._profile.tactile_state_address,
            self._profile.tactile_resultant_register_count,
            func_code=0x04,
        )
        count = self._profile.tactile_resultant_register_count
        raw = list(struct.unpack(f">{count}H", raw_bytes[:count * 2]))
        tactile_state, _ = parse_tactile_state_error(raw)

        result = {}
        current_addr = (self._profile.tactile_state_address +
                        self._profile.tactile_resultant_register_count)

        for region in self._config.tactile_regions:
            idx = region.id.value
            resultant = parse_tactile_resultant(raw, idx)
            state_bit = (tactile_state & (1 << idx)) != 0

            # Read distributed force for this region
            dist_regs = (region.count * 3 + 1) // 2
            dist_bytes = self._ensure_transport().read_registers(self._src_id,
                                                                 self._slave_id,
                                                                 current_addr,
                                                                 dist_regs,
                                                                 func_code=0x04)
            dist_words = struct.unpack(f">{dist_regs}H", dist_bytes[:dist_regs * 2])
            distributed = parse_tactile_distributed(
                registers_to_bytes_low_high(list(dist_words)), region.count)
            current_addr += dist_regs

            result[region.id] = build_tactile_info(state_bit, resultant, distributed)
        return result

    # ------------------------------------------------------------------
    # Device info reading
    # ------------------------------------------------------------------

    def _read_input_bytes(self, addr: int, count: int) -> bytes:
        """Helper to read input registers and return raw bytes."""
        return self._ensure_transport().read_registers(self._src_id,
                                                       self._slave_id,
                                                       addr,
                                                       count,
                                                       func_code=0x04)

    def _get_string_info(self, addr: int, count: int, parse) -> str:
        try:
            return parse(self._read_input_bytes(addr, count)) or "N/A"
        except Exception:
            if not self.is_connected():
                raise
            return "N/A"

    def get_device_name(self) -> str:
        return self._get_string_info(REG_DEVICE_NAME, 8, parse_device_name)

    def get_firmware_version(self) -> str:
        return self._get_packed_version(REG_FIRMWARE_VERSION)

    def get_serial_number(self) -> str:
        try:
            return parse_ascii_serial_number(self._read_input_bytes(REG_SERIAL_NUMBER, 10))
        except Exception:
            if not self.is_connected():
                raise
            return "N/A"

    def get_hand_type(self) -> int:
        try:
            return parse_hand_type(self._read_input_bytes(REG_HAND_TYPE, 1))
        except Exception:
            if not self.is_connected():
                raise
            return 0

    def _get_packed_version(self, register: int) -> str:
        try:
            raw = self._read_input_bytes(register, 1)
            if len(raw) < 2 or raw[:2] == b"\x00\x00":
                return "N/A"
            return parse_packed_firmware_version(raw)
        except Exception:
            if not self.is_connected():
                raise
            return "N/A"

    def get_firmware_package_version(self) -> str:
        return self._get_packed_version(REG_IN_FIRMWARE_PACKAGE_VER)

    def get_position_sensor_version(self) -> str:
        return self._get_packed_version(REG_IN_POSITION_SENSOR_VER)

    def get_tactile_sensor_version(self) -> str:
        return self._get_packed_version(REG_IN_TACTILE_SENSOR_VER)

    def get_motor_driver_version(self) -> str:
        return self._get_packed_version(REG_IN_MOTOR_DRV_VER)

    def get_thumb_tactile_sensor_version(self) -> str:
        return self._get_packed_version(REG_IN_THUMB_TACTILE_VER)

    def get_finger_tactile_sensor_version(self) -> str:
        return self._get_packed_version(REG_IN_FINGER_TACTILE_VER)

    # ------------------------------------------------------------------
    # Tactile sensor
    # ------------------------------------------------------------------

    def open_tactile(self) -> bool:
        return self._write_tactile_control(0x0001)

    def close_tactile(self) -> bool:
        return self._write_tactile_control(0x0002)

    def zero_tactile(self) -> bool:
        return self._write_tactile_control(0x0004)

    def _write_tactile_control(self, command: int) -> bool:
        """Write a tactile control command and await the terminal state.

        Args:
            command: low-byte command value (1=enable, 2=disable, 4=zero).
        """
        baseline = self._read_input_word(REG_TACTILE_CTRL_STATUS)
        if not self._ensure_transport().write_registers(
                self._src_id,
                self._slave_id,
                self._profile.tactile_control_address,
                struct.pack(">H", command),
        ):
            return False
        state = self._wait_mailbox_terminal(REG_TACTILE_CTRL_STATUS, baseline)
        return state == MAILBOX_OK

    # ------------------------------------------------------------------
    # Device operations
    # ------------------------------------------------------------------

    def _wait_mailbox_terminal(
        self,
        address: int,
        baseline: int | None = None,
        timeout_sec: float = 2.0,
        interval_sec: float = 0.02,
        settle_sec: float = 0.3,
    ) -> int | None:
        """Wait for the terminal mailbox state of a command register.

        command mailboxes encode the low byte as status (0 idle / 1 busy)
        and the high byte as result (1 ok / 2 failed / 3 invalid). The register
        keeps the last terminal value, so a fresh terminal can equal
        ``baseline`` (for example open-tactile right after close-tactile). A
        terminal reading is accepted when it differs from ``baseline``, when
        the busy state was observed first, or when it has stayed unchanged for
        ``settle_sec`` (the firmware consumes commands within one 10 ms task
        tick, so a value unchanged past the settle window is a fresh terminal).
        Returns the terminal value, or None on timeout.
        """
        start = time.time()
        deadline = start + timeout_sec
        busy_seen = False
        while time.time() < deadline:
            value = self._read_input_word(address)
            if value is None:
                time.sleep(interval_sec)
                continue
            if value == MAILBOX_BUSY:
                busy_seen = True
            terminal = value in (MAILBOX_OK, MAILBOX_FAILED, MAILBOX_INVALID)
            settled = (time.time() - start) >= settle_sec
            if terminal and (busy_seen or value != baseline or settled):
                return value
            time.sleep(interval_sec)
        return None

    def clear_fault(self) -> bool:
        """Clear device faults via the mailbox (writing full value 1)."""
        baseline = self._read_input_word(REG_FAULT_CLEAR_STATUS)
        if not self._ensure_transport().write_registers(self._src_id, self._slave_id,
                                                        REG_CLEAR_FAULT, struct.pack(">H", 0x0001)):
            return False
        state = self._wait_mailbox_terminal(REG_FAULT_CLEAR_STATUS, baseline)
        if state != MAILBOX_OK:
            logger.error("Fault clearance failed or timed out")
            return False
        logger.info("Fault cleared")
        return True

    # ------------------------------------------------------------------
    # Subscription (polling-based)
    # ------------------------------------------------------------------

    def subscribe(self, callback, *args, interval_ms: int | None = None, **kwargs) -> int:
        """Subscribe to device data updates.

        The callback receives ``(hand_state, joints, *args, **kwargs)``.

        Args:
            callback: Callable invoked with ``(hand_state, joints)``.
            interval_ms: Optional polling interval in milliseconds.

        Returns:
            Subscription ID.
        """
        if not self.is_connected():
            raise RuntimeError("Device is not connected")

        with self._lock:
            interval_sec = (interval_ms / 1000.0 if interval_ms is not None else None)
            sub_id = self._next_sub_id
            self._next_sub_id += 1
            self._callbacks[sub_id] = (callback, args, kwargs, interval_sec)
            self._recompute_poll_interval_locked()
            self._ensure_poll_started_locked()
            return sub_id

    def unsubscribe(self, sub_id) -> bool:
        with self._lock:
            if sub_id not in self._callbacks:
                return False
            del self._callbacks[sub_id]
            self._recompute_poll_interval_locked()
            poll_thread = self._stop_poll_locked() if not self._callbacks else None
        self._join_poll_thread(poll_thread)
        return True

    def _ensure_poll_started_locked(self) -> None:
        if self._poll_thread is None or not self._poll_thread.is_alive():
            stop_event = threading.Event()
            poll_thread = threading.Thread(target=self._poll_loop, args=(stop_event, ), daemon=True)
            self._poll_stop = stop_event
            self._poll_thread = poll_thread
            poll_thread.start()

    def _stop_poll(self) -> None:
        with self._lock:
            poll_thread = self._stop_poll_locked()
        self._join_poll_thread(poll_thread)

    def _stop_poll_locked(self):
        self._poll_stop.set()
        poll_thread = self._poll_thread
        self._poll_thread = None
        return poll_thread

    @staticmethod
    def _join_poll_thread(poll_thread) -> None:
        if (poll_thread and poll_thread.is_alive()
                and poll_thread is not threading.current_thread()):
            poll_thread.join(timeout=0.5)

    def _recompute_poll_interval_locked(self) -> None:
        intervals = [item[3] for item in self._callbacks.values() if item[3] is not None]
        self._poll_interval_sec = (min(intervals) if intervals else self._DEFAULT_POLL_INTERVAL_SEC)

    def _poll_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                if not self._connected:
                    break

                if not self._config.all_joints:
                    time.sleep(self._poll_interval_sec)
                    continue

                joint_start, joint_count = get_joint_input_span(self._config.all_joints,
                                                                self._profile)
                if joint_count == 0:
                    time.sleep(self._poll_interval_sec)
                    continue
                start = min(self._profile.hand_info_address, joint_start)
                end = max(
                    self._profile.hand_info_address + 13,
                    joint_start + joint_count - 1,
                )
                count = end - start + 1
                raw_bytes = self._transport.read_registers(self._src_id,
                                                           self._slave_id,
                                                           start,
                                                           count,
                                                           func_code=0x04)
                raw = list(struct.unpack(f">{count}H", raw_bytes[:count * 2]))
                hand_offset = self._profile.hand_info_address - start
                hand_state = parse_hand_info(raw[hand_offset:hand_offset + 14])
                joints = parse_joints(
                    raw,
                    self._config.all_joints,
                    self._profile,
                    start,
                )

                if stop_event.is_set():
                    break
                with self._lock:
                    callbacks = list(self._callbacks.values())

                for cb, cb_args, cb_kwargs, _ in callbacks:
                    try:
                        cb(hand_state, joints, *cb_args, **cb_kwargs)
                    except Exception:
                        logger.exception("Subscription callback error")
            except Exception as e:
                logger.error("Subscription stopped: %s", e)
                stop_event.set()
                break

            time.sleep(self._poll_interval_sec)
