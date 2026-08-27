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
import math
import struct
import time

from .._subscription import SubscriptionManager
from ..types import (
    CtrlMode,
    ErrorCode,
    HandState,
    JointCommand,
    JointData,
    JointId,
    MotorCheckError,
    MotorDiagnosticError,
    ProductConfig,
    ProductType,
    SelfTestError,
    SelfTestErrorInfo,
    State,
    TactileRegionConfig,
    TactileInfo,
    VersionCheckError,
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


class EthercatComm(IComm):
    """IComm implementation for EtherCAT."""

    _COMPAT_THUMB_TACTILE_COUNT = 28

    def __init__(self, config: ProductConfig):
        self._client = EthercatClient()
        self._sub_manager = SubscriptionManager(self._client, self.is_connected)
        self.update_config(config)

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

    @staticmethod
    def _uses_per_joint_control_layout(config: ProductConfig) -> bool:
        """Return whether the product uses per-joint EtherCAT control fields."""
        return config.product_type == ProductType.GHandLite1

    def _expected_rpdo_bytes(self, config: ProductConfig) -> int:
        """Return the expected EtherCAT RPDO byte size for the product."""
        if self._uses_per_joint_control_layout(config):
            return len(self._controlled_joints) * 6
        return 2 + len(self._controlled_joints) * 6

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
        self._expected_rpdo_size = self._expected_rpdo_bytes(config)
        self._uses_per_joint_control_pdo_layout = self._uses_per_joint_control_layout(config)

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
            mode: Control mode (position, speed, or torque).

        Returns:
            True if the command is sent successfully.
        """
        if self._uses_per_joint_control_pdo_layout:
            self._client.send_data(self._build_per_joint_control_rpdo(joints, mode, stop=0))
        else:
            rpdo = Rpdo(self._controlled_joints)
            rpdo.mode = mode.value
            rpdo.stop = 0

            for joint in joints:
                rpdo.joints[joint.id] = (math.radians(joint.angle), joint.speed, joint.torque)

            self._client.send_data(rpdo.to_bytes())
        return True

    def stop(self) -> bool:
        """Send an immediate stop command to all joints."""
        if self._uses_per_joint_control_pdo_layout:
            self._client.send_data(self._build_per_joint_control_rpdo([], CtrlMode.POSITION, stop=1))
        else:
            rpdo = Rpdo(self._controlled_joints)
            rpdo.mode = 0
            rpdo.stop = 1
            self._client.send_data(rpdo.to_bytes())
        return True

    def _build_per_joint_control_rpdo(
        self,
        joints: list[JointCommand],
        mode: CtrlMode,
        stop: int,
    ) -> bytes:
        """Build the per-joint-control EtherCAT 6-byte-per-joint RPDO."""
        by_id = {joint.id: joint for joint in joints}
        data = bytearray()
        for joint_id in self._controlled_joints:
            joint = by_id.get(joint_id)
            if joint is None:
                position = 0
                speed = 0
                torque = 0
            else:
                position = int(joint.angle * 10) & 0xFFFF
                speed = int(joint.speed)
                torque = int(joint.torque)
            data.extend(
                struct.pack(
                    "<BBHbb",
                    mode.value & 0xFF,
                    stop & 0xFF,
                    position,
                    speed,
                    torque,
                )
            )
        return bytes(data)

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

        if self._uses_per_joint_control_pdo_layout:
            return self._parse_per_joint_control_joints(data)

        tpdo = Tpdo.from_bytes(data, self._config)

        joints = []
        for joint_id, joint_tpdo in tpdo.joints.items():
            angle = joint_tpdo.angle
            if abs(angle) < 1e-10:
                angle = 0.0
            joints.append(
                JointData(
                    id=joint_id,
                    angle=angle,
                    speed=joint_tpdo.speed,
                    torque=joint_tpdo.torque,
                    state=self._parse_state(joint_tpdo.state),
                    error=self._parse_error_code(joint_tpdo.error),
                )
            )
        return joints

    def _parse_per_joint_control_joints(self, data: bytes) -> list[JointData]:
        """Parse the per-joint-control EtherCAT TPDO joint prefix."""
        offset = 4
        joints = []
        for joint_id in self._config.valid_joints:
            if len(data) < offset + 6:
                break
            state, error, angle_raw, speed, torque = struct.unpack_from(
                "<BBHbb", data, offset
            )
            joints.append(
                JointData(
                    id=joint_id,
                    angle=angle_raw / 10.0,
                    speed=speed,
                    torque=torque,
                    state=self._parse_state(state),
                    error=self._parse_error_code(error),
                )
            )
            offset += 6
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

    def get_hand_info(self) -> HandState:
        """Retrieve high-level hand status from TPDO.

        Returns:
            HandState instance.
        """
        data = self._recv_tpdo_data()

        hand_tpdo = HandTpdo.from_bytes(data)
        return HandState(
            state=self._parse_state(hand_tpdo.state),
            error=self._parse_error_code(hand_tpdo.error),
            temperature=hand_tpdo.temperature,
        )

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data from TPDO.

        Returns:
            Dictionary mapping TactileSensorId to TactileInfo.
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
            result[region.id] = TactileInfo(
                state=bool(tpdo.tactile_state.state & (1 << region.id.value)),
                resultant_force=tactile.resultant_force,
                distributed_force=tactile.sample_force,
            )
        return result

    # ===== Tactile sensor =====

    def open_tactile(self) -> bool:
        """Enable the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.
        """
        self._client.sdo_write(0x2004, 0x01, b'\x01')
        result = self._client.sdo_read(0x2004, 0x03)
        if result != b'\x00':
            logger.error("Device rejected open_tactile command")
            return False
        return True

    def close_tactile(self) -> bool:
        """Disable the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.
        """
        self._client.sdo_write(0x2004, 0x01, b'\x02')
        result = self._client.sdo_read(0x2004, 0x03)
        if result != b'\x00':
            logger.error("Device rejected close_tactile command")
            return False
        return True

    def zero_tactile(self) -> bool:
        """Zero-calibrate the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.
        """
        self._client.sdo_write(0x2004, 0x01, b'\x04')
        result = self._client.sdo_read(0x2004, 0x03)
        if result != b'\x00':
            logger.error("Device rejected zero_tactile command")
            return False
        return True

    # ===== Device operations =====

    def clear_fault(self) -> bool:
        """Clear device faults.

        Returns:
            True on success, False if the device rejected the command.
        """
        self._client.sdo_write(0x2002, 0x01, b'\x01')
        logger.info("Fault cleared")
        return True

    def init_joint(self) -> bool:
        """Initialize joint positions.

        Returns:
            True on success, False if the device rejected the command.
        """
        self._client.sdo_write(0x2003, 0x01, b'\x01')
        logger.info("Joint initialization completed")
        return True

    def get_device_name(self) -> str:
        """Retrieve the device name via SDO."""
        return self._read_string_sdo(0x1008, 0x00)

    def get_hardware_version(self) -> str:
        """Retrieve the hardware version via SDO."""
        return self._read_string_sdo(0x1009, 0x00)

    def get_firmware_version(self) -> str:
        """Retrieve the firmware version via SDO."""
        return self._read_string_sdo(0x100A, 0x00)

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
        try:
            raw = self._client.sdo_read(0x200C, 0x01)
            return raw[:19].decode("ascii", errors="ignore").strip("\x00")
        except Exception:
            return "N/A"

    def _read_packed_firmware_version(self, mcu_id: int) -> str:
        """Read a packed firmware version via SDO."""
        try:
            self._client.sdo_write(0x2007, 0x01, bytes([mcu_id]))
            version_high = int.from_bytes(
                self._client.sdo_read(0x2007, 0x02), byteorder="little"
            )
            version_low = int.from_bytes(
                self._client.sdo_read(0x2007, 0x03), byteorder="little"
            )
        except Exception:
            logger.info("Packed firmware version not available", exc_info=True)
            return "N/A"

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

        Writes the motor driver MCU id (0x04) to index 0x2007 sub-index 0x01,
        then reads version high/low from sub-indices 0x02/0x03 and parses the
        semantic version as (major, minor, patch).

        Returns "N/A" if the motor driver version is not available, matching
        the behaviour of CANFD and RS485 transports.
        """
        return self._read_packed_firmware_version(0x04)

    def get_thumb_tactile_sensor_version(self) -> str:
        """Retrieve the thumb tactile sensor version via SDO."""
        return self._read_packed_firmware_version(0x06)

    def get_finger_tactile_sensor_version(self) -> str:
        """Retrieve the finger tactile sensor version via SDO."""
        return self._read_packed_firmware_version(0x07)

    def get_hand_type(self) -> int:
        """Retrieve the hand type via SDO.

        Returns:
            0 for unknown, 1 for left hand, 2 for right hand.
        """
        try:
            return int.from_bytes(self._client.sdo_read(0x2001, 0x00), byteorder="little")
        except Exception:
            return 0

    # ===== Self-test error query =====

    _SELF_TEST_INDEX = 0x2008
    _SELF_TEST_SUB_COMMAND = 0x01
    _SELF_TEST_SUB_STATE = 0x02
    _SELF_TEST_SUB_ERROR_CODE = 0x03

    _SELF_TEST_STATE_IDLE = 0
    _SELF_TEST_STATE_PROCESSING = 1
    _SELF_TEST_STATE_SUCCESS = 2
    _SELF_TEST_STATE_FAILED = 3

    _SELF_TEST_POLL_INTERVAL_SEC = 0.01
    _SELF_TEST_POLL_TIMEOUT_SEC = 1.0

    def get_self_test_error_info(self) -> SelfTestErrorInfo:
        """Query self-test error information via object dictionary 0x2008.

        Reads the A0 summary and only dispatches the detailed A1~A8 queries for
        error categories that are actually flagged. Does not trigger a
        self-test or zeroing.
        """
        info = SelfTestErrorInfo()

        summary_byte = self._get_self_test_summary_error_code()
        info.summary = SelfTestError(summary_byte)
        logger.debug("Self-test summary: 0x%02X", summary_byte)

        if info.summary == SelfTestError.NONE:
            return info

        if info.summary & SelfTestError.VERSION:
            info.version = VersionCheckError(self._get_version_check_error_code())
            logger.info("Self-test error: version mismatch (0x%02X)", int(info.version))

        if info.summary & SelfTestError.POSITION_SENSOR:
            info.position_sensor = self._collect_motor_errors(
                self._get_position_sensor_error_codes()
            )
            self._log_motor_errors("position sensor", info.position_sensor)

        if info.summary & SelfTestError.TACTILE_SENSOR:
            info.tactile_sensor = self._collect_motor_errors(
                self._get_tactile_sensor_error_codes()
            )
            self._log_motor_errors("tactile sensor", info.tactile_sensor)

        if info.summary & SelfTestError.TEMPERATURE_SENSOR:
            info.temperature = self._get_temperature_sensor_error_code()
            logger.info("Self-test error: temperature sensor (0x%02X)", info.temperature)

        if info.summary & SelfTestError.FAN:
            info.fan = self._get_fan_error_code()
            logger.info("Self-test error: fan (0x%02X)", info.fan)

        if info.summary & SelfTestError.ZEROING:
            info.zeroing = self._collect_motor_errors(self._get_zeroing_error_codes())
            self._log_motor_errors("zeroing", info.zeroing)

        if info.summary & SelfTestError.MOTOR:
            info.motor = self._collect_motor_errors(self._get_motor_error_codes())
            self._log_motor_errors("motor check", info.motor)

        return info

    def get_self_test_status(self) -> int:
        """Read the current self-test status from object dictionary 0x2008:0x02.

        Status values: 0 idle, 1 processing, 2 command processed successfully,
        3 failed.
        """
        raw = self._client.sdo_read(self._SELF_TEST_INDEX, self._SELF_TEST_SUB_STATE)
        return raw[0] if raw else self._SELF_TEST_STATE_IDLE

    def _read_diagnostic_error_codes(self, command: int) -> list[int]:
        """Execute one 0x2008 read transaction and return the 13-byte error array.

        The caller decides which slots of the returned list are meaningful.
        Raises ``RuntimeError`` on transaction failure or timeout.
        """
        self._client.sdo_write(
            self._SELF_TEST_INDEX,
            self._SELF_TEST_SUB_COMMAND,
            bytes([command & 0xFF]),
        )

        # State 只用于判断事务是否结束(2 或 3 都算结束);
        # Result 不判断,只读取 error_code 数据。
        self._poll_self_test_state(command)

        raw = self._client.sdo_read(
            self._SELF_TEST_INDEX, self._SELF_TEST_SUB_ERROR_CODE
        )
        codes = list(raw[:13])
        if len(codes) < 13:
            codes.extend([0] * (13 - len(codes)))
        return codes

    def _poll_self_test_state(self, command: int) -> int:
        """Poll subindex 0x02 until state becomes success (2) or failed (3)."""
        deadline = time.monotonic() + self._SELF_TEST_POLL_TIMEOUT_SEC
        while True:
            raw = self._client.sdo_read(
                self._SELF_TEST_INDEX, self._SELF_TEST_SUB_STATE
            )
            state = raw[0] if raw else self._SELF_TEST_STATE_IDLE
            if state in (
                self._SELF_TEST_STATE_SUCCESS,
                self._SELF_TEST_STATE_FAILED,
            ):
                return state
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Self-test query 0x{command:02X} timed out (state={state})"
                )
            time.sleep(self._SELF_TEST_POLL_INTERVAL_SEC)

    def _get_self_test_summary_error_code(self) -> int:
        return self._read_diagnostic_error_codes(0xA0)[0]

    def _get_version_check_error_code(self) -> int:
        return self._read_diagnostic_error_codes(0xA1)[0]

    def _get_position_sensor_error_codes(self) -> list[int]:
        return self._read_diagnostic_error_codes(0xA2)

    def _get_tactile_sensor_error_codes(self) -> list[int]:
        return self._read_diagnostic_error_codes(0xA3)

    def _get_temperature_sensor_error_code(self) -> int:
        return self._read_diagnostic_error_codes(0xA4)[0]

    def _get_fan_error_code(self) -> int:
        return self._read_diagnostic_error_codes(0xA5)[0]

    def _get_zeroing_error_codes(self) -> list[int]:
        return self._read_diagnostic_error_codes(0xA6)

    def _get_motor_error_codes(self) -> list[int]:
        return self._read_diagnostic_error_codes(0xA8)

    def _motor_index_to_joint(self, motor_index: int) -> JointId | None:
        """Resolve a 13-channel motor slot to its ``JointId`` via the product config.

        The mapping reuses ``self._controlled_joints``, which is the ordered list
        of joints owning a motor for the active product profile.
        """
        if 0 <= motor_index < len(self._controlled_joints):
            return self._controlled_joints[motor_index]
        return None

    def _collect_motor_errors(
        self, error_codes: list[int]
    ) -> list[MotorDiagnosticError]:
        """Filter a 13-slot error array to structured non-zero entries."""
        errors = []
        for index, code in enumerate(error_codes):
            if code == 0:
                continue
            errors.append(
                MotorDiagnosticError(
                    motor_index=index,
                    joint_id=self._motor_index_to_joint(index),
                    error_code=code,
                )
            )
        return errors

    def _log_motor_errors(
        self, category: str, errors: list[MotorDiagnosticError]
    ) -> None:
        for err in errors:
            joint = err.joint_id.name if err.joint_id is not None else "unknown"
            description = self._motor_error_description(category, err.error_code)
            logger.info(
                "Self-test %s error: motor=%d joint=%s code=0x%02X (%s)",
                category,
                err.motor_index,
                joint,
                err.error_code,
                description,
            )

    @staticmethod
    def _motor_error_description(category: str, code: int) -> str:
        if category == "motor check":
            try:
                return MotorCheckError(code).name
            except ValueError:
                return "unknown"
        if category == "zeroing":
            mapping = {
                0x01: "motor abnormal",
                0x02: "full-stroke check failed",
                0x03: "zeroing timeout",
            }
            return mapping.get(code, "unknown")
        if category == "position sensor":
            return "position sensor abnormal" if code == 0x01 else "unknown"
        if category == "tactile sensor":
            parts = []
            names = {
                0x01: "thumb tip disconnected",
                0x02: "ff tip disconnected",
                0x04: "mf tip disconnected",
                0x08: "rf tip disconnected",
                0x10: "lf tip disconnected",
                0x80: "communication failed",
            }
            for bit, name in names.items():
                if code & bit:
                    parts.append(name)
            return ", ".join(parts) if parts else "unknown"
        return "unknown"

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

    def unsubscribe(self, sub_id) -> bool:
        """Remove a previously registered subscription.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription existed and was removed.
        """
        return self._sub_manager.unsubscribe(sub_id)
