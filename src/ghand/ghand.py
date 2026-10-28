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
"""High-level API for the GHand dexterous hand."""

from __future__ import annotations

import logging
import time
from typing import Any
from ._config import load_product_config
from .comm import IComm, create_comm
import numpy as np
from ._converter import joints_to_nparray
from ._converter import nparray_to_joints
from .collision import CollisionCheckResult, CollisionClient
from .collision.angle_mapping import COLLISION_JOINT_ORDER
from .collision.angle_mapping import internal_radians_to_sdk_degrees
from .collision.angle_mapping import neutral_internal_radians
from ._product_config import ProductConfig
from .types import (
    CANFDBitTiming,
    CommType,
    JointId,
    JointControlMode,
    JointLoopType,
    ProductType,
    RS485BaudRate,
    HandControlMode,
    HandType,
    JointCommand,
    HandData,
    HandRuntimeState,
    JointData,
)

logger = logging.getLogger("ghand.ghand")

BaudRateConfig = RS485BaudRate | CANFDBitTiming


class GHand:
    """High-level API for the GHand dexterous hand."""

    def __init__(self, product_type: ProductType, comm_type: CommType):
        """Initialize the GHand instance.

        Args:
            product_type: Product model (e.g. ``ProductType.GHand5``).
            comm_type: Communication protocol (e.g. ``CommType.CANFD``).
        """
        self._product_type = product_type
        self._comm_type = comm_type
        self._product_config = load_product_config(product_type)
        self._active_joints = self._product_config.active_joints.copy()
        self._passive_joints = set(self._product_config.all_joints) - set(
            self._active_joints.keys())
        self._has_tactile = self._product_config.has_tactile
        self._comm = self._create_comm(comm_type)
        self._tactile_opened = False
        self._safety_margin = 0.0
        self._collision_checker = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        try:
            if getattr(self, "_comm", None) is not None:
                self.close()
        except Exception:
            pass

    def _create_comm(self, comm_type: CommType) -> IComm:
        """Instantiate the appropriate IComm implementation."""
        return create_comm(comm_type, self._product_config)

    def _apply_product_config(self, config: ProductConfig) -> None:
        """Apply a new product configuration.

        Args:
            config: New product configuration to apply.
        """
        self._product_config = config
        self._active_joints = config.active_joints.copy()
        self._passive_joints = set(config.all_joints) - set(self._active_joints.keys())
        self._has_tactile = config.has_tactile
        self._tactile_opened = False
        self._comm.update_config(config)

    @staticmethod
    def _check_joint_limit(joint: JointCommand, limit, mode: JointControlMode):
        """Clamp the joint angle to its configured limits.

        Args:
            joint: Joint to check and modify in place.
            limit: Tuple of (min, max) in degrees.
            mode: Current control mode.
        """
        original_angle = joint.angle
        if joint.angle < limit[0]:
            joint.angle = limit[0]
        elif joint.angle > limit[1]:
            joint.angle = limit[1]
        if joint.angle != original_angle and mode == JointControlMode.POSITION and mode == JointControlMode.MIT:
            logger.warning(
                "[Joint] ID: %s angle %.1f adjusted to %.1f degrees",
                JointId(joint.id).name,
                original_angle,
                joint.angle,
            )

    @staticmethod
    def _check_velocity_limit(joint: JointCommand, mode: JointControlMode):
        """Validate and clamp joint velocity based on the control mode.

        Args:
            joint: Joint to check and modify in place.
            mode: current control mode.
        """
        original_velocity = joint.velocity
        if mode in (JointControlMode.VELOCITY, JointControlMode.MIT):
            joint.velocity = max(-100, min(100, joint.velocity))
        else:
            joint.velocity = min(100, abs(joint.velocity))

        if joint.velocity != original_velocity and mode != JointControlMode.CURRENT:
            logger.warning(
                "[Joint] ID: %s velocity %s adjusted to %s in %s mode",
                JointId(joint.id).name,
                original_velocity,
                joint.velocity,
                mode.name,
            )

    @staticmethod
    def _check_current_limit(joint: JointCommand, mode: JointControlMode):
        """Validate and clamp joint current based on the control mode.

        Args:
            joint: Joint to check and modify in place.
            mode: current control mode.
        """
        original_current = joint.current
        if mode in (JointControlMode.CURRENT, JointControlMode.MIT):
            joint.current = max(-100, min(100, joint.current))
        else:
            joint.current = min(100, abs(joint.current))

        if joint.current != original_current:
            logger.warning(
                "[Joint] ID: %s current %s adjusted to %s in %s mode",
                JointId(joint.id).name,
                original_current,
                joint.current,
                mode.name,
            )

    @staticmethod
    def _check_mit_gains(joint: JointCommand):
        """Clamp MIT gains to their ranges while keeping kp greater than kd."""
        original_kp, original_kd = joint.kp, joint.kd
        joint.kp = max(10, min(2000, joint.kp))
        joint.kd = max(0, min(50, joint.kp - 1, joint.kd))
        if (joint.kp, joint.kd) != (original_kp, original_kd):
            logger.warning(
                "[Joint] ID: %s MIT gains adjusted from kp=%s, kd=%s to kp=%s, kd=%s",
                JointId(joint.id).name,
                original_kp,
                original_kd,
                joint.kp,
                joint.kd,
            )

    def search_adapters(self) -> list[str]:
        """Search for available device adapters.

        Returns:
            List of adapter IDs.
        """
        id_list = self._comm.search_adapters()

        if id_list:
            logger.info("Available adapters:\n%s", "\n".join(str(id) for id in id_list))
        else:
            logger.warning("No adapters found")

        return id_list

    def _resolve_product_type(self) -> bool:
        """Verify the connected device matches the configured product type.

        Returns:
            True if the device name matches the expected product name.
        """
        try:
            device_name = self.get_device_name()
        except Exception:
            logger.error("Failed to get device name for verification", exc_info=True)
            return False

        expected_names = [self._product_config.name]
        if device_name.lower() not in {name.lower() for name in expected_names if name}:
            logger.error(
                "Product type mismatch: expected one of %s, got %s",
                expected_names,
                device_name,
            )
            return False
        return True

    def _validate_baud_rate(self, baudrate: BaudRateConfig | None) -> BaudRateConfig | None:
        if self._comm_type == CommType.RS485:
            if baudrate is not None and not isinstance(baudrate, RS485BaudRate):
                raise TypeError("RS485 communication requires RS485BaudRate")
        elif self._comm_type == CommType.CANFD:
            if baudrate is not None and not isinstance(baudrate, CANFDBitTiming):
                raise TypeError("CANFD communication requires CANFDBitTiming")
        else:
            baudrate = None
            logger.warning("Unsupported communication type; ignoring baud rate")
        return baudrate

    def open(
        self,
        id: str = "auto",
        slave_id: int | None = None,
        baudrate: BaudRateConfig | None = None,
    ) -> bool:
        """Open the device connection.

        Args:
            id: Device ID. Use "auto" to search automatically.
            slave_id: Optional RS485/CANFD slave ID override for this connection.
                Default RS485/CANFD slave IDs are 0x31 for the left hand and
                0x32 for the right hand. For EtherCAT with a single slave,
                the default slave ID is 0x01.
            baudrate: Optional RS485 baud rate or CANFD bit timing profile.
                Pass ``RS485BaudRate`` for RS485 and ``CANFDBitTiming`` for
                CANFD. When omitted, RS485 defaults to
                ``RS485BaudRate.BAUD_1000000`` (0x05, 1000000 baud), and CANFD
                defaults to ``CANFDBitTiming.TIMING_1M_5M`` (0x07): arbitration
                at 1 Mbit/s and data at 5 Mbit/s, both at 75% sample point.
                Ignored for EtherCAT.

        Returns:
            True if the connection is established successfully.
        """
        if baudrate is not None:
            baudrate = self._validate_baud_rate(baudrate)

        if self.is_connected():
            return True

        if id == "auto":
            adapters = self._comm.search_adapters()
            logger.info("Found IDs:\n\t%s", "\n\t".join(str(id) for id in adapters))
        else:
            adapters = [id]

        for adapter in adapters:
            if not self._comm.connect(adapter, slave_id=slave_id, baudrate=baudrate):
                continue
            if not self._resolve_product_type():
                self.close()
                continue
            logger.info("Device opened successfully (ID: %s)", adapter)
            return True
        return False

    def set_slave_id(self, slave_id: int) -> bool:
        """Set the connected RS485/CANFD device slave ID.

        Not supported for EtherCAT.

        Args:
            slave_id: New slave ID (1..63) written to holding register ``0x0003``.

        Returns:
            True if the device accepted the new ID.
        """
        if not 0 < slave_id <= 0x3F:
            raise ValueError("slave_id must be in range 1..63")
        result = self._comm.set_slave_id(slave_id)
        if result:
            logger.info("Slave ID set to 0x%02X", slave_id)
        return result

    def set_baudrate(self, baudrate: BaudRateConfig) -> bool:
        """Set the RS485 baud rate or CANFD bit timing (register 0x0004).

        The protocol gear mapped from the enum is stored in Flash and takes
        effect after the next power-up.

        Args:
            baudrate: ``RS485BaudRate`` for RS485 connections, or
                ``CANFDBitTiming`` for CANFD connections.

        Returns:
            True if the device accepted the configuration.
        """
        baudrate = self._validate_baud_rate(baudrate)
        result = self._comm.set_baudrate(baudrate)
        if result:
            logger.info("Baudrate set to %s (effective after reboot)", baudrate.name)
        return result

    def close(self) -> bool:
        """Close the device connection.

        Returns:
            True.
        """
        try:
            self._comm.disconnect()
            logger.info("Disconnected from device")
        finally:
            self._tactile_opened = False
        return True

    def is_connected(self) -> bool:
        """Return whether the device is currently connected."""
        if self._comm.is_connected():
            return True
        self._tactile_opened = False
        return False

    def subscribe(self, callback, interval_ms: int | None = None):
        """Subscribe to device data updates.

        The callback receives a unified `DeviceData` object regardless of the
        underlying communication protocol.

        Args:
            callback: Callable invoked with a `DeviceData` instance.
            interval_ms: Optional protocol-specific polling interval in milliseconds.

        Returns:
            Subscription ID.
        """
        if not self.is_connected():
            raise RuntimeError("Device is not connected")

        return self._comm.subscribe_device_data(
            callback,
            include_tactile=self._tactile_opened,
            interval_ms=interval_ms,
        )

    def unsubscribe(self, sub_id):
        """Unsubscribe from data updates.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription was removed successfully.
        """
        result = self._comm.unsubscribe(sub_id)
        return result

    def get_firmware_version(self) -> str:
        """Retrieve the firmware version.

        Returns:
            Firmware version string.
        """
        return self._comm.get_firmware_version()

    def get_device_name(self) -> str:
        """Retrieve the device name.

        Returns:
            Device name string.
        """
        return self._comm.get_device_name()

    def get_firmware_package_version(self) -> str:
        """Retrieve the firmware package version.

        Returns:
            Version string, or "N/A" if the version is not available.
        """
        return self._comm.get_firmware_package_version()

    def get_position_sensor_version(self) -> str:
        """Retrieve the position sensor version.

        Returns:
            Version string, or "N/A" if the version is not available.
        """
        return self._comm.get_position_sensor_version()

    def get_tactile_sensor_version(self) -> str:
        """Retrieve the tactile MCU version.

        Returns:
            Version string, or "N/A" if the version is not available.
        """
        return self._comm.get_tactile_sensor_version()

    def get_serial_number(self) -> str:
        """Retrieve the product serial number.

        Returns:
            Device ASCII serial string.
        """
        return self._comm.get_serial_number()

    def get_stall_tolerances(self) -> dict[JointId, int]:
        """Retrieve per-joint stall tolerances when supported."""
        return self._comm.get_stall_tolerances()

    def set_stall_tolerances(self, tolerances: dict[JointId, int]) -> bool:
        """Set per-joint stall tolerances when supported."""
        return self._comm.set_stall_tolerances(tolerances)

    def get_pid_parameters(self) -> list[int]:
        """Retrieve the raw closed-loop PID parameter array when supported."""
        return self._comm.get_pid_parameters()

    def set_pid_parameters(self, parameters: list[int]) -> bool:
        """Set the raw closed-loop PID parameter array when supported."""
        return self._comm.set_pid_parameters(parameters)

    def get_hand_state_machine(self) -> HandRuntimeState | int:
        """Retrieve the whole-hand runtime state."""
        return self._comm.get_hand_state_machine()

    def get_motor_driver_version(self) -> str:
        """Retrieve the motor driver version.

        Returns:
            Version string, or "N/A" if the version is not available.
        """
        return self._comm.get_motor_driver_version()

    def get_thumb_tactile_sensor_version(self) -> str:
        """Retrieve the thumb tactile sensor version.

        Returns:
            Version string, or "N/A" if the version is not available.
        """
        return self._comm.get_thumb_tactile_sensor_version()

    def get_finger_tactile_sensor_version(self) -> str:
        """Retrieve the finger tactile sensor version.

        Returns:
            Version string, or "N/A" if the version is not available.
        """
        return self._comm.get_finger_tactile_sensor_version()

    def fault_clearance(self) -> bool:
        """Clear device faults.

        Returns:
            True on success, False if the device rejects the command.
        """
        return self._comm.clear_fault()

    def tactile_open(self) -> bool:
        """Enable the tactile sensors.

        Returns:
            True on success, False if the device rejects the command.

        Raises:
            NotImplementedError: If the product has no tactile support.
        """
        if not self._has_tactile:
            raise NotImplementedError("This product does not support tactile sensors")
        result = self._comm.open_tactile()
        if result:
            self._tactile_opened = True
        return result

    def tactile_close(self) -> bool:
        """Disable the tactile sensors.

        Returns:
            True if the sensors are closed or were not open, False if the device rejects the command.
        """
        if not self._tactile_opened:
            return True
        result = self._comm.close_tactile()
        if result:
            self._tactile_opened = False
        return result

    def tactile_zero(self) -> bool:
        """Zero-calibrate the tactile sensors.

        Returns:
            True on success, False if the device rejects the command.

        Raises:
            RuntimeError: If the tactile sensors are not open.
        """
        if not self._tactile_opened:
            raise RuntimeError("Tactile sensors are not open")
        return self._comm.zero_tactile()

    def get_hand_type(self) -> HandType:
        """Retrieve the hand type (left or right).

        Returns:
            HandType.NONE, HandType.LEFT_HAND, or HandType.RIGHT_HAND.
        """
        htype = self._comm.get_hand_type()
        if htype == 1:
            return HandType.LEFT_HAND
        if htype == 2:
            return HandType.RIGHT_HAND
        return HandType.NONE

    def move_joints(self,
                    joints: list[JointCommand],
                    hand_control_mode: HandControlMode = HandControlMode.POSITION) -> bool:
        """Send joint control commands.

        Communication exceptions propagate to the caller.

        Args:
            joints: List of JointCommand objects.
            hand_control_mode: Hand control mode. CUSTOM uses each joint's control_mode and
                loop_type; other modes use closed-loop control. Defaults to POSITION.

        Returns:
            True if the command is sent successfully.
        """
        active_joints = []
        for joint in joints:
            if joint.id in self._passive_joints:
                logger.warning("Passive joint %s will be ignored", JointId(joint.id).name)
                continue
            # Create a copy so the caller's original object is not mutated.
            joint_cmd = JointCommand(
                id=joint.id,
                control_mode=(joint.control_mode if hand_control_mode == HandControlMode.CUSTOM else
                              JointControlMode(hand_control_mode.value)),
                loop_type=joint.loop_type,
                control_state=joint.control_state,
                angle=joint.angle,
                velocity=joint.velocity,
                current=joint.current,
                kp=joint.kp,
                kd=joint.kd,
            )
            self._check_current_limit(joint_cmd, joint_cmd.control_mode)
            if joint_cmd.control_mode != JointControlMode.CURRENT:
                self._check_velocity_limit(joint_cmd, joint_cmd.control_mode)
            if joint_cmd.control_mode in (JointControlMode.POSITION, JointControlMode.MIT):
                self._check_joint_limit(joint_cmd, self._active_joints[joint.id],
                                        joint_cmd.control_mode)
            if joint_cmd.control_mode == JointControlMode.MIT:
                self._check_mit_gains(joint_cmd)
            active_joints.append(joint_cmd)

        if not active_joints:
            logger.warning("No active joints to move after filtering passive joints")
            return False

        return self._comm.move_joints(active_joints, hand_control_mode)

    def disable_hand(self) -> bool:
        """Disable all active joints; communication exceptions propagate to the caller."""
        return self._comm.disable_hand()

    def stop(self) -> bool:
        """Stop all joint motion immediately; communication exceptions propagate to the caller."""
        return self._comm.stop()

    def get_joints(self) -> list[JointData]:
        """Retrieve the current state of all joints.

        Returns:
            List of JointData objects.
        """
        return self._comm.get_joints()

    def get_hand_info(self) -> HandData:
        """Retrieve high-level hand status information.

        Returns:
            HandData instance.
        """
        return self._comm.get_hand_info()

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data.

        Returns:
            Dictionary mapping TactileSensorId to TactileData.

        Raises:
            RuntimeError: If the tactile sensors are not open.
        """
        if not self._tactile_opened:
            raise RuntimeError("Tactile sensors are not open")
        return self._comm.get_tactile_data()

    def set_safety_margin(self, margin: float) -> None:
        """Set the collision detection safety margin.

        Args:
            margin: Safety margin in the range [0.0, 1.0].
                0.0 = no margin (exact contact).
                1.0 = maximum margin (2 mm).

        Raises:
            ValueError: If margin is outside [0.0, 1.0].

        Example:
            >>> hand = GHand()
            >>> hand.open("auto")
            >>> hand.set_safety_margin(0.5)  # 1 mm margin
        """
        if margin < 0.0 or margin > 1.0:
            logger.warning(
                "Safety margin %s out of range [0.0, 1.0], clamping to valid range",
                margin,
            )
            margin = max(0.0, min(1.0, margin))

        self._safety_margin = margin
        logger.info("Collision safety margin set to %s (%.1f mm)", margin, margin * 2)

    def _ensure_collision_checker(self) -> CollisionClient:
        """Initialize the collision checker object on first use."""

        if self._collision_checker is None:
            self._collision_checker = CollisionClient()
        return self._collision_checker

    def check_collision(self, joints: list[JointCommand]) -> CollisionCheckResult:
        """Check whether the target joint pose would cause a collision.

        This method only performs collision detection and does not move the hand.
        If a collision is detected, the result includes safe angles.

        Args:
            joints: List of JointCommand objects. Unspecified joints are filled from
                the current device state if connected, otherwise 0 degrees.

        Returns:
            CollisionCheckResult with has_collision, safe_angles, and
            collision_pairs.

        Example:
            >>> hand = GHand()
            >>> result = hand.check_collision(joints)
            >>> if result.has_collision:
            ...     print("Collision detected, using safe angles")
            ...     joints = hand._angles_to_joints(result.safe_angles)
        """

        collision_checker = self._ensure_collision_checker()

        current_joints = None
        if self.is_connected():
            try:
                current_joints = self.get_joints()
            except Exception:
                logger.debug("Unable to get current joint state, using defaults (0 degrees)")

        target_angles = joints_to_nparray(joints, current_joints)
        if current_joints is None:
            neutral_angles = internal_radians_to_sdk_degrees(neutral_internal_radians())
            for index, joint_id in enumerate(COLLISION_JOINT_ORDER):
                target_angles[int(joint_id)] = neutral_angles[index]
            for joint in joints:
                target_angles[int(joint.id)] = float(joint.angle)

        collision_angles = np.asarray(
            [target_angles[int(joint_id)] for joint_id in COLLISION_JOINT_ORDER])

        result = collision_checker.collision_check(target_angles=collision_angles,
                                                   safety_margin=self._safety_margin)

        if result.has_collision:
            if result.safe_angles is None:
                raise RuntimeError("Collision checker reported a collision without safe angles")
            safe_angles = target_angles.copy()
            for index, joint_id in enumerate(COLLISION_JOINT_ORDER):
                safe_angles[int(joint_id)] = result.safe_angles[index]
            result.safe_angles = safe_angles
        else:
            result.safe_angles = target_angles.copy()
            result.collision_pairs = None
        return result

    @staticmethod
    def _joints_to_angles(joints: list[JointCommand],
                          current_joints: list[JointData] | None = None) -> Any:
        """Convert a list of Joints to a numpy array.

        Args:
            joints: List of JointCommand objects.
            current_joints: Optional current joint states for filling unspecified joints.

        Returns:
            18-element numpy array of joint angles in degrees.
        """

        return joints_to_nparray(joints, current_joints)

    @staticmethod
    def _angles_to_joints(angles: Any,
                          velocity: int = 100,
                          current: int = 100) -> list[JointCommand]:
        """Convert a numpy array to a list of JointCommand objects.

        Args:
            angles: 18-element numpy array of joint angles in degrees.
            velocity: Velocity percentage applied to all joints. Defaults to 100.
            current: Current percentage applied to all joints. Defaults to 100.

        Returns:
            List of 18 JointCommand objects.
        """

        return nparray_to_joints(angles, velocity, current)
