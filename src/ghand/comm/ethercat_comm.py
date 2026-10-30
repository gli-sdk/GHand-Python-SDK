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
"""EtherCAT communication implementation.

Wraps EthercatClient and handles PDO encoding/decoding.
"""

import logging
import struct
import time

from .._subscription import SubscriptionManager
from .._product_config import ProductConfig, TactileRegionConfig
from .._device_value import parse_device_value
from ..types import (
    JointId,
    HandControlMode,
    JointControlMode,
    JointLoopType,
    JointControlState,
    JointState,
    HandControlState,
    JointErrorCode,
    JointCommand,
    DeviceData,
    HandData,
    HandFault,
    HandWarning,
    HandCriticalError,
    HandRuntimeState,
    JointData,
    TactileData,
)
from .ethercat_client import EthercatClient
from .ethercat_protocol import (
    Rpdo,
    Tpdo,
    HandTpdo,
    compute_tpdo_size,
)
from .icomm import IComm

logger = logging.getLogger("ghand.ethercat_comm")


class EtherCATComm(IComm):
    """IComm implementation for EtherCAT."""

    _COMPAT_THUMB_TACTILE_COUNT = 28
    _SDO_WRITE_SETTLE_SEC = 0.02
    _SDO_POLL_INTERVAL_SEC = 0.01
    _SDO_POLL_TIMEOUT_SEC = 1.0

    def __init__(self, config: ProductConfig):
        self._client = EthercatClient()
        self._sub_manager = SubscriptionManager(self._client, self.is_connected)
        self.update_config(config)

    @property
    def config(self) -> ProductConfig:
        """Return the active product config selected for the mapped PDO layout."""
        return self._config

    def _clone_config_with_tactile_counts(self, config: ProductConfig,
                                          tactile_counts: list[int]) -> ProductConfig:
        """Clone product config while replacing tactile region sample counts."""
        tactile_regions = [
            TactileRegionConfig(id=region.id, count=count)
            for region, count in zip(config.tactile_regions, tactile_counts)
        ]
        return ProductConfig(
            name=config.name,
            model=config.model,
            all_joints=list(config.all_joints),
            active_joints=config.active_joints.copy(),
            has_tactile=config.has_tactile,
            tactile_regions=tactile_regions,
            product_type=config.product_type,
        )

    def _expected_rpdo_bytes(self, config: ProductConfig) -> int:
        """Return the expected EtherCAT RPDO byte size for the product."""
        return 2 + len(self._controlled_joints) * 12

    def _build_tpdo_layouts(self, config: ProductConfig) -> dict[int, ProductConfig]:
        """Build supported TPDO layouts keyed by mapped input size."""
        tactile_counts = [r.count for r in config.tactile_regions] if config.has_tactile else None
        layouts = {compute_tpdo_size(len(config.all_joints), tactile_counts): config}
        if config.has_tactile and tactile_counts and tactile_counts[
                0] > self._COMPAT_THUMB_TACTILE_COUNT:
            compat_counts = list(tactile_counts)
            compat_counts[0] = self._COMPAT_THUMB_TACTILE_COUNT
            compat_config = self._clone_config_with_tactile_counts(config, compat_counts)
            layouts[compute_tpdo_size(len(config.all_joints), compat_counts)] = compat_config
        return layouts

    def _select_tpdo_layout(self, input_size: int) -> None:
        """Select the active parser layout from the actual mapped input size."""
        layout = self._tpdo_layouts.get(input_size)
        if layout is None:
            return
        self._config = layout
        self._expected_tpdo_size = input_size
        self._tpdo_size_selected = True

    def update_config(self, config: ProductConfig) -> None:
        """Update the cached product configuration and derived constants."""
        self._config = config
        self._tpdo_layouts = self._build_tpdo_layouts(config)
        self._expected_tpdo_sizes = tuple(sorted(self._tpdo_layouts))
        self._expected_tpdo_size = compute_tpdo_size(
            len(config.all_joints),
            [r.count for r in config.tactile_regions] if config.has_tactile else None,
        )
        self._tpdo_size_selected = False
        self._controlled_joints = [j for j in config.all_joints if j in config.active_joints]
        self._rpdo = Rpdo(self._controlled_joints)
        self._expected_rpdo_size = self._expected_rpdo_bytes(config)

    # ===== Connection management =====

    def search_adapters(self) -> list[str]:
        """Search for available EtherCAT adapters.

        Returns:
            List of adapter IDs.
        """
        return self._client.search()

    def connect(
        self,
        device_name: str,
        slave_id: int | None = None,
        baudrate: int | None = None,
    ) -> bool:
        """Connect to the specified EtherCAT device.

        Args:
            device_name: Adapter ID to connect to.
            slave_id: Ignored for EtherCAT.
            baudrate: Ignored for EtherCAT.

        Returns:
            True if the connection and SOEM startup succeed.
        """
        connected = self._client.connect(device_name)
        if connected and self._client.run(self._expected_tpdo_sizes, self._expected_rpdo_size):
            self._select_tpdo_layout(self._client.input_size)
            return True

        # logger.error("Failed to connect EtherCAT device %s", device_name)
        self._client.disconnect()
        return False

    def disconnect(self) -> bool:
        """Disconnect from the EtherCAT device and stop subscriptions."""
        self._sub_manager.stop()
        self._client.disconnect()
        logger.info("Device disconnected")
        return True

    def is_connected(self) -> bool:
        """Return whether the EtherCAT client is connected."""
        return self._client._connected and not self._client._connection_lost

    # ===== Joint control =====

    def move_joints(self, joints: list[JointCommand], mode: HandControlMode) -> bool:
        """Send joint control commands via RPDO.

        Args:
            joints: List of JointCommand objects.
            mode: Control mode (position, velocity, or current).

        Returns:
            True if the command is sent successfully.
        """
        self._rpdo.mode = mode.value
        self._rpdo.stop = 1

        for joint in joints:
            target = self._rpdo.joints[joint.id]
            target.mode = (joint.control_mode.value & 0x0F) | (joint.loop_type.value << 4)
            target.stop = joint.control_state.value
            target.angle = joint.angle
            target.velocity = joint.velocity
            target.current = joint.current
            target.kp = joint.kp
            target.kd = joint.kd

        self._client.send_data(self._rpdo.to_bytes())
        return True

    def disable_hand(self) -> bool:
        """Disable all active joints at the hand-control level."""
        self._rpdo.stop = 0
        self._client.send_data(self._rpdo.to_bytes())
        return True

    def stop(self) -> bool:
        """Send an immediate stop command to all joints."""
        self._rpdo.stop = 1
        for joint in self._rpdo.joints.values():
            joint.stop = JointControlState.STOPPED
        self._client.send_data(self._rpdo.to_bytes())
        return True

    # ===== State retrieval =====

    def _validate_tpdo_data(self, data: bytes) -> bytes:
        """Validate a TPDO frame before any protocol fields are decoded."""
        expected_sizes = ((self._expected_tpdo_size, )
                          if self._tpdo_size_selected else self._expected_tpdo_sizes)
        if len(data) not in expected_sizes:
            raise RuntimeError("Invalid EtherCAT TPDO length: "
                               f"expected one of {expected_sizes}, got {len(data)}")
        return data

    def _recv_tpdo_data(self) -> bytes:
        """Return one valid TPDO frame with the configured mapped size."""
        return self._validate_tpdo_data(self._client.recv_data())

    def get_joints(self) -> list[JointData]:
        """Retrieve the current state of all joints from TPDO.

        Returns:
            List of JointData objects.
        """
        data = self._recv_tpdo_data()

        tpdo = Tpdo.from_bytes(data, self._config)

        joints = []
        for joint_id, joint_tpdo in tpdo.joints.items():
            angle = joint_tpdo.angle
            if abs(angle) < 1e-10:
                angle = 0.0
            joints.append(
                JointData(
                    id=joint_id,
                    state=parse_device_value(JointState, joint_tpdo.state),
                    error=parse_device_value(JointErrorCode, joint_tpdo.error),
                    control_mode=parse_device_value(JointControlMode, joint_tpdo.mode & 0x0F),
                    loop_type=parse_device_value(JointLoopType, joint_tpdo.mode >> 4),
                    angle=angle,
                    velocity=joint_tpdo.velocity,
                    current=joint_tpdo.current,
                ))
        return joints

    def get_hand_info(self) -> HandData:
        """Retrieve high-level hand status from TPDO.

        Returns:
            HandData instance.
        """
        data = self._recv_tpdo_data()

        hand_tpdo = HandTpdo.from_bytes(data)
        return HandData(
            joints_state=parse_device_value(HandControlState, hand_tpdo.state),
            error_warn=HandWarning(int.from_bytes(hand_tpdo.error_warn, "little")),
            error_fault=HandFault(int.from_bytes(hand_tpdo.error_fault, "little")),
            error_critical=HandCriticalError(int.from_bytes(hand_tpdo.error_critical, "little")),
            temperature=hand_tpdo.temperature,
        )

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data from TPDO.

        Returns:
            Dictionary mapping TactileSensorId to TactileData.
        """
        data = self._recv_tpdo_data()
        if len(data) < self._expected_tpdo_size:
            raise RuntimeError(
                "Data length insufficient. Expected %s bytes, got %s bytes",
                self._expected_tpdo_size,
                len(data),
            )

        tpdo = Tpdo.from_bytes(data, self._config)
        result = {}
        for region in self._config.tactile_regions:
            tactile = getattr(tpdo, f"{region.id.name.lower()}_tactile")
            result[region.id] = TactileData(
                state=bool(tpdo.tactile_state.state & (1 << region.id.value)),
                resultant_force=tactile.resultant_force,
                distributed_force=tactile.sample_force,
            )
        return result

    # ===== Tactile sensor =====

    def _execute_sdo_command(
        self,
        index: int,
        command: int,
        command_subindex: int = 0x01,
        state_subindex: int = 0x02,
        result_subindex: int = 0x03,
    ) -> bool:
        self._client.sdo_write(index, command_subindex, bytes([command]))
        time.sleep(self._SDO_WRITE_SETTLE_SEC)

        deadline = time.monotonic() + self._SDO_POLL_TIMEOUT_SEC
        while time.monotonic() < deadline:
            state_raw = self._client.sdo_read(index, state_subindex)
            state = state_raw[0] if state_raw else 0
            if state == 0:
                result_raw = self._client.sdo_read(index, result_subindex)
                result = result_raw[0] if result_raw else 0
                if result:
                    if result != 1:
                        logger.error("SDO command 0x%04X failed with result %d", index, result)
                    return result == 1
            time.sleep(self._SDO_POLL_INTERVAL_SEC)

        logger.error("SDO command 0x%04X timed out", index)
        return False

    def open_tactile(self) -> bool:
        """Enable the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.
        """
        return self._execute_sdo_command(0x2004, 0x01)

    def close_tactile(self) -> bool:
        """Disable the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.
        """
        return self._execute_sdo_command(0x2004, 0x02)

    def zero_tactile(self) -> bool:
        """Zero-calibrate the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.
        """
        return self._execute_sdo_command(0x2004, 0x04)

    # ===== Device operations =====

    def clear_fault(self) -> bool:
        """Clear device faults.

        Returns:
            True on success, False if the device rejected the command.
        """
        success = self._execute_sdo_command(0x2002, 0x01)
        if success:
            logger.info("Fault cleared")
        return success

    def get_device_name(self) -> str:
        """Retrieve the device name via SDO."""
        return self._read_string_sdo(0x1008, 0x00)

    def get_firmware_version(self) -> str:
        """Retrieve the firmware version via SDO."""
        return self._read_packed_firmware_version(0x01)

    def _read_string_sdo(self, index: int, subindex: int) -> str:
        try:
            return (self._client.sdo_read(index, subindex).decode(
                "utf-8", errors="ignore").strip("\x00") or "N/A")
        except Exception:
            if not self.is_connected():
                raise
            return "N/A"

    def get_serial_number(self) -> str:
        """Retrieve the 19-byte ASCII product serial number via SDO."""
        try:
            raw = self._client.sdo_read(0x2009, 0x00)
            return raw[:19].decode("ascii", errors="ignore").strip("\x00")
        except Exception:
            if not self.is_connected():
                raise
            return "N/A"

    @staticmethod
    def _pack_uint_array(values: list[int], count: int, item_format: str) -> bytes:
        if len(values) != count:
            raise ValueError(f"expected {count} values, got {len(values)}")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("parameter values must be integers")
        try:
            return struct.pack(f"<{count}{item_format}", *values)
        except struct.error as exc:
            raise ValueError(str(exc)) from exc

    @staticmethod
    def _unpack_uint_array(raw: bytes, count: int, item_format: str) -> list[int]:
        expected_size = struct.calcsize(f"<{count}{item_format}")
        if len(raw) != expected_size:
            raise RuntimeError(
                f"invalid SDO parameter size: expected {expected_size}, got {len(raw)}")
        return list(struct.unpack(f"<{count}{item_format}", raw))

    def _write_sdo_parameters(self, index: int, payload: bytes) -> bool:
        self._client.sdo_write(index, 0x01, payload)
        if self._client.sdo_read(index, 0x01) != payload:
            logger.error("SDO parameter readback mismatch at index 0x%04X", index)
            return False
        return self._execute_sdo_command(
            index,
            0xA1,
            command_subindex=0x02,
            state_subindex=0x03,
            result_subindex=0x04,
        )

    def get_stall_tolerances(self) -> dict[JointId, int]:
        """Read the 13 per-joint stall tolerances from SDO 0x2003:01."""
        if not self._execute_sdo_command(
                0x2003,
                0xA2,
                command_subindex=0x02,
                state_subindex=0x03,
                result_subindex=0x04,
        ):
            raise RuntimeError("Failed to refresh stall tolerances")
        values = self._unpack_uint_array(self._client.sdo_read(0x2003, 0x01), 13, "B")
        return dict(zip(self._controlled_joints, values))

    def set_stall_tolerances(self, tolerances: dict[JointId, int]) -> bool:
        """Write all 13 per-joint stall tolerances through SDO 0x2003."""
        if set(tolerances) != set(self._controlled_joints):
            raise ValueError("stall tolerances must contain all 13 active JointId keys")
        values = [tolerances[joint_id] for joint_id in self._controlled_joints]
        return self._write_sdo_parameters(
            0x2003,
            self._pack_uint_array(values, 13, "B"),
        )

    def get_pid_parameters(self) -> list[int]:
        """Read the raw 39-value uint16 PID array from SDO 0x2008:01."""
        if not self._execute_sdo_command(
                0x2008,
                0xA2,
                command_subindex=0x02,
                state_subindex=0x03,
                result_subindex=0x04,
        ):
            raise RuntimeError("Failed to refresh PID parameters")
        return self._unpack_uint_array(self._client.sdo_read(0x2008, 0x01), 39, "H")

    def set_pid_parameters(self, parameters: list[int]) -> bool:
        """Write the raw 39-value uint16 PID array through SDO 0x2008."""
        return self._write_sdo_parameters(
            0x2008,
            self._pack_uint_array(parameters, 39, "H"),
        )

    def get_hand_state_machine(self) -> HandRuntimeState | int:
        """Read the whole-hand runtime state from SDO 0x200A:00."""
        raw = self._client.sdo_read(0x200A, 0x00)
        if len(raw) != 1:
            raise RuntimeError(f"invalid hand state machine size: expected 1, got {len(raw)}")
        return parse_device_value(HandRuntimeState, raw[0])

    def _read_packed_firmware_version(self, subindex: int) -> str:
        """Read a packed firmware version from SDO 0x2007."""
        try:
            raw = self._client.sdo_read(0x2007, subindex)
        except Exception:
            if not self.is_connected():
                raise
            logger.info("Packed firmware version not available", exc_info=True)
            return "N/A"

        if len(raw) < 2 or raw[:2] == b"\x00\x00":
            return "N/A"
        value = int.from_bytes(raw[:2], byteorder="little")
        version_high = (value >> 8) & 0xFF
        version_low = value & 0xFF
        major = (version_high >> 5) & 0x07
        minor = version_high & 0x1F
        patch = (version_low >> 4) & 0x0F
        return f"V{major}.{minor}.{patch}"

    def get_firmware_package_version(self) -> str:
        """Retrieve the firmware package version via SDO."""
        return self._read_packed_firmware_version(0x05)

    def get_position_sensor_version(self) -> str:
        """Retrieve the position sensor version via SDO."""
        return self._read_packed_firmware_version(0x02)

    def get_tactile_sensor_version(self) -> str:
        """Retrieve the tactile MCU version via SDO."""
        return self._read_packed_firmware_version(0x03)

    def get_motor_driver_version(self) -> str:
        """Retrieve the motor driver version via SDO.

        Returns "N/A" if the motor driver version is not available.
        """
        return self._read_packed_firmware_version(0x04)

    def get_thumb_tactile_sensor_version(self) -> str:
        """Retrieve the thumb tactile sensor version via SDO."""
        return self._read_packed_firmware_version(0x06)

    def get_finger_tactile_sensor_version(self) -> str:
        """Retrieve the four-finger tactile sensor version via SDO."""
        return self._read_packed_firmware_version(0x07)

    def get_hand_type(self) -> int:
        """Retrieve the hand type via SDO.

        Returns:
            0 for unknown, 1 for left hand, 2 for right hand.
        """
        try:
            return int.from_bytes(self._client.sdo_read(0x2001, 0x00), byteorder="little")
        except Exception:
            if not self.is_connected():
                raise
            return 0

    # ===== Subscription =====

    def subscribe(self, callback, *args, **kwargs) -> int:
        """Subscribe to device data updates.

        The callback receives raw TPDO bytes.  The caller is responsible for
        parsing (e.g. via ``Tpdo.from_bytes``).

        Args:
            callback: Callable invoked with raw ``bytes``.

        Returns:
            Subscription ID.
        """
        if not self.is_connected():
            raise RuntimeError("Device is not connected")

        return self._sub_manager.subscribe(callback, *args, **kwargs)

    def subscribe_device_data(
        self,
        callback,
        *,
        include_tactile: bool = False,
        interval_ms: int | None = None,
    ) -> int:
        """Subscribe to unified ``DeviceData`` updates."""

        def adapter(data_bytes, *args, **kwargs):
            tpdo = Tpdo.from_bytes(data_bytes, self._config)
            hand = HandData(
                joints_state=parse_device_value(HandControlState, tpdo.hand.state),
                error_warn=HandWarning(int.from_bytes(tpdo.hand.error_warn, "little")),
                error_fault=HandFault(int.from_bytes(tpdo.hand.error_fault, "little")),
                error_critical=HandCriticalError(int.from_bytes(tpdo.hand.error_critical,
                                                                "little")),
                temperature=tpdo.hand.temperature,
            )
            joints = [
                JointData(
                    id=jid,
                    state=parse_device_value(JointState, jtpdo.state),
                    error=parse_device_value(JointErrorCode, jtpdo.error),
                    control_mode=parse_device_value(JointControlMode, jtpdo.mode & 0x0F),
                    loop_type=parse_device_value(JointLoopType, jtpdo.mode >> 4),
                    angle=jtpdo.angle,
                    velocity=jtpdo.velocity,
                    current=jtpdo.current,
                ) for jid, jtpdo in tpdo.joints.items()
            ]
            tactile = None
            if self._config.has_tactile:
                tactile = {}
                for region in self._config.tactile_regions:
                    attr = f"{region.id.name.lower()}_tactile"
                    tdata = getattr(tpdo, attr, None)
                    if tdata is not None:
                        tactile[region.id] = TactileData(
                            state=bool(tpdo.tactile_state.state & (1 << region.id.value)),
                            resultant_force=tdata.resultant_force,
                            distributed_force=tdata.sample_force,
                        )
            callback(DeviceData(hand=hand, joints=joints, tactile=tactile), *args, **kwargs)

        return self.subscribe(adapter, interval_ms=interval_ms)

    def unsubscribe(self, sub_id) -> bool:
        """Remove a previously registered subscription.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription existed and was removed.
        """
        return self._sub_manager.unsubscribe(sub_id)
