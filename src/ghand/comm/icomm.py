# Copyright (c) 2026 GLITech
#
# Licensed under the MIT License. See LICENSE in the project root for license information.

"""Communication protocol abstraction interface."""

from abc import ABC, abstractmethod


class IComm(ABC):
    """Abstract communication interface providing unified business-level APIs
    for EtherCAT, CANFD, and RS485.
    """

    # ===== Connection management =====

    @abstractmethod
    def connect(self, device_name: str) -> bool:
        """Connect to the specified device.

        Args:
            device_name: Identifier of the device to connect to.

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
        """Stop all joint motion."""
        ...

    # ===== State retrieval =====

    @abstractmethod
    def get_hand_info(self):
        """Retrieve hand status information."""
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
            True on success, False on failure.
        """
        ...

    @abstractmethod
    def close_tactile(self) -> bool:
        """Disable the tactile sensors.

        Returns:
            True on success, False on failure.
        """
        ...

    @abstractmethod
    def zero_tactile(self) -> bool:
        """Zero-calibrate the tactile sensors.

        Returns:
            True on success, False on failure.
        """
        ...

    # ===== Device operations =====

    @abstractmethod
    def clear_fault(self) -> bool:
        """Clear device faults.

        Returns:
            True on success, False on failure.
        """
        ...

    @abstractmethod
    def init_joint(self) -> bool:
        """Initialize joint positions.

        Returns:
            True on success, False on failure.
        """
        ...

    @abstractmethod
    def get_device_name(self) -> str:
        """Retrieve the device name."""
        ...

    @abstractmethod
    def get_hardware_version(self) -> str:
        """Retrieve the hardware version."""
        ...

    @abstractmethod
    def get_firmware_version(self) -> str:
        """Retrieve the firmware version."""
        ...

    @abstractmethod
    def get_serial_number(self) -> int:
        """Retrieve the product serial number."""
        ...

    @abstractmethod
    def get_motor_driver_version(self) -> tuple:
        """Retrieve the motor driver version."""
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
    def subscribe(self, callback, *args, **kwargs) -> int:
        """Subscribe to device data updates.

        Args:
            callback: Callable invoked when new data arrives.

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
