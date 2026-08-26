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

from ..types import (
    CtrlMode,
    ErrorCode,
    HandState,
    JointData,
    JointId,
    ProductConfig,
    SelfTestErrorInfo,
    State,
    TactileInfo,
)
from .canfd_transport import CanfdTransport, pack_arbitration, unpack_arbitration
from .icomm import IComm
from .modbus_codec import (
    BAUDRATE_CONFIG_REGISTER,
    REG_CLEAR_FAULT,
    REG_DEVICE_NAME,
    REG_FIRMWARE_VERSION,
    REG_HAND_TYPE,
    REG_HARDWARE_VERSION,
    REG_INIT_JOINT,
    REG_IN_FINGER_TACTILE_SENSOR_VER,
    REG_IN_FIRMWARE_PACKAGE_VER,
    REG_IN_MOTOR_DRV_VER,
    REG_IN_POSITION_SENSOR_VER,
    REG_IN_SERIAL_NUMBER,
    REG_IN_TACTILE_SENSOR_VER,
    REG_IN_THUMB_TACTILE_SENSOR_VER,
    build_tactile_info,
    encode_joint_command,
    get_joint_input_span,
    get_modbus_profile,
    parse_device_name,
    parse_firmware_version,
    parse_hand_info,
    parse_hand_type,
    parse_hardware_version,
    parse_ascii_serial_number,
    parse_packed_firmware_version,
    parse_joints,
    parse_tactile_distributed,
    parse_tactile_resultant,
    parse_tactile_state_error,
    registers_to_bytes,
)
from .self_test_workflow import build_self_test_error_info

# CANFD baud rate gear map per protocol documentation.
# Writing a gear value to BAUDRATE_CONFIG_REGISTER selects both the arbitration
# phase bitrate/data-phase bitrate and their sample points; the new
# configuration takes effect after the next power-up.
CANFD_BAUDRATE_GEAR_MAP: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {
    # gear: ((arbitration_baud, arbitration_sample_point), (data_baud, data_sample_point))
    0x00: ((500_000, 80), (1_000_000, 75)),
    0x01: ((500_000, 80), (2_000_000, 80)),
    0x02: ((500_000, 80), (4_000_000, 80)),
    0x03: ((500_000, 80), (5_000_000, 75)),
    0x04: ((1_000_000, 75), (4_000_000, 80)),
    0x05: ((1_000_000, 75), (5_000_000, 75)),
}
CANFD_DEFAULT_BAUDRATE_GEAR = 0x05

logger = logging.getLogger("ghand.canfd_comm")


class CanfdComm(IComm):
    """IComm implementation for CANFD."""

    _DELETE_CONNECTION_SETTLE_SEC = 0.1
    _MIN_REOPEN_INTERVAL_SEC = 0.5
    _DEFAULT_POLL_INTERVAL_SEC = 0.03
    _DEFAULT_BAUDRATE_GEAR = CANFD_DEFAULT_BAUDRATE_GEAR
    COMMON_BAUDRATE_GEARS = tuple(sorted(CANFD_BAUDRATE_GEAR_MAP.keys(), reverse=True))

    def __init__(self, config: ProductConfig):
        self._config = config
        self._profile = get_modbus_profile(config)
        self._transport: CanfdTransport | None = None
        self._src_id = 0x0A  # master node id
        self._slave_id = 0x00
        self._connected = False
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()
        self._callbacks: dict[int, tuple] = {}
        self._next_sub_id = 1
        self._lock = threading.Lock()
        self._last_disconnect_at = 0.0
        self._poll_interval_sec = self._DEFAULT_POLL_INTERVAL_SEC

    def update_config(self, config: ProductConfig) -> None:
        """Update the cached product configuration."""
        self._config = config
        self._profile = get_modbus_profile(config)

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
        baudrate_gear: int | None = None,
        quiet: bool = False,
    ) -> bool:
        """Connect to the specified CANFD device.

        Internally performs the full CANFD connection handshake:
        open device → init channel → Node ID detection → establish connection.

        Args:
            device_name: ZQWL CDC serial device name (e.g. "COM3" or "/dev/ttyACM0").
            slave_id: Optional target slave ID. If provided, only this ID is
                used; otherwise the connection polls 0x31 and 0x32.
            baudrate_gear: Baud rate gear value. The gear selects both the
                arbitration and data phase bitrates. Defaults to gear 0x05
                (1 Mbps arbitration, 5 Mbps data).
            quiet: When True, suppress non-fatal failure logs. Useful when the
                caller is scanning several gears.

        Returns:
            True if the connection and handshake succeed.
        """
        if self._connected:
            return True

        def _log_error(msg: str, *args) -> None:
            if quiet:
                logger.debug(msg, *args)
            else:
                logger.error(msg, *args)

        try:
            self._wait_for_reopen_window()
            if self._transport is None:
                self._transport = self._create_transport(device_name)

            gear = (
                baudrate_gear
                if baudrate_gear is not None
                else self._DEFAULT_BAUDRATE_GEAR
            )
            pair = CANFD_BAUDRATE_GEAR_MAP.get(gear)
            if pair is None:
                _log_error("Invalid CANFD baudrate gear: %s", baudrate_gear)
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
                quiet=quiet,
            ):
                _log_error("Failed to open CANFD transport at gear=0x%02X", gear)
                self._cleanup_failed_connect()
                return False

            # Establish connection: function code 0x02, write connection timer=0.
            if not self._establish_connection(slave_id):
                _log_error("Failed to establish CANFD connection at gear=0x%02X", gear)
                self._cleanup_failed_connect()
                return False

            self._connected = True
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
            _log_error("CANFD connect failed: %s", exc)
            self._cleanup_failed_connect()
            return False

    def disconnect(self) -> bool:
        """Disconnect from the CANFD device."""
        self._stop_poll()
        self._callbacks.clear()
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

    def _establish_connection(self, slave_id: int | None = None) -> bool:
        """Send connection-establishment frame (FC 0x02), polling node IDs."""
        slave_ids = [slave_id] if slave_id is not None else [0x31, 0x32]
        for slave_id in dict.fromkeys(slave_ids):
            if slave_id is None:
                continue
            timer_values = self._profile.canfd_connection_timer_values
            data = (
                struct.pack(
                    ">HH",
                    self._profile.canfd_connection_timer_address,
                    self._profile.canfd_connection_timer_registers,
                )
                + struct.pack(f">{len(timer_values)}H", *timer_values)
            )
            can_id = pack_arbitration(
                self._src_id, slave_id, ack=0, func_code=0x02,
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
                if arb["ack"] == 1 and arb["dst_id"] == self._src_id and arb["src_id"] == slave_id:
                    if arb["func_code"] == 0x82:
                        break  # Exception: try next dst_id
                    if arb["func_code"] == 0x02:
                        self._slave_id = slave_id
                        return True
        return False

    def _delete_connection(self) -> None:
        """Send connection-deletion frame (FC 0x05)."""
        delete_values = self._profile.canfd_connection_delete_values
        data = (
            struct.pack(
                ">HH",
                self._profile.canfd_connection_delete_address,
                self._profile.canfd_connection_delete_registers,
            )
            + struct.pack(f">{len(delete_values)}H", *delete_values)
        )
        can_id = pack_arbitration(
            self._src_id, self._slave_id, ack=0, func_code=0x05,
            start=1, end=1, toggle=0, seg_num=0,
        )
        self._transport.send_frame(can_id, data)

    def set_slave_id(self, slave_id: int) -> bool:
        """Write a new CANFD node/slave ID to holding register 0x0000."""
        if not 0 < slave_id <= 0x3F:
            raise ValueError("CANFD slave_id must be in range 1..63")
        try:
            self._transport.write_registers(
                self._src_id,
                self._slave_id,
                0x0000,
                struct.pack(">H", slave_id),
            )
        except Exception as exc:
            logger.error("Failed to set CANFD slave ID to 0x%02X: %s", slave_id, exc)
            return False
        self._slave_id = slave_id
        return True

    def set_baudrate_config(
        self,
        baudrate_gear: int | None = None,
    ) -> bool:
        """Write the baud rate gear to holding register 0x002C.

        The value is saved to Flash and takes effect after the next power-up.
        For CANFD the gear selects both the arbitration phase bitrate/data-phase
        bitrate and their sample points.

        Args:
            baudrate_gear: Gear value written directly to the register. When
                omitted the default gear (0x05) is used. Supported gears map to:
                0x00=(500K@80%,1M@75%), 0x01=(500K@80%,2M@80%),
                0x02=(500K@80%,4M@80%), 0x03=(500K@80%,5M@75%),
                0x04=(1M@75%,4M@80%), 0x05=(1M@75%,5M@75%) default.

        Returns:
            True if the device accepted the configuration.
        """
        gear = baudrate_gear if baudrate_gear is not None else CANFD_DEFAULT_BAUDRATE_GEAR
        try:
            self._transport.write_registers(
                self._src_id,
                self._slave_id,
                BAUDRATE_CONFIG_REGISTER,
                struct.pack(">H", gear),
            )
        except Exception as exc:
            logger.error("Failed to set CANFD baudrate config to gear 0x%02X: %s", gear, exc)
            return False
        return True

    # ------------------------------------------------------------------
    # Joint control
    # ------------------------------------------------------------------

    def move_joints(self, joints: list, mode: CtrlMode) -> bool:
        """Send joint control commands."""
        if not self.is_connected():
            logger.error("Cannot move joints: CANFD device is not connected")
            return False

        if self._profile.mode_register is not None:
            mode_value = (mode.value << 8) & 0xFF00
            logger.debug(
                "CANFD write mode register addr=0x%04X value=0x%04X",
                self._profile.mode_register,
                mode_value,
            )
            try:
                self._transport.write_registers(
                    self._src_id,
                    self._slave_id,
                    self._profile.mode_register,
                    struct.pack(">H", mode_value),
                )
            except Exception:
                logger.exception(
                    "Failed to write CANFD mode register addr=0x%04X",
                    self._profile.mode_register,
                )
                raise

        for joint in joints:
            joint_id = JointId(joint.id)
            base_addr = self._profile.joint_control_addresses.get(joint_id)
            if base_addr is None:
                continue
            position, speed_torque = encode_joint_command(joint)
            if self._profile.control_layout == "per_joint_mode_3reg":
                mode_stop = ((mode.value & 0xFF) << 8) | 0x00
                registers = [mode_stop, position, speed_torque]
            else:
                registers = [position, speed_torque]
            logger.debug(
                "CANFD write joint=%s addr=0x%04X registers=%s",
                joint_id.name,
                base_addr,
                [f"0x{reg:04X}" for reg in registers],
            )
            try:
                self._transport.write_registers(
                    self._src_id,
                    self._slave_id,
                    base_addr,
                    struct.pack(f">{len(registers)}H", *registers),
                )
            except Exception:
                logger.exception(
                    "Failed to write CANFD joint=%s addr=0x%04X",
                    joint_id.name,
                    base_addr,
                )
                raise
        return True

    def stop(self) -> bool:
        """Send an immediate stop command."""
        if self._profile.stop_register is not None:
            self._transport.write_registers(
                self._src_id,
                self._slave_id,
                self._profile.stop_register,
                struct.pack(">H", 0x0001),
            )
            return True

        for joint_id in self._config.valid_joints:
            base_addr = self._profile.joint_control_addresses.get(joint_id)
            if base_addr is None:
                continue
            self._transport.write_registers(
                self._src_id, self._slave_id, base_addr, struct.pack(">H", 0x0001)
            )
        return True

    # ------------------------------------------------------------------
    # State retrieval
    # ------------------------------------------------------------------

    def get_joints(self) -> list:
        """Retrieve the current state of all valid joints."""
        if not self._config.valid_joints:
            return []
        start, count = get_joint_input_span(self._config.valid_joints, self._profile)
        if count == 0:
            return []
        raw_bytes = self._transport.read_registers(
            self._src_id, self._slave_id, start, count, func_code=0x04
        )
        # Convert bytes back to uint16 register list for the shared codec.
        raw = list(struct.unpack(f">{count}H", raw_bytes[: count * 2]))
        return parse_joints(raw, self._config.valid_joints, self._profile, start)

    def get_hand_info(self) -> HandState:
        """Retrieve high-level hand status."""
        raw_bytes = self._transport.read_registers(
            self._src_id,
            self._slave_id,
            self._profile.hand_info_address,
            2,
            func_code=0x04,
        )
        raw = list(struct.unpack(">2H", raw_bytes[:4]))
        return parse_hand_info(raw)

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data."""
        if not self._config.has_tactile:
            return {}
        # Read state + resultant forces (16 registers from 0x1080)
        raw_bytes = self._transport.read_registers(
            self._src_id,
            self._slave_id,
            self._profile.tactile_state_address,
            self._profile.tactile_resultant_register_count,
            func_code=0x04,
        )
        count = self._profile.tactile_resultant_register_count
        raw = list(struct.unpack(f">{count}H", raw_bytes[: count * 2]))
        tactile_state, _ = parse_tactile_state_error(raw)

        result = {}
        current_addr = (
            self._profile.tactile_state_address
            + self._profile.tactile_resultant_register_count
        )

        for region in self._config.tactile_regions:
            idx = region.id.value
            resultant = parse_tactile_resultant(raw, idx)
            state_bit = (tactile_state & (1 << idx)) != 0

            # Read distributed force for this region
            dist_regs = (region.count * 3 + 1) // 2
            dist_bytes = self._transport.read_registers(
                self._src_id, self._slave_id, current_addr, dist_regs, func_code=0x04
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
            self._src_id, self._slave_id, addr, count, func_code=0x04
        )

    def _get_string_info(self, addr: int, count: int, parse) -> str:
        try:
            return parse(self._read_input_bytes(addr, count)) or "N/A"
        except Exception:
            return "N/A"

    def get_device_name(self) -> str:
        return self._get_string_info(REG_DEVICE_NAME, 8, parse_device_name)

    def get_hardware_version(self) -> str:
        return self._get_string_info(REG_HARDWARE_VERSION, 8, parse_hardware_version)

    def get_firmware_version(self) -> str:
        return self._get_string_info(REG_FIRMWARE_VERSION, 8, parse_firmware_version)

    def get_serial_number(self) -> str:
        try:
            return parse_ascii_serial_number(self._read_input_bytes(REG_IN_SERIAL_NUMBER, 10))
        except Exception:
            return "N/A"

    def get_hand_type(self) -> int:
        try:
            return parse_hand_type(self._read_input_bytes(REG_HAND_TYPE, 1))
        except Exception:
            return 0

    def _get_packed_version(self, register: int) -> str:
        try:
            raw = self._read_input_bytes(register, 1)
            if len(raw) < 2:
                return "N/A"
            return parse_packed_firmware_version(raw)
        except Exception:
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
        return self._get_packed_version(REG_IN_THUMB_TACTILE_SENSOR_VER)

    def get_finger_tactile_sensor_version(self) -> str:
        return self._get_packed_version(REG_IN_FINGER_TACTILE_SENSOR_VER)

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
            self._src_id,
            self._slave_id,
            self._profile.tactile_control_address,
            struct.pack(">H", command),
        )
        return True

    # ------------------------------------------------------------------
    # Device operations
    # ------------------------------------------------------------------

    def _wait_holding_result(
        self,
        address: int,
        timeout_sec: float = 2.0,
        interval_sec: float = 0.05,
    ) -> bool:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            raw = self._transport.read_registers(
                self._src_id, self._slave_id, address, 1, func_code=0x03
            )
            register = struct.unpack(">H", raw[:2])[0]
            status = register & 0x00FF
            if status == 1:
                return True
            if status == 2:
                return False
            time.sleep(interval_sec)
        return False

    def clear_fault(self) -> bool:
        self._transport.write_registers(
            self._src_id, self._slave_id, REG_CLEAR_FAULT, struct.pack(">H", 0x0100)
        )
        if not self._wait_holding_result(REG_CLEAR_FAULT):
            logger.error("Fault clearance failed or timed out")
            return False
        logger.info("Fault cleared")
        return True

    def init_joint(self) -> bool:
        self._transport.write_registers(
            self._src_id, self._slave_id, REG_INIT_JOINT, struct.pack(">H", 0x0001)
        )
        logger.info("Joint initialization completed")
        return True

    # ------------------------------------------------------------------
    # Self-test error query (registers 0x0038 ~ 0x003F)
    # ------------------------------------------------------------------

    def _self_test_read_registers(self, address: int, count: int) -> list[int]:
        raw = self._transport.read_registers(
            self._src_id, self._slave_id, address, count, func_code=0x03
        )
        return list(struct.unpack(f">{count}H", raw[: count * 2]))

    def _self_test_write_register(self, address: int, value: int) -> None:
        self._transport.write_registers(
            self._src_id, self._slave_id, address, struct.pack(">H", value)
        )

    def get_self_test_error_info(self) -> SelfTestErrorInfo:
        """Query self-test error information via CANFD-mapped registers 0x0038~0x003F."""
        return build_self_test_error_info(
            self._config,
            self._self_test_read_registers,
            self._self_test_write_register,
        )

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
            interval_sec = (
                interval_ms / 1000.0 if interval_ms is not None else None
            )
            sub_id = self._next_sub_id
            self._next_sub_id += 1
            self._callbacks[sub_id] = (callback, args, kwargs, interval_sec)
            self._recompute_poll_interval_locked()
            self._ensure_poll_started()
            return sub_id

    def unsubscribe(self, sub_id) -> bool:
        with self._lock:
            if sub_id not in self._callbacks:
                return False
            del self._callbacks[sub_id]
            self._recompute_poll_interval_locked()
            should_stop = not self._callbacks
        if should_stop:
            self._stop_poll()
        return True

    def _ensure_poll_started(self) -> None:
        if self._poll_thread is None or not self._poll_thread.is_alive():
            self._poll_stop.clear()
            self._poll_thread = threading.Thread(
                target=self._poll_loop, daemon=True
            )
            self._poll_thread.start()

    def _stop_poll(self) -> None:
        self._poll_stop.set()
        if (
            self._poll_thread
            and self._poll_thread.is_alive()
            and self._poll_thread is not threading.current_thread()
        ):
            self._poll_thread.join(timeout=0.5)
        self._poll_thread = None

    def _recompute_poll_interval_locked(self) -> None:
        intervals = [
            item[3] for item in self._callbacks.values() if item[3] is not None
        ]
        self._poll_interval_sec = (
            min(intervals) if intervals else self._DEFAULT_POLL_INTERVAL_SEC
        )

    def _poll_loop(self) -> None:
        while not self._poll_stop.is_set():
            try:
                if not self._connected:
                    break

                if not self._config.valid_joints:
                    time.sleep(self._poll_interval_sec)
                    continue

                joint_start, joint_count = get_joint_input_span(
                    self._config.valid_joints, self._profile
                )
                if joint_count == 0:
                    time.sleep(self._poll_interval_sec)
                    continue
                start = min(self._profile.hand_info_address, joint_start)
                end = max(
                    self._profile.hand_info_address + 1,
                    joint_start + joint_count - 1,
                )
                count = end - start + 1
                raw_bytes = self._transport.read_registers(
                    self._src_id, self._slave_id, start, count, func_code=0x04
                )
                raw = list(struct.unpack(f">{count}H", raw_bytes[: count * 2]))
                hand_offset = self._profile.hand_info_address - start
                hand_state = parse_hand_info(raw[hand_offset:hand_offset + 2])
                joints = parse_joints(
                    raw,
                    self._config.valid_joints,
                    self._profile,
                    start,
                )

                with self._lock:
                    callbacks = list(self._callbacks.values())

                for cb, cb_args, cb_kwargs, _ in callbacks:
                    try:
                        cb(hand_state, joints, *cb_args, **cb_kwargs)
                    except Exception:
                        logger.exception("Subscription callback error")
            except Exception as e:
                logger.error("Subscription stopped: %s", e)
                self._poll_stop.set()
                break

            time.sleep(self._poll_interval_sec)
