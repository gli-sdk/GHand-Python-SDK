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

"""Communication protocol abstraction interface.

Error handling contract:
- A. Connection management (connect/disconnect/search_adapters): return bool,
  do NOT raise on normal failure.
- B. State-change operations (clear_fault/init_joint/tactile_*): return bool
  to indicate device confirmation; return False when the device rejects the
  command. Underlying exceptions bubble up naturally.
- C. Critical control / data retrieval (move_joints/stop/get_*/get_joints):
  underlying exceptions bubble up naturally.
"""

from abc import ABC, abstractmethod


class IComm(ABC):
    """Abstract communication interface providing unified business-level APIs
    for EtherCAT, CANFD, and RS485.
    """

    # ===== Connection management =====

    @abstractmethod
    def connect(
        self,
        device_name: str,
        slave_id: int | None = None,
        baudrate_gear: int | None = None,
        quiet: bool = False,
    ) -> bool:
        """Connect to the specified device.

        Args:
            device_name: Identifier of the device to connect to.
            slave_id: Optional RS485/CANFD slave ID override for this connection.
                Implementations that do not use slave IDs may ignore it.
            baudrate_gear: Optional baud rate gear value. For RS485 this selects
                the serial baud rate; for CANFD it selects both the arbitration
                and data phase bitrates. Other implementations may ignore it.
            quiet: When True, suppress non-fatal failure logs. Useful for
                auto-detection loops that are expected to try several ports
                or baud rates before finding a device.

        Returns:
            True if the connection succeeds, False otherwise.
        """
        ...

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the device."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Return whether the device is currently connected."""
        ...

    @abstractmethod
    def search_adapters(self) -> list[str]:
        """Search for available adapters.

        Returns:
            List of adapter IDs.
        """
        ...

    def set_slave_id(self, slave_id: int) -> bool:
        """Set the device slave ID.

        Args:
            slave_id: New slave ID to write to the device.

        Returns:
            True if the command succeeds, False otherwise.
        """
        return False

    def set_baudrate_config(
        self,
        baudrate_gear: int | None = None,
    ) -> bool:
        """Configure the RS485/CANFD baud rate gear (Flash, effective on reboot).

        Args:
            baudrate_gear: Protocol gear value written directly to holding
                register 0x002C. When omitted the protocol default gear is used.

        Returns:
            True if the command succeeds, False otherwise.
        """
        return False

    # ===== Joint control =====

    @abstractmethod
    def move_joints(self, joints: list, mode) -> bool:
        """Send joint control commands.

        Args:
            joints: List of JointCommand objects.
            mode: Control mode (position, speed, or torque).

        Returns:
            True if the command is sent successfully.
        """
        ...

    @abstractmethod
    def get_joints(self) -> list:
        """Retrieve the current state of all joints.

        Returns:
            List of JointData objects.
        """
        ...

    @abstractmethod
    def stop(self) -> bool:
        """Stop all joint motion.

        """
        ...

    # ===== State retrieval =====

    @abstractmethod
    def get_hand_info(self):
        """Retrieve hand status information.

        """
        ...

    @abstractmethod
    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data.

        Returns:
            Dictionary mapping sensor IDs to tactile readings.

        """
        ...

    # ===== Tactile sensor =====

    @abstractmethod
    def open_tactile(self) -> bool:
        """Enable the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.

        """
        ...

    @abstractmethod
    def close_tactile(self) -> bool:
        """Disable the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.

        """
        ...

    @abstractmethod
    def zero_tactile(self) -> bool:
        """Zero-calibrate the tactile sensors.

        Returns:
            True on success, False if the device rejected the command.

        """
        ...

    # ===== Device operations =====

    @abstractmethod
    def clear_fault(self) -> bool:
        """Clear device faults.

        Returns:
            True on success, False if the device rejected the command.

        """
        ...

    @abstractmethod
    def init_joint(self) -> bool:
        """Initialize joint positions.

        Returns:
            True on success, False if the device rejected the command.

        """
        ...

    @abstractmethod
    def get_device_name(self) -> str:
        """Retrieve the device name.

        """
        ...

    @abstractmethod
    def get_hardware_version(self) -> str:
        """Retrieve the hardware version.

        """
        ...

    @abstractmethod
    def get_firmware_version(self) -> str:
        """Retrieve the firmware version.

        """
        ...

    @abstractmethod
    def get_firmware_package_version(self) -> str:
        """Retrieve the firmware package version.

        """
        ...

    @abstractmethod
    def get_position_sensor_version(self) -> str:
        """Retrieve the position sensor version.

        """
        ...

    @abstractmethod
    def get_tactile_sensor_version(self) -> str:
        """Retrieve the tactile MCU version.

        """
        ...

    @abstractmethod
    def get_serial_number(self) -> str:
        """Retrieve the product serial number.

        """
        ...

    @abstractmethod
    def get_motor_driver_version(self) -> str:
        """Retrieve the motor driver version.

        """
        ...

    @abstractmethod
    def get_thumb_tactile_sensor_version(self) -> str:
        """Retrieve the thumb tactile sensor version.

        """
        ...

    @abstractmethod
    def get_finger_tactile_sensor_version(self) -> str:
        """Retrieve the finger tactile sensor version.

        """
        ...

    @abstractmethod
    def get_hand_type(self) -> int:
        """Retrieve the hand type.

        Returns:
            0 for unknown, 1 for left hand, 2 for right hand.

        """
        ...

    def get_self_test_error_info(self):
        """Retrieve structured self-test error information.

        Default implementation returns an empty ``SelfTestErrorInfo``. Backends
        that support the self-test error query (object dictionary 0x2008)
        should override this method.

        Returns:
            SelfTestErrorInfo instance.
        """
        from ..types import SelfTestErrorInfo

        return SelfTestErrorInfo()

    def get_self_test_status(self) -> int:
        """Retrieve the self-test status byte.

        Backends that expose a direct self-test status register should override
        this method. Status values are: ``0`` idle, ``1`` processing,
        ``2`` command processed successfully, ``3`` failed. The default ``0``
        matches the idle/unknown status.
        """
        return 0

    # ===== Subscription =====

    @abstractmethod
    def subscribe(self, callback, *args, interval_ms: int | None = None, **kwargs) -> int:
        """Subscribe to device data updates.

        Args:
            callback: Callable invoked when new data arrives.
            interval_ms: Optional polling interval in milliseconds.

        Returns:
            Subscription ID that can be used to unsubscribe.
        """
        ...

    @abstractmethod
    def unsubscribe(self, sub_id) -> bool:
        """Unsubscribe from data updates.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription was removed successfully.
        """
        ...
