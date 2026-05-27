# Copyright (c) 2026 GLITech
#
# Licensed under the MIT License. See LICENSE in the project root for license information.

"""RS485 communication implementation using Modbus RTU."""

from __future__ import annotations

import logging
import struct
import threading
import time
import types
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
    CommunicationError,
    ErrorCode,
    HandState,
    JointData,
    JointId,
    ProductConfig,
    State,
    TactileInfo,
)
from .icomm import IComm

logger = logging.getLogger("ghand.rs485_comm")


# Max registers per Modbus read (Modbus standard limit)
_MAX_READ_REGISTERS = 125


def _crc16(data: bytes) -> int:
    """Compute Modbus CRC16."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

# Mapping from controlled joint ID to holding register base address
_HOLDING_REG_MAP = {
    JointId.THUMB_PIP: 0x0011,
    JointId.THUMB_MCP: 0x0013,
    JointId.THUMB_SWING: 0x0015,
    JointId.THUMB_ROTATION: 0x0017,
    JointId.FF_PIP: 0x0019,
    JointId.FF_MCP: 0x001B,
    JointId.FF_SWING: 0x001D,
    JointId.MF_PIP: 0x001F,
    JointId.MF_MCP: 0x0021,
    JointId.RF_PIP: 0x0023,
    JointId.RF_MCP: 0x0025,
    JointId.LF_PIP: 0x0027,
    JointId.LF_MCP: 0x0029,
}


class Rs485Comm(IComm):
    """IComm implementation for RS485/Modbus RTU."""

    def __init__(self, config: ProductConfig):
        self._config = config
        self._slave_id = 0x71
        self._client: Any = None
        self._connected = False
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()
        self._callbacks: dict[int, tuple] = {}
        self._next_sub_id = 1
        self._lock = threading.Lock()

    def update_config(self, config: ProductConfig) -> None:
        """Update the cached product configuration."""
        self._config = config
        # self._slave_id = getattr(config, "slave_id", 0x71)

    @staticmethod
    def _registers_to_bytes(registers: list[int]) -> bytes:
        """Convert a list of uint16 registers to bytes (preserving received byte order)."""
        return b"".join(struct.pack(">H", reg) for reg in registers)

    # ===== Connection management =====

    def _ensure_client(self) -> Any:
        if self._client is None:
            raise CommunicationError("RS485 client not initialized")
        return self._client

    def search_adapters(self) -> list[str]:
        """Search for available RS485 adapters.

        Returns:
            List of verified serial port names.
        """
        if serial is None:
            logger.warning("pyserial not available, cannot search adapters")
            return []
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect(self, device_name: str) -> bool:
        """Connect to the specified RS485 device.

        Args:
            device_name: Serial port name (e.g., "COM3", "/dev/ttyUSB0").

        Returns:
            True if the connection succeeds, False otherwise.
        """
        try:
            self._client = ModbusSerialClient(
                port=device_name,
                baudrate=1000000,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=1.0,
            )
            if not self._client.connect():
                return False
            # Verify device by reading slave ID holding register
            result = self._client.read_holding_registers(
                0x0000, count=1, device_id=self._slave_id
            )
            if result is None or result.isError():
                self._client.close()
                self._client = None
                return False
            self._slave_id = result.registers[0]
            self._connected = True
            logger.info("Device connected via RS485 (%s)", device_name)
            return True
        except ModbusException as e:
            logger.error("Failed to connect to RS485 device: %s", e)
            if self._client:
                self._client.close()
                self._client = None
            return False

    def disconnect(self) -> bool:
        """Disconnect from the RS485 device and stop subscriptions."""
        self._stop_poll()
        self._callbacks.clear()
        if self._client:
            self._client.close()
            self._client = None
        self._connected = False
        self._slave_id = 0x71
        logger.info("Device disconnected")
        return True

    def is_connected(self) -> bool:
        """Return whether the RS485 client is connected."""
        return self._connected

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
        client = self._ensure_client()
        try:
            # Write mode register (high byte = mode, low byte = 0)
            mode_value = (mode.value << 8) & 0xFF00
            result = client.write_register(0x0010, mode_value, device_id=self._slave_id)
            if result is None or result.isError():
                raise CommunicationError("Failed to write mode register")

            for joint in joints:
                joint_id = JointId(joint.id)
                if joint_id not in _HOLDING_REG_MAP:
                    continue
                base_addr = _HOLDING_REG_MAP[joint_id]
                reg0 = int(joint.angle * 10)
                reg1 = ((joint.speed & 0xFF) << 8) | (joint.torque & 0xFF)

                result = client.write_registers(
                    base_addr, [reg0, reg1], device_id=self._slave_id
                )
                if result is None or result.isError():
                    raise CommunicationError(
                        f"Failed to write joint {joint_id.name}"
                    )

            return True
        except ModbusException as e:
            raise CommunicationError(f"RS485 move_joints failed: {e}") from e

    def stop(self) -> bool:
        """Send an immediate stop command."""
        client = self._ensure_client()
        try:
            result = client.write_register(0x0010, 0x0001, device_id=self._slave_id)
            return result is not None and not result.isError()
        except ModbusException as e:
            raise CommunicationError(f"RS485 stop failed: {e}") from e

    # ===== State retrieval (batch read) =====

    def get_joints(self) -> list:
        """Retrieve the current state of all valid joints.

        Returns:
            List of JointData objects.
        """
        client = self._ensure_client()
        if not self._config.valid_joints:
            return []

        try:
            max_id = max(j.value for j in self._config.valid_joints)
            count = (max_id + 1) * 3
            result = client.read_input_registers(
                0x1023, count=count, device_id=self._slave_id
            )
            if result is None or result.isError():
                raise CommunicationError("Failed to read joint registers")

            raw = result.registers
            joints = []
            for joint_id in self._config.valid_joints:
                offset = joint_id.value * 3
                if offset + 2 >= len(raw):
                    continue
                joint = self._parse_joint_data(raw, offset, joint_id.value)
                joints.append(joint)
            return joints
        except ModbusException as e:
            raise CommunicationError(f"RS485 get_joints failed: {e}") from e

    def _parse_joint_data(self, raw: list[int], offset: int, joint_id: int) -> JointData:
        """Parse 3 input registers into JointData."""
        status_byte = (raw[offset] >> 8) & 0xFF
        error_byte = raw[offset] & 0xFF
        angle = raw[offset + 1] / 10.0
        speed = (raw[offset + 2] >> 8) & 0xFF
        if speed >= 128:
            speed -= 256
        torque = raw[offset + 2] & 0xFF
        if torque >= 128:
            torque -= 256
        return JointData(
            id=joint_id,
            state=State(status_byte),
            error=ErrorCode(error_byte),
            angle=angle,
            speed=speed,
            torque=torque,
        )

    def get_hand_info(self) -> HandState:
        """Retrieve high-level hand status.

        Returns:
            HandState instance.
        """
        client = self._ensure_client()
        try:
            result = client.read_input_registers(
                0x1021, count=2, device_id=self._slave_id
            )
            if result is None or result.isError():
                raise CommunicationError("Failed to read hand info registers")

            raw = result.registers
            state_byte = (raw[0] >> 8) & 0xFF
            error_byte = raw[0] & 0xFF
            temperature = raw[1]
            return HandState(
                state=State(state_byte),
                error=ErrorCode(error_byte),
                temperature=temperature,
            )
        except ModbusException as e:
            raise CommunicationError(f"RS485 get_hand_info failed: {e}") from e

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data.

        Returns:
            Dictionary mapping TactileSensorId to TactileInfo.
            Returns empty dict if product has no tactile support.
        """
        if not self._config.has_tactile:
            return {}

        client = self._ensure_client()
        try:
            result = client.read_input_registers(
                0x1080, count=16, device_id=self._slave_id
            )
            if result is None or result.isError():
                raise CommunicationError("Failed to read tactile input registers")
            data = result.registers
            if len(data) < 16:
                raise CommunicationError("Tactile data insufficient")

            result = {}
            tactile_state = (data[0] >> 8) & 0xFF
            tactile_error = data[0] & 0xFF

            current_addr = 0x1080 + 16

            for region in self._config.tactile_regions:
                idx = region.id.value
                base = 1 + idx * 3
                raw_fx = (data[base] >> 8) & 0xFF
                fx = (raw_fx - 0x100) / 10.0 if raw_fx >= 0x80 else raw_fx / 10.0
                raw_fy = (data[base + 1] >> 8) & 0xFF
                fy = (raw_fy - 0x100) / 10.0 if raw_fy >= 0x80 else raw_fy / 10.0
                fz = ((data[base + 2] >> 8) & 0xFF) / 10.0
                state_bit = (tactile_state & (1 << region.id.value)) != 0

                # Read distributed force
                dist_regs = (region.count * 3 + 1) // 2
                dist_result = client.read_input_registers(
                    current_addr, count=dist_regs, device_id=self._slave_id
                )
                distributed = None
                if dist_result is not None and not dist_result.isError():
                    dist_bytes = self._registers_to_bytes(dist_result.registers)
                    distributed = []
                    for i in range(0, len(dist_bytes) - 2, 3):
                        fx_d = dist_bytes[i]
                        fy_d = dist_bytes[i + 1]
                        fz_d = dist_bytes[i + 2]
                        if fx_d >= 0x80:
                            fx_d -= 0x100
                        if fy_d >= 0x80:
                            fy_d -= 0x100
                        distributed.extend([fx_d, fy_d, fz_d])

                current_addr += dist_regs

                result[region.id] = TactileInfo(
                    state=state_bit,
                    resultant_force=[fx, fy, fz],
                    distributed_force=distributed,
                )
            return result
        except ModbusException as e:
            raise CommunicationError(f"RS485 get_tactile_data failed: {e}") from e

    def _read_holding_registers_chunked(
        self, address: int, count: int
    ) -> list[int]:
        """Read holding registers in chunks of _MAX_READ_REGISTERS."""
        client = self._ensure_client()
        data = []
        offset = 0
        while offset < count:
            chunk = min(_MAX_READ_REGISTERS, count - offset)
            result = client.read_holding_registers(
                address + offset, count=chunk, device_id=self._slave_id
            )
            if result is None or result.isError():
                raise CommunicationError(
                    f"Failed to read holding registers at {address + offset}"
                )
            data.extend(result.registers)
            offset += chunk
        return data

    # ===== Device info reading =====

    def _read_input_registers_bytes(self, address: int, count: int) -> bytes:
        """Read input registers and convert to bytes."""
        client = self._ensure_client()
        result = client.read_input_registers(
            address, count=count, device_id=self._slave_id
        )
        if result is None or result.isError():
            raise CommunicationError(
                f"Failed to read input registers at {address:#x}"
            )
        return self._registers_to_bytes(result.registers)

    def get_device_name(self) -> str:
        """Retrieve the device name."""
        raw_bytes = self._read_input_registers_bytes(0x1000, 8)
        return raw_bytes.decode("utf-8", errors="ignore").strip("\x00")

    def get_hardware_version(self) -> str:
        """Retrieve the hardware version."""
        raw_bytes = self._read_input_registers_bytes(0x1008, 8)
        return raw_bytes.decode("utf-8", errors="ignore").strip("\x00")

    def get_firmware_version(self) -> str:
        """Retrieve the firmware version."""
        raw_bytes = self._read_input_registers_bytes(0x1010, 8)
        return raw_bytes.decode("utf-8", errors="ignore").strip("\x00")

    def get_serial_number(self) -> int:
        """Retrieve the product serial number."""
        raw_bytes = self._read_input_registers_bytes(0x1018, 8)
        return int.from_bytes(raw_bytes, byteorder="little")

    def get_hand_type(self) -> int:
        """Retrieve the hand type.

        Returns:
            0 for unknown, 1 for left hand, 2 for right hand.
        """
        
        raw_bytes = self._read_input_registers_bytes(0x1020, 1)
        return int.from_bytes(raw_bytes, byteorder="big")

    def get_motor_driver_version(self) -> tuple:
        """Retrieve the motor driver version."""
        client = self._ensure_client()
        try:
            data = self._read_holding_registers_chunked(0x2007, 3)
            return (
                self._decode_u16(data[0]),
                self._decode_u16(data[1]),
                self._decode_u16(data[2]),
            )
        except ModbusException as e:
            raise CommunicationError(
                f"RS485 get_motor_driver_version failed: {e}"
            ) from e

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
        """Write tactile control command to holding register 0x002B.

        Args:
            command: High byte command value.
        """
        client = self._ensure_client()
        try:
            result = client.write_register(
                0x002B, command, device_id=self._slave_id
            )
            return result is not None and not result.isError()
        except ModbusException as e:
            raise CommunicationError(
                f"RS485 tactile control failed: {e}"
            ) from e

    # ===== Device operations =====

    def clear_fault(self) -> bool:
        """Clear device faults."""
        client = self._ensure_client()
        try:
            result = client.write_register(
                0x0001, 0x0100, device_id=self._slave_id
            )
            if result is None or result.isError():
                return False
            logger.info("Fault cleared")
            return True
        except ModbusException as e:
            raise CommunicationError(f"RS485 clear_fault failed: {e}") from e

    def init_joint(self) -> bool:
        """Initialize joint positions."""
        client = self._ensure_client()
        try:
            result = client.write_register(
                0x0002, 0x0001, device_id=self._slave_id
            )
            if result is None or result.isError():
                return False
            logger.info("Joint initialization completed")
            return True
        except ModbusException as e:
            raise CommunicationError(f"RS485 init_joint failed: {e}") from e

    # ===== Subscription =====

    def subscribe(self, callback, *args, **kwargs) -> int:
        """Subscribe to device data updates.

        Args:
            callback: Callable invoked with a device data object when new data arrives.

        Returns:
            Subscription ID.
        """
        def wrapper(hand_state, joints, *w_args, **w_kwargs):
            data = types.SimpleNamespace()
            data.hand = hand_state
            for joint in joints:
                jid = JointId(joint.id)
                setattr(data, jid.name.lower(), joint)
            callback(data, *w_args, **w_kwargs)

        with self._lock:
            sub_id = self._next_sub_id
            self._next_sub_id += 1
            self._callbacks[sub_id] = (wrapper, args, kwargs)
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
            if sub_id in self._callbacks:
                del self._callbacks[sub_id]
                if not self._callbacks:
                    self._stop_poll()
                return True
            return False

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
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=0.5)
        self._poll_thread = None

    def _poll_loop(self) -> None:
        """Poll device state every 10ms and dispatch to callbacks."""
        while not self._poll_stop.is_set():
            try:
                if not self._connected or self._client is None:
                    time.sleep(0.01)
                    continue

                # Read hand info + joints in one batch
                if not self._config.valid_joints:
                    time.sleep(0.01)
                    continue

                max_id = max(j.value for j in self._config.valid_joints)
                count = 2 + (max_id + 1) * 3  # hand info (2) + joints
                result = self._client.read_input_registers(
                    0x1021, count=count, device_id=self._slave_id
                )
                if result is None or result.isError():
                    time.sleep(0.01)
                    continue

                raw = result.registers
                hand_state = HandState(
                    state=State((raw[0] >> 8) & 0xFF),
                    error=ErrorCode(raw[0] & 0xFF),
                    temperature=raw[1],
                )

                joints = []
                for joint_id in self._config.valid_joints:
                    offset = 2 + joint_id.value * 3
                    if offset + 2 >= len(raw):
                        continue
                    joints.append(
                        self._parse_joint_data(raw, offset, joint_id.value)
                    )

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
