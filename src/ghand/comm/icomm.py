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
- B. State-change operations (clear_fault/tactile_*): return bool
  to indicate device confirmation; return False when the device rejects the
  command. Underlying exceptions bubble up naturally.
- C. Critical control / data retrieval (move_joints/stop/get_*/get_joints):
  underlying exceptions bubble up naturally.
"""

from abc import ABC, abstractmethod

from ..types import CANFDBitTiming, RS485BaudRate


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
        baudrate: RS485BaudRate | CANFDBitTiming | None = None,
    ) -> bool:
        """Connect to the specified device.

        Args:
            device_name: Identifier of the device to connect to.
            slave_id: Optional RS485/CANFD slave ID override for this connection.
                Implementations that do not use slave IDs may ignore it.
            baudrate: Optional baud rate gear value. For RS485 this selects
                the serial baud rate; for CANFD it selects both the arbitration
                and data phase bitrates. Other implementations may ignore it.

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

        The default implementation reports that the protocol is unsupported.

        Args:
            slave_id: New slave ID to write to the device.

        Returns:
            True if the command succeeds, False otherwise.

        Raises:
            NotImplementedError: If the protocol does not support setting slave IDs.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support set_slave_id")

    def set_baudrate(self, baudrate: int) -> bool:
        """Configure the RS485/CANFD baud rate gear (Flash, effective on reboot).

        Args:
            baudrate: Protocol gear value written directly to holding
                register 0x0004.

        Returns:
            True if the command succeeds, False otherwise.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support set_baudrate")

    # ===== Joint control =====

    @abstractmethod
    def move_joints(self, joints: list, mode) -> bool:
        """Send joint control commands.

        Args:
            joints: List of JointCommand objects.
            mode: Control mode (position, velocity, or current).

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
    def disable_hand(self) -> bool:
        """Disable all active joints at the hand-control level."""
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
    def get_device_name(self) -> str:
        """Retrieve the device name.

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

    def get_stall_tolerances(self) -> dict:
        """Retrieve per-joint stall tolerances when supported."""
        raise NotImplementedError("stall tolerance configuration is not supported")

    def set_stall_tolerances(self, tolerances: dict) -> bool:
        """Set per-joint stall tolerances when supported."""
        raise NotImplementedError("stall tolerance configuration is not supported")

    def get_pid_parameters(self) -> list[int]:
        """Retrieve the raw closed-loop PID parameter array when supported."""
        raise NotImplementedError("PID parameter configuration is not supported")

    def set_pid_parameters(self, parameters: list[int]) -> bool:
        """Set the raw closed-loop PID parameter array when supported."""
        raise NotImplementedError("PID parameter configuration is not supported")

    def get_hand_state_machine(self):
        """Retrieve the whole-hand runtime state machine value when supported."""
        raise NotImplementedError("hand state machine query is not supported")

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

    def subscribe_device_data(
        self,
        callback,
        *,
        include_tactile: bool = False,
        interval_ms: int | None = None,
    ) -> int:
        """Subscribe to unified ``DeviceData`` updates."""
        from ..types import DeviceData

        def adapter(hand_state, joints, *args, **kwargs):
            tactile = None
            if include_tactile:
                tactile = self.get_tactile_data()
                if not tactile:
                    tactile = None
            callback(DeviceData(hand=hand_state, joints=joints, tactile=tactile), *args, **kwargs)

        return self.subscribe(adapter, interval_ms=interval_ms)

    @abstractmethod
    def unsubscribe(self, sub_id) -> bool:
        """Unsubscribe from data updates.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription was removed successfully.
        """
        ...
