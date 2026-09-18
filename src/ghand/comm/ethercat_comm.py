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
import threading
import time

from .._subscription import SubscriptionManager
from ..types import (
    JointId,
    CtrlMode,
    JointControlState,
    JointState,
    State,
    ErrorCode,
    JointErrorCode,
    ProductConfig,
    TactileRegionConfig,
    JointCommand,
    DeviceData,
    HandState,
    HandStateMachine,
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


# EtherCAT SDO object dictionary indices
SDO_DEVICE_NAME = 0x1008
SDO_FIRMWARE_VERSION = 0x100A
SDO_SERIAL_NUMBER_LEGACY = 0x1018
SDO_HAND_TYPE = 0x2001
SDO_FAULT_CLEAR = 0x2002
SDO_STALL_TOLERANCE = 0x2003
SDO_TACTILE_CONTROL = 0x2004
SDO_FIRMWARE_INFO = 0x2007
SDO_PID_PARAMETERS = 0x2008
SDO_SERIAL_NUMBER = 0x2009
SDO_HAND_STATE_MACHINE = 0x200A

# SDO subindices
SDO_SUB_COMMAND = 0x01
SDO_SUB_STATE = 0x02
SDO_SUB_RESULT = 0x03

_STALL_TOLERANCE_JOINT_ORDER = (
    JointId.THUMB_MCP,
    JointId.THUMB_TMC_FE,
    JointId.THUMB_TMC_AA,
    JointId.THUMB_TMC_PS,
    JointId.FF_PIP,
    JointId.FF_MCP,
    JointId.FF_MCP_AA,
    JointId.MF_PIP,
    JointId.MF_MCP,
    JointId.RF_PIP,
    JointId.RF_MCP,
    JointId.LF_PIP,
    JointId.LF_MCP,
)


class EthercatComm(IComm):
    """IComm implementation for EtherCAT."""

    _COMPAT_THUMB_TACTILE_COUNT = 28
    _SDO_WRITE_SETTLE_SEC = 0.02
    _SDO_POLL_INTERVAL_SEC = 0.01
    _SDO_POLL_TIMEOUT_SEC = 1.0

    def __init__(self, config: ProductConfig):
        self._client = EthercatClient()
        self._sub_manager = SubscriptionManager(self._client, self.is_connected)
        self._static_sdo_cache = {}
        self._static_sdo_cache_lock = threading.Lock()
        self.update_config(config)

    def _clear_static_sdo_cache(self) -> None:
        with self._static_sdo_cache_lock:
            self._static_sdo_cache.clear()

    def _read_static_sdo_once(self, key: str, reader):
        """Cache one successful static SDO value for the current connection."""
        with self._static_sdo_cache_lock:
            if key in self._static_sdo_cache:
                return self._static_sdo_cache[key]
            value = reader()
            if value not in (None, "", "N/A", 0):
                self._static_sdo_cache[key] = value
            return value

    @property
    def config(self) -> ProductConfig:
        """Return the active product config selected for the mapped PDO layout."""
        return self._config

    def _clone_config_with_tactile_counts(
        self, config: ProductConfig, tactile_counts: list[int]
    ) -> ProductConfig:
        """Clone product config while replacing tactile region sample counts."""
        tactile_regions = [
            TactileRegionConfig(id=region.id, count=count)
            for region, count in zip(config.tactile_regions, tactile_counts)
        ]
        return ProductConfig(
            name=config.name,
            model=config.model,
            valid_joints=list(config.valid_joints),
            joint_limits=config.joint_limits.copy(),
            has_tactile=config.has_tactile,
            tactile_regions=tactile_regions,
            product_type=config.product_type,
            slave_id=config.slave_id,
        )

    def _expected_rpdo_bytes(self, config: ProductConfig) -> int:
        """Return the expected EtherCAT RPDO byte size for the product."""
        return 2 + len(self._controlled_joints) * 12

    def _build_tpdo_layouts(self, config: ProductConfig) -> dict[int, ProductConfig]:
        """Build supported TPDO layouts keyed by mapped input size."""
        tactile_counts = [r.count for r in config.tactile_regions] if config.has_tactile else None
        layouts = {
            compute_tpdo_size(len(config.valid_joints), tactile_counts): config
        }
        if config.has_tactile and tactile_counts and tactile_counts[0] > self._COMPAT_THUMB_TACTILE_COUNT:
            compat_counts = list(tactile_counts)
            compat_counts[0] = self._COMPAT_THUMB_TACTILE_COUNT
            compat_config = self._clone_config_with_tactile_counts(config, compat_counts)
            layouts[compute_tpdo_size(len(config.valid_joints), compat_counts)] = compat_config
        return layouts

    def _select_tpdo_layout(self, input_size: int) -> None:
        """Select the active parser layout from the actual mapped input size."""
        layout = self._tpdo_layouts.get(input_size)
        if layout is None:
            return
        self._config = layout
        self._expected_tpdo_size = input_size
        self._tpdo_size_selected = True
        logger.info(
            "Selected EtherCAT TPDO layout: input=%s, tactile_counts=%s",
            input_size,
            [r.count for r in self._config.tactile_regions] if self._config.has_tactile else [],
        )

    def update_config(self, config: ProductConfig) -> None:
        """Update the cached product configuration and derived constants."""
        self._config = config
        self._tpdo_layouts = self._build_tpdo_layouts(config)
        self._expected_tpdo_sizes = tuple(sorted(self._tpdo_layouts))
        self._expected_tpdo_size = compute_tpdo_size(
            len(config.valid_joints),
            [r.count for r in config.tactile_regions] if config.has_tactile else None,
        )
        self._tpdo_size_selected = False
        self._controlled_joints = [j for j in config.valid_joints if j in config.joint_limits]
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
        baudrate_gear: int | None = None,
        quiet: bool = False,
    ) -> bool:
        """Connect to the specified EtherCAT device.

        Args:
            device_name: Adapter ID to connect to.
            slave_id: Ignored for EtherCAT.
            baudrate_gear: Ignored for EtherCAT.
            quiet: Ignored for EtherCAT; errors are always logged.

        Returns:
            True if the connection and SOEM startup succeed.
        """
        self._clear_static_sdo_cache()
        connected = self._client.connect(device_name)
        if connected and self._client.run(self._expected_tpdo_sizes, self._expected_rpdo_size):
            self._select_tpdo_layout(self._client.input_size)
            logger.info("Device connected via EtherCAT (%s)", device_name)
            return True

        logger.error("Failed to connect EtherCAT device %s", device_name)
        self._client.disconnect()
        return False

    def disconnect(self) -> bool:
        """Disconnect from the EtherCAT device and stop subscriptions."""
        self._clear_static_sdo_cache()
        self._sub_manager.stop()
        self._client.disconnect()
        logger.info("Device disconnected")
        return True

    def is_connected(self) -> bool:
        """Return whether the EtherCAT client is connected."""
        return self._client._connected and not self._client._connection_lost

    # ===== Joint control =====

    def move_joints(self, joints: list[JointCommand], mode: CtrlMode) -> bool:
        """Send joint control commands via RPDO.

        Args:
            joints: List of JointCommand objects.
            mode: Control mode (position, speed, or current).

        Returns:
            True if the command is sent successfully.
        """
        self._rpdo.mode = mode.value
        self._rpdo.stop = 1

        for joint in joints:
            joint_id = JointId(joint.id)
            if joint_id not in self._rpdo.joints:
                raise ValueError(f"Joint {joint_id.name} is not controllable")
            target = self._rpdo.joints[joint_id]
            joint_mode = joint.mode
            if joint_mode is None and mode != CtrlMode.CUSTOM:
                joint_mode = mode
            if joint_mode is not None:
                if joint_mode == CtrlMode.CUSTOM:
                    raise ValueError("Per-joint mode cannot be CUSTOM")
                target.mode = (
                    joint_mode.value
                    if isinstance(joint_mode, CtrlMode)
                    else int(joint_mode)
                )
            target.stop = JointControlState(joint.stop).value
            target.angle = joint.angle
            target.speed = joint.speed
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
        expected_sizes = (
            (self._expected_tpdo_size,)
            if self._tpdo_size_selected
            else self._expected_tpdo_sizes
        )
        if len(data) not in expected_sizes:
            raise RuntimeError(
                "Invalid EtherCAT TPDO length: "
                f"expected one of {expected_sizes}, got {len(data)}"
            )
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
                    state=self._parse_joint_state(joint_tpdo.state),
                    error=self._parse_joint_error_code(joint_tpdo.error),
                    mode=joint_tpdo.mode,
                    stop=joint_tpdo.stop,
                    angle=angle,
                    speed=joint_tpdo.speed,
                    current=joint_tpdo.current,
                )
            )
        return joints

    @staticmethod
    def _parse_state(value: int) -> State:
        try:
            return State(value)
        except ValueError:
            return State.UNKNOWN_STATE

    @staticmethod
    def _parse_error_code(value: int) -> ErrorCode:
        try:
            return ErrorCode(value)
        except ValueError:
            return ErrorCode.UNKNOWN_ERROR

    @staticmethod
    def _parse_joint_state(value: int) -> JointState:
        try:
            return JointState(value)
        except ValueError:
            return JointState.UNKNOWN_STATE

    @staticmethod
    def _parse_joint_error_code(value: int) -> JointErrorCode:
        try:
            return JointErrorCode(value)
        except ValueError:
            return JointErrorCode.UNKNOWN_ERROR

    def get_hand_info(self) -> HandState:
        """Retrieve high-level hand status from TPDO.

        Returns:
            HandState instance.
        """
        data = self._recv_tpdo_data()

        hand_tpdo = HandTpdo.from_bytes(data)
        return HandState(
            state=self._parse_state(hand_tpdo.state),
            error_warn=hand_tpdo.error_warn,
            error_fault=hand_tpdo.error_fault,
            error_critical=hand_tpdo.error_critical,
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
        command_subindex: int = SDO_SUB_COMMAND,
        state_subindex: int = SDO_SUB_STATE,
        result_subindex: int = SDO_SUB_RESULT,
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
        return self._execute_sdo_command(SDO_TACTILE_CONTROL, 0x01)

    def close_tactile(self) -> bool:
        """Disable the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.
        """
        return self._execute_sdo_command(SDO_TACTILE_CONTROL, 0x02)

    def zero_tactile(self) -> bool:
        """Zero-calibrate the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.
        """
        return self._execute_sdo_command(SDO_TACTILE_CONTROL, 0x04)

    # ===== Device operations =====

    def clear_fault(self) -> bool:
        """Clear device faults.

        Returns:
            True on success, False if the device rejected the command.
        """
        success = self._execute_sdo_command(SDO_FAULT_CLEAR, 0x01)
        if success:
            logger.info("Fault cleared")
        return success

    def get_device_name(self) -> str:
        """Retrieve the device name via SDO."""
        return self._read_static_sdo_once(
            "device_name", lambda: self._read_string_sdo(SDO_DEVICE_NAME, 0x00)
        )

    def get_firmware_version(self) -> str:
        """Retrieve the firmware version via SDO."""
        return self._read_static_sdo_once(
            "firmware_version", lambda: self._read_packed_firmware_version(0x01)
        )

    def _read_string_sdo(self, index: int, subindex: int) -> str:
        try:
            return (
                self._client.sdo_read(index, subindex)
                .decode("utf-8", errors="ignore")
                .strip("\x00")
                or "N/A"
            )
        except Exception:
            return "N/A"

    def get_serial_number(self) -> str:
        """Retrieve the 19-byte ASCII product serial number via SDO."""
        def read_serial_number() -> str:
            try:
                raw = self._client.sdo_read(SDO_SERIAL_NUMBER, 0x01)
                return raw[:19].decode("ascii", errors="ignore").strip("\x00")
            except Exception:
                return "N/A"

        return self._read_static_sdo_once("serial_number", read_serial_number)

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
                f"invalid SDO parameter size: expected {expected_size}, got {len(raw)}"
            )
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
        values = self._unpack_uint_array(
            self._client.sdo_read(SDO_STALL_TOLERANCE, 0x01), 13, "B"
        )
        return dict(zip(_STALL_TOLERANCE_JOINT_ORDER, values))

    def set_stall_tolerances(self, tolerances: dict[JointId, int]) -> bool:
        """Write all 13 per-joint stall tolerances through SDO 0x2003."""
        if set(tolerances) != set(_STALL_TOLERANCE_JOINT_ORDER):
            raise ValueError("stall tolerances must contain all 13 active JointId keys")
        values = [tolerances[joint_id] for joint_id in _STALL_TOLERANCE_JOINT_ORDER]
        return self._write_sdo_parameters(
            SDO_STALL_TOLERANCE,
            self._pack_uint_array(values, 13, "B"),
        )

    def get_pid_parameters(self) -> list[int]:
        """Read the raw 39-value uint16 PID array from SDO 0x2008:01."""
        return self._unpack_uint_array(
            self._client.sdo_read(SDO_PID_PARAMETERS, 0x01), 39, "H"
        )

    def set_pid_parameters(self, parameters: list[int]) -> bool:
        """Write the raw 39-value uint16 PID array through SDO 0x2008."""
        return self._write_sdo_parameters(
            SDO_PID_PARAMETERS,
            self._pack_uint_array(parameters, 39, "H"),
        )

    def get_hand_state_machine(self) -> HandStateMachine:
        """Read the whole-hand runtime state from SDO 0x200A:01."""
        raw = self._client.sdo_read(SDO_HAND_STATE_MACHINE, 0x01)
        if len(raw) != 1:
            raise RuntimeError(
                f"invalid hand state machine size: expected 1, got {len(raw)}"
            )
        return HandStateMachine(raw[0])

    def _read_packed_firmware_version(self, subindex: int) -> str:
        """Read a packed firmware version from SDO 0x2007."""
        try:
            raw = self._client.sdo_read(SDO_FIRMWARE_INFO, subindex)
        except Exception:
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
        """Firmware package version is not exposed by EtherCAT V2.1."""
        return "N/A"

    def get_position_sensor_version(self) -> str:
        """Retrieve the position sensor version via SDO."""
        return self._read_static_sdo_once(
            "position_sensor_version", lambda: self._read_packed_firmware_version(0x02)
        )

    def get_tactile_sensor_version(self) -> str:
        """Retrieve the tactile MCU version via SDO."""
        return self._read_static_sdo_once(
            "tactile_sensor_version", lambda: self._read_packed_firmware_version(0x03)
        )

    def get_motor_driver_version(self) -> str:
        """Retrieve the motor driver version via SDO.

        Returns "N/A" if the motor driver version is not available.
        """
        return self._read_static_sdo_once(
            "motor_driver_version", lambda: self._read_packed_firmware_version(0x04)
        )

    def get_thumb_tactile_sensor_version(self) -> str:
        """Per-finger tactile versions are not exposed by EtherCAT V2.1."""
        return "N/A"

    def get_finger_tactile_sensor_version(self) -> str:
        """Per-finger tactile versions are not exposed by EtherCAT V2.1."""
        return "N/A"

    def get_hand_type(self) -> int:
        """Retrieve the hand type via SDO.

        Returns:
            0 for unknown, 1 for left hand, 2 for right hand.
        """
        def read_hand_type() -> int:
            try:
                return int.from_bytes(
                    self._client.sdo_read(SDO_HAND_TYPE, 0x00), byteorder="little"
                )
            except Exception:
                return 0

        return self._read_static_sdo_once("hand_type", read_hand_type)

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
            hand = HandState(
                state=self._parse_state(tpdo.hand.state),
                error_warn=tpdo.hand.error_warn,
                error_fault=tpdo.hand.error_fault,
                error_critical=tpdo.hand.error_critical,
                temperature=tpdo.hand.temperature,
            )
            joints = [
                JointData(
                    id=jid.value,
                    state=self._parse_joint_state(jtpdo.state),
                    error=self._parse_joint_error_code(jtpdo.error),
                    mode=jtpdo.mode,
                    stop=jtpdo.stop,
                    angle=jtpdo.angle,
                    speed=jtpdo.speed,
                    current=jtpdo.current,
                )
                for jid, jtpdo in tpdo.joints.items()
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
