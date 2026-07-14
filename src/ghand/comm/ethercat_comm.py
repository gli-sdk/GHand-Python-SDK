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
    ProductConfig,
    State,
    TactileRegionConfig,
    TactileInfo,
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

    _CONNECT_RETRIES = 3
    _CONNECT_RETRY_DELAY_SEC = 0.5
    _COMPAT_THUMB_TACTILE_COUNT = 28

    def __init__(self, config: ProductConfig):
        self._client = EthercatClient()
        self._sub_manager = SubscriptionManager(self._client)
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
            aliases=list(config.aliases),
            valid_joints=list(config.valid_joints),
            joint_limits=config.joint_limits.copy(),
            has_tactile=config.has_tactile,
            tactile_regions=tactile_regions,
            slave_id=config.slave_id,
            modbus_profile=config.modbus_profile,
            ethercat_input_sizes=config.ethercat_input_sizes,
            ethercat_output_size=config.ethercat_output_size,
            ethercat_rpdo_layout=config.ethercat_rpdo_layout,
            ethercat_tpdo_layout=config.ethercat_tpdo_layout,
        )

    def _build_tpdo_layouts(self, config: ProductConfig) -> dict[int, ProductConfig]:
        """Build supported TPDO layouts keyed by mapped input size."""
        tactile_counts = [r.count for r in config.tactile_regions] if config.has_tactile else None
        layouts = {
            compute_tpdo_size(len(config.valid_joints), tactile_counts): config
        }
        for input_size in config.ethercat_input_sizes:
            layouts[input_size] = config
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
        self._expected_rpdo_size = (
            config.ethercat_output_size
            if config.ethercat_output_size is not None
            else 2 + len(self._controlled_joints) * 6
        )
        self._rpdo_layout = config.ethercat_rpdo_layout
        self._tpdo_layout = config.ethercat_tpdo_layout

    # ===== Connection management =====

    def search_adapters(self) -> list[str]:
        """Search for available EtherCAT adapters.

        Returns:
            List of adapter IDs.
        """
        return self._client.search()

    def connect(self, device_name: str) -> bool:
        """Connect to the specified EtherCAT device.

        Args:
            device_name: Adapter ID to connect to.

        Returns:
            True if the connection and SOEM startup succeed.
        """
        for attempt in range(1, self._CONNECT_RETRIES + 1):
            connected = self._client.connect(device_name)
            if connected and self._client.run(self._expected_tpdo_sizes, self._expected_rpdo_size):
                self._select_tpdo_layout(self._client.input_size)
                logger.info("Device connected via EtherCAT (%s)", device_name)
                return True

            logger.error(
                "Failed to connect EtherCAT device %s (attempt %s/%s)",
                device_name,
                attempt,
                self._CONNECT_RETRIES,
            )
            self._client.disconnect()
            if attempt < self._CONNECT_RETRIES:
                time.sleep(self._CONNECT_RETRY_DELAY_SEC)

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
        if self._rpdo_layout == "per_joint_mode_3reg":
            self._client.send_data(self._build_l1_rpdo(joints, mode, stop=0))
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
        if self._rpdo_layout == "per_joint_mode_3reg":
            self._client.send_data(self._build_l1_rpdo([], CtrlMode.POSITION, stop=1))
        else:
            rpdo = Rpdo(self._controlled_joints)
            rpdo.mode = 0
            rpdo.stop = 1
            self._client.send_data(rpdo.to_bytes())
        return True

    def _build_l1_rpdo(
        self,
        joints: list[JointCommand],
        mode: CtrlMode,
        stop: int,
    ) -> bytes:
        """Build the L1 EtherCAT 6-byte-per-joint RPDO."""
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

        if self._tpdo_layout == "l1_extended":
            return self._parse_l1_extended_joints(data)

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

    def _parse_l1_extended_joints(self, data: bytes) -> list[JointData]:
        """Parse the L1 extended EtherCAT TPDO joint prefix."""
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
            return State.ABNORMAL_RUNNING

    @staticmethod
    def _parse_error_code(value: int) -> ErrorCode | int:
        try:
            return ErrorCode(value)
        except ValueError:
            return value

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
        return self._client.sdo_read(0x1008, 0x00).decode("utf-8").strip("\x00")

    def get_hardware_version(self) -> str:
        """Retrieve the hardware version via SDO."""
        return self._client.sdo_read(0x1009, 0x00).decode("utf-8").strip("\x00")

    def get_firmware_version(self) -> str:
        """Retrieve the firmware version via SDO."""
        return self._client.sdo_read(0x100A, 0x00).decode("utf-8").strip("\x00")

    def get_serial_number(self) -> int:
        """Retrieve the product serial number via SDO."""
        return int.from_bytes(self._client.sdo_read(0x1018, 0x04), byteorder="little")

    def get_motor_driver_version(self) -> tuple:
        """Retrieve the motor driver version via SDO.

        Writes the motor driver MCU id (0x04) to index 0x2007 sub-index 0x01,
        then reads version high/low from sub-indices 0x02/0x03 and parses the
        semantic version as (major, minor, patch).
        """
        self._client.sdo_write(0x2007, 0x01, b"\x04")
        version_high = int.from_bytes(
            self._client.sdo_read(0x2007, 0x02), byteorder="little"
        )
        version_low = int.from_bytes(
            self._client.sdo_read(0x2007, 0x03), byteorder="little"
        )
        major = (version_high >> 5) & 0x07
        minor = version_high & 0x1F
        patch = (version_low >> 4) & 0x0F
        return (major, minor, patch)

    def get_hand_type(self) -> int:
        """Retrieve the hand type via SDO.

        Returns:
            0 for unknown, 1 for left hand, 2 for right hand.
        """
        return int.from_bytes(self._client.sdo_read(0x2001, 0x00), byteorder="little")

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
        def validated_callback(data, *callback_args, **callback_kwargs):
            callback(
                self._validate_tpdo_data(data),
                *callback_args,
                **callback_kwargs,
            )

        return self._sub_manager.subscribe(validated_callback, *args, **kwargs)

    def unsubscribe(self, sub_id) -> bool:
        """Remove a previously registered subscription.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription existed and was removed.
        """
        return self._sub_manager.unsubscribe(sub_id)
