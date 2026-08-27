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

"""RS485 communication implementation using Modbus RTU."""

from __future__ import annotations

import logging
import os
import platform
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
try:
    import serial.tools.list_ports
except ImportError:
    serial = None  # type: ignore[assignment]

try:
    from pymodbus.client import ModbusSerialClient
    from pymodbus.exceptions import ModbusException
except ImportError:
    ModbusSerialClient = None  # type: ignore[misc,assignment]
    ModbusException = Exception  # type: ignore[misc,assignment]
from ..types import (
    ErrorCode,
    HandState,
    JointData,
    JointId,
    ProductConfig,
    SelfTestErrorInfo,
    State,
    TactileInfo,
)
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
    REG_SLAVE_ID,
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

# RS485 baud rate gear map per protocol documentation.
# Writing a gear value to BAUDRATE_CONFIG_REGISTER selects the serial baud rate;
# the new configuration takes effect after the next power-up.
RS485_BAUDRATE_GEAR_MAP: dict[int, int] = {
    0x00: 57_600,
    0x01: 115_200,
    0x02: 230_400,
    0x03: 460_800,
    0x04: 921_600,
    0x05: 1_000_000,
}
RS485_DEFAULT_BAUDRATE_GEAR = 0x05

logger = logging.getLogger("ghand.rs485_comm")


class Rs485Comm(IComm):
    """IComm implementation for RS485/Modbus RTU."""

    _DEFAULT_POLL_INTERVAL_SEC = 0.1
    _DEFAULT_BAUDRATE_GEAR = RS485_DEFAULT_BAUDRATE_GEAR
    SUPPORTED_BAUDRATE_GEARS = tuple(
        sorted(RS485_BAUDRATE_GEAR_MAP.keys(), reverse=True)
    )
    _LINUX_PORT_PATTERNS = (
        "/dev/serial/by-id/*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/ttyAMA*",
    )

    def __init__(self, config: ProductConfig):
        self._config = config
        self._profile = get_modbus_profile(config)
        self._slave_id = getattr(config, "slave_id", 0x31) or 0x31
        self._client: Any = None
        self._connected = False
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()
        self._callbacks: dict[int, tuple] = {}
        self._next_sub_id = 1
        self._lock = threading.Lock()
        self._io_lock = threading.RLock()
        self._poll_interval_sec = self._DEFAULT_POLL_INTERVAL_SEC

    def update_config(self, config: ProductConfig) -> None:
        """Update the cached product configuration."""
        self._config = config
        self._profile = get_modbus_profile(config)
        if not self._connected:
            self._slave_id = getattr(config, "slave_id", 0x31) or 0x31

    # ===== Connection management =====

    def _ensure_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("RS485 client not initialized")
        return self._client

    def _read_input_registers(
        self, address: int, count: int, device_id: int | None = None
    ):
        """Read input registers as one serialized Modbus transaction."""
        client = self._ensure_client()
        target_id = self._slave_id if device_id is None else device_id
        with self._io_lock:
            return client.read_input_registers(
                address, count=count, device_id=target_id
            )

    def _read_holding_registers(
        self, address: int, count: int, device_id: int | None = None
    ):
        """Read holding registers as one serialized Modbus transaction."""
        client = self._ensure_client()
        target_id = self._slave_id if device_id is None else device_id
        with self._io_lock:
            return client.read_holding_registers(
                address, count=count, device_id=target_id
            )

    def _write_register(self, address: int, value: int):
        """Write one holding register as one serialized Modbus transaction."""
        client = self._ensure_client()
        with self._io_lock:
            return client.write_register(address, value, device_id=self._slave_id)

    def _write_registers(self, address: int, values: list[int]):
        """Write multiple holding registers as one serialized Modbus transaction."""
        client = self._ensure_client()
        with self._io_lock:
            return client.write_registers(address, values, device_id=self._slave_id)

    @classmethod
    def _linux_serial_candidates(cls) -> list[str]:
        """Return common Linux serial/USB-RS485 device paths."""
        candidates: list[str] = []
        for pattern in cls._LINUX_PORT_PATTERNS:
            candidates.extend(str(path) for path in Path("/").glob(pattern.lstrip("/")))
        return candidates

    @staticmethod
    def _dedupe_ports(ports: list[str]) -> list[str]:
        """Deduplicate ports while preserving stable sorted output."""
        return sorted(dict.fromkeys(ports))

    def search_adapters(self) -> list[str]:
        """Search for available RS485 adapters.

        Returns:
            List of serial port names. On Linux, auto-discovery prefers USB
            adapters and stable ``/dev/serial/by-id`` aliases; built-in
            ``/dev/ttyS*`` ports are supported only when passed explicitly.
        """
        if serial is None:
            logger.warning("pyserial not available, cannot search adapters")
            return []
        ports = []
        for port in serial.tools.list_ports.comports():
            device = port.device
            if platform.system() == "Linux" and device.startswith("/dev/ttyS"):
                continue
            if platform.system() == "Windows":
                if port.vid == 0x3562 and port.pid in (0x0100, 0x0101, 0x0105):
                    continue
                if not port.vid or not port.pid:
                    continue
            ports.append(device)
        if platform.system() == "Linux":
            ports.extend(self._linux_serial_candidates())
        return self._dedupe_ports(ports)

    def _resolve_device_name(self, device_name: str) -> str | None:
        """Resolve an explicit or default RS485 serial device name."""
        if device_name:
            return device_name
        adapters = self.search_adapters()
        return adapters[0] if adapters else None

    def _log_linux_connect_hint(self, device_name: str, exc: Exception | None = None) -> None:
        """Log actionable Linux serial-port hints for common failures."""
        if platform.system() != "Linux":
            return

        detail = f": {exc}" if exc is not None else ""
        logger.error(
            "Failed to open RS485 serial port %s%s. "
            "On Linux, verify the device exists and your user has permission. "
            "Common checks: ls -l %s; add the user to the dialout group; "
            "or set a udev rule for the USB-RS485 adapter.",
            device_name,
            detail,
            device_name,
        )

    def connect(
        self,
        device_name: str,
        slave_id: int | None = None,
        baudrate_gear: int | None = None,
        quiet: bool = False,
    ) -> bool:
        """Connect to the specified RS485 device.

        Args:
            device_name: Serial port name (e.g., "COM3", "/dev/ttyUSB0").
            slave_id: Optional target slave ID. If provided, only this ID is
                used; otherwise the connection polls 0x31 and 0x32.
            baudrate_gear: Connection baud rate gear. If None, the value is
                taken from the ``GHAND_RS485_BAUDRATE_GEAR`` environment
                variable, falling back to the default gear (0x05).
            quiet: When True, suppress non-fatal failure logs. Useful when the
                caller is scanning several ports or baud rates.

        Returns:
            True if the connection succeeds, False otherwise.
        """
        if ModbusSerialClient is None:
            logger.error("pymodbus not available, cannot connect RS485 device")
            return False

        resolved_device = self._resolve_device_name(device_name)
        if resolved_device is None:
            if not quiet:
                logger.error("No RS485 serial adapters found")
            return False

        if baudrate_gear is None:
            baudrate_gear = int(
                os.environ.get("GHAND_RS485_BAUDRATE_GEAR", self._DEFAULT_BAUDRATE_GEAR)
            )

        baudrate = RS485_BAUDRATE_GEAR_MAP.get(baudrate_gear)
        if baudrate is None:
            if not quiet:
                logger.error("Invalid RS485 baudrate gear: %s", baudrate_gear)
            return False

        if self._connect_with_baudrate(resolved_device, slave_id, baudrate, quiet):
            logger.info(
                "Device connected via RS485 (%s, slave_id=0x%02X, baudrate_gear=0x%02X, baudrate=%s)",
                resolved_device,
                self._slave_id,
                baudrate_gear,
                baudrate,
            )
            return True
        return False

    def _connect_with_baudrate(
        self, device_name: str, slave_id: int | None, baudrate: int, quiet: bool
    ) -> bool:
        """Attempt a single RS485 connection with the given baud rate."""
        try:
            self._client = ModbusSerialClient(
                port=device_name,
                baudrate=baudrate,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=0.5,
            )
            if not self._client.connect():
                if not quiet:
                    self._log_linux_connect_hint(device_name)
                self._client.close()
                self._client = None
                return False
            slave_ids = [slave_id] if slave_id is not None else [0x31, 0x32]
            for target_slave_id in dict.fromkeys(slave_ids):
                if target_slave_id is None:
                    continue
                try:
                    result = self._read_holding_registers(
                        REG_SLAVE_ID, count=1, device_id=target_slave_id
                    )
                except ModbusException:
                    logger.debug("No response from RS485 slave 0x%02X", target_slave_id)
                    continue
                if result is not None and not result.isError():
                    self._slave_id = target_slave_id
                    break
            else:
                self._client.close()
                self._client = None
                if not quiet:
                    logger.error("No RS485 device responded on %s", device_name)
                return False
            self._connected = True
            return True
        except ModbusException as e:
            if not quiet:
                logger.error("Failed to connect to RS485 device: %s", e)
            if self._client:
                self._client.close()
                self._client = None
            return False
        except (OSError, ValueError) as e:
            if not quiet:
                self._log_linux_connect_hint(device_name, e)
            if self._client:
                self._client.close()
                self._client = None
            return False

    def disconnect(self) -> bool:
        """Disconnect from the RS485 device and stop subscriptions."""
        self._stop_poll()
        self._callbacks.clear()
        if self._client:
            with self._io_lock:
                self._client.close()
            self._client = None
        self._connected = False
        self._slave_id = 0x31
        logger.info("Device disconnected")
        return True

    def is_connected(self) -> bool:
        """Return whether the RS485 client is connected."""
        return self._connected

    def set_slave_id(self, slave_id: int) -> bool:
        """Write a new Modbus slave ID to holding register 0x0000."""
        if not 0 < slave_id <= 0xFF:
            raise ValueError("slave_id must be in range 1..255")
        try:
            result = self._write_register(REG_SLAVE_ID, slave_id)
        except Exception as exc:
            logger.error("Failed to set RS485 slave ID to 0x%02X: %s", slave_id, exc)
            return False
        if result is None or result.isError():
            return False
        self._slave_id = slave_id
        return True

    def set_baudrate_config(
        self,
        baudrate_gear: int | None = None,
    ) -> bool:
        """Write the baud rate gear to holding register 0x002C.

        The value is saved to Flash and takes effect after the next power-up.

        Args:
            baudrate_gear: Gear value written directly to the register. When
                omitted the default gear (0x05) is used.

        Returns:
            True if the device accepted the configuration.
        """
        gear = baudrate_gear if baudrate_gear is not None else RS485_DEFAULT_BAUDRATE_GEAR
        try:
            result = self._write_register(BAUDRATE_CONFIG_REGISTER, gear)
        except Exception as exc:
            logger.error("Failed to set RS485 baudrate config to gear 0x%02X: %s", gear, exc)
            return False
        return result is not None and not result.isError()

    # ===== Joint control (single register write) =====

    def move_joints(self, joints: list, mode) -> bool:
        """Send joint control commands via single register writes.

        Only writes registers for joints that are explicitly provided.

        Args:
            joints: List of JointCommand objects.
            mode: Control mode (position, speed, or torque).

        Returns:
            True if all commands are sent successfully.
        """
        if self._profile.mode_register is not None:
            mode_value = (mode.value << 8) & 0xFF00
            result = self._write_register(self._profile.mode_register, mode_value)
            if result is None or result.isError():
                raise RuntimeError("Failed to write mode register")

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

            result = self._write_registers(base_addr, registers)
            if result is None or result.isError():
                raise RuntimeError(
                    f"Failed to write joint {joint_id.name}"
                )

        return True

    def stop(self) -> bool:
        """Send an immediate stop command."""
        if self._profile.stop_register is not None:
            result = self._write_register(self._profile.stop_register, 0x0001)
            return result is not None and not result.isError()

        success = False
        for joint_id in self._config.valid_joints:
            base_addr = self._profile.joint_control_addresses.get(joint_id)
            if base_addr is None:
                continue
            result = self._write_register(base_addr, 0x0001)
            success = result is not None and not result.isError()
            if not success:
                return False
        return success

    # ===== State retrieval (batch read) =====

    def get_joints(self) -> list:
        """Retrieve the current state of all valid joints.

        Returns:
            List of JointData objects.
        """
        if not self._config.valid_joints:
            return []

        start, count = get_joint_input_span(self._config.valid_joints, self._profile)
        if count == 0:
            return []
        result = self._read_input_registers(start, count=count)
        if result is None or result.isError():
            raise RuntimeError("Failed to read joint registers")

        return parse_joints(
            list(result.registers),
            self._config.valid_joints,
            self._profile,
            start,
        )

    def get_hand_info(self) -> HandState:
        """Retrieve high-level hand status.

        Returns:
            HandState instance.
        """
        result = self._read_input_registers(self._profile.hand_info_address, count=2)
        if result is None or result.isError():
            raise RuntimeError("Failed to read hand info registers")

        raw = result.registers
        return parse_hand_info(raw)

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data.

        Returns:
            Dictionary mapping TactileSensorId to TactileInfo.
            Returns empty dict if product has no tactile support.
        """
        if not self._config.has_tactile:
            return {}

        result = self._read_input_registers(
            self._profile.tactile_state_address,
            count=self._profile.tactile_resultant_register_count,
        )
        if result is None or result.isError():
            raise RuntimeError("Failed to read tactile input registers")
        data = result.registers
        if len(data) < self._profile.tactile_resultant_register_count:
            raise RuntimeError("Tactile data insufficient")

        result = {}
        tactile_state, _ = parse_tactile_state_error(data)

        current_addr = (
            self._profile.tactile_state_address
            + self._profile.tactile_resultant_register_count
        )

        for region in self._config.tactile_regions:
            idx = region.id.value
            resultant = parse_tactile_resultant(data, idx)
            state_bit = (tactile_state & (1 << idx)) != 0

            # Read distributed force
            dist_regs = (region.count * 3 + 1) // 2
            dist_result = self._read_input_registers(current_addr, count=dist_regs)
            distributed = None
            if dist_result is not None and not dist_result.isError():
                dist_bytes = registers_to_bytes(dist_result.registers)
                distributed = parse_tactile_distributed(dist_bytes, region.count)

            current_addr += dist_regs

            result[region.id] = build_tactile_info(
                state_bit, resultant, distributed
            )
        return result

    # ===== Device info reading =====

    def _read_input_registers_bytes(self, address: int, count: int) -> bytes:
        """Read input registers and convert to bytes."""
        result = self._read_input_registers(address, count=count)
        if result is None or result.isError():
            raise RuntimeError(
                f"Failed to read input registers at {address:#x}"
            )
        return registers_to_bytes(result.registers)

    def get_device_name(self) -> str:
        """Retrieve the device name."""
        return self._get_string_info(REG_DEVICE_NAME, 8, parse_device_name)

    def get_hardware_version(self) -> str:
        """Retrieve the hardware version."""
        return self._get_string_info(REG_HARDWARE_VERSION, 8, parse_hardware_version)

    def get_firmware_version(self) -> str:
        """Retrieve the firmware version."""
        return self._get_string_info(REG_FIRMWARE_VERSION, 8, parse_firmware_version)

    def _get_string_info(self, register: int, count: int, parse) -> str:
        try:
            return parse(self._read_input_registers_bytes(register, count)) or "N/A"
        except Exception:
            return "N/A"

    def get_serial_number(self) -> str:
        """Retrieve the product serial number."""
        try:
            return parse_ascii_serial_number(
                self._read_input_registers_bytes(REG_IN_SERIAL_NUMBER, 10)
            )
        except Exception:
            return "N/A"

    def get_hand_type(self) -> int:
        """Retrieve the hand type.

        Returns:
            0 for unknown, 1 for left hand, 2 for right hand.
        """
        try:
            return parse_hand_type(self._read_input_registers_bytes(REG_HAND_TYPE, 1))
        except Exception:
            return 0

    def _get_packed_version(self, register: int) -> str:
        try:
            raw = self._read_input_registers_bytes(register, 1)
            if len(raw) < 2 or raw[:2] == b"\x00\x00":
                return "N/A"
            return parse_packed_firmware_version(raw)
        except Exception:
            return "N/A"

    def get_firmware_package_version(self) -> str:
        """Retrieve the firmware package version."""
        return self._get_packed_version(REG_IN_FIRMWARE_PACKAGE_VER)

    def get_position_sensor_version(self) -> str:
        """Retrieve the position sensor version."""
        return self._get_packed_version(REG_IN_POSITION_SENSOR_VER)

    def get_tactile_sensor_version(self) -> str:
        """Retrieve the tactile MCU version."""
        return self._get_packed_version(REG_IN_TACTILE_SENSOR_VER)

    def get_motor_driver_version(self) -> str:
        """Retrieve the motor driver version."""
        return self._get_packed_version(REG_IN_MOTOR_DRV_VER)

    def get_thumb_tactile_sensor_version(self) -> str:
        """Retrieve the thumb tactile sensor version."""
        return self._get_packed_version(REG_IN_THUMB_TACTILE_SENSOR_VER)

    def get_finger_tactile_sensor_version(self) -> str:
        """Retrieve the finger tactile sensor version."""
        return self._get_packed_version(REG_IN_FINGER_TACTILE_SENSOR_VER)

    # ===== Tactile sensor =====

    def open_tactile(self) -> bool:
        """Enable the tactile sensors."""
        return self._write_tactile_control(0x0100)

    def close_tactile(self) -> bool:
        """Disable the tactile sensors."""
        return self._write_tactile_control(0x0200)

    def zero_tactile(self) -> bool:
        """Zero-calibrate the tactile sensors."""
        return self._write_tactile_control(0x0400)

    def _write_tactile_control(self, command: int) -> bool:
        """Write tactile control command to the product-specific register.

        Args:
            command: High byte command value.
        """
        result = self._write_register(self._profile.tactile_control_address, command)
        return result is not None and not result.isError()

    # ===== Device operations =====

    def _wait_holding_result(
        self,
        address: int,
        timeout_sec: float = 2.0,
        interval_sec: float = 0.05,
    ) -> bool:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            result = self._read_holding_registers(address, count=1)
            if result is None or result.isError():
                return False
            status = result.registers[0] & 0x00FF
            if status == 1:
                return True
            if status == 2:
                return False
            time.sleep(interval_sec)
        return False

    def clear_fault(self) -> bool:
        """Clear device faults."""
        result = self._write_register(REG_CLEAR_FAULT, 0x0100)
        if result is None or result.isError():
            return False
        if not self._wait_holding_result(0x0001):
            logger.error("Fault clearance failed or timed out")
            return False
        logger.info("Fault cleared")
        return True

    def init_joint(self) -> bool:
        """Initialize joint positions."""
        result = self._write_register(REG_INIT_JOINT, 0x0001)
        if result is None or result.isError():
            return False
        logger.info("Joint initialization completed")
        return True

    # ===== Self-test error query =====

    def _self_test_read_registers(self, address: int, count: int) -> list[int]:
        result = self._read_holding_registers(address, count=count)
        if result is None or result.isError():
            raise RuntimeError(
                f"RS485 self-test read failed at 0x{address:04X}"
            )
        return list(result.registers)

    def _self_test_write_register(self, address: int, value: int) -> None:
        result = self._write_register(address, value)
        if result is None or result.isError():
            raise RuntimeError(
                f"RS485 self-test write failed at 0x{address:04X}"
            )

    def get_self_test_error_info(self) -> SelfTestErrorInfo:
        """Query self-test error information via holding registers 0x0038~0x003F."""
        return build_self_test_error_info(
            self._config,
            self._self_test_read_registers,
            self._self_test_write_register,
        )

    def get_self_test_status(self) -> int:
        """Read the current self-test status from holding register 0x0038 low byte."""
        return self._self_test_read_registers(0x0038, 1)[0] & 0x00FF

    # ===== Subscription =====

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
        """Unsubscribe from data updates.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription was removed successfully.
        """
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
        """Start the polling thread if not already running."""
        if self._poll_thread is None or not self._poll_thread.is_alive():
            self._poll_stop.clear()
            self._poll_thread = threading.Thread(
                target=self._poll_loop, daemon=True
            )
            self._poll_thread.start()

    def _stop_poll(self) -> None:
        """Signal the polling thread to stop."""
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
        """Poll device state every 10ms and dispatch to callbacks."""
        while not self._poll_stop.is_set():
            try:
                if not self._connected or self._client is None:
                    break

                # Read hand info + joints in one batch
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
                result = self._read_input_registers(start, count=count)
                if result is None or result.isError():
                    raise ConnectionError("RS485 device did not respond")

                raw = list(result.registers)
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
