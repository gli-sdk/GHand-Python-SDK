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
from .collision.angle_mapping import internal_radians_to_sdk_degrees
from .collision.angle_mapping import neutral_internal_radians
from .diagnostics import (
    ConnectionDiagnostics,
    Diagnostics,
    ErrorDiagnostics,
    IdentityDiagnostics,
    SubscriptionDiagnostics,
)
from .types import (
    OperationResult,
    SdkError,
    CANFDBitTiming,
    CommType,
    JointId,
    ProductType,
    RS485BaudRate,
    CtrlMode,
    HandType,
    ProductConfig,
    JointCommand,
    HandState,
    HandStateMachine,
    JointData,
)

logger = logging.getLogger("ghand.ghand")

BaudRateSelection = RS485BaudRate | CANFDBitTiming

_COLLISION_JOINT_ORDER = (
    JointId.LF_MCP,
    JointId.LF_PIP,
    JointId.LF_DIP,
    JointId.RF_MCP,
    JointId.RF_PIP,
    JointId.RF_DIP,
    JointId.MF_MCP,
    JointId.MF_PIP,
    JointId.MF_DIP,
    JointId.FF_MCP_AA,
    JointId.FF_MCP,
    JointId.FF_PIP,
    JointId.FF_DIP,
    JointId.THUMB_TMC_PS,
    JointId.THUMB_TMC_AA,
    JointId.THUMB_TMC_FE,
    JointId.THUMB_MCP,
    JointId.THUMB_IP,
)


class GHand:
    """High-level API for the GHand dexterous hand."""

    def __init__(
        self, product_type: ProductType, comm_type: CommType
    ):
        """Initialize the GHand instance.

        Args:
            product_type: Product model (e.g. ``ProductType.GHand5``).
            comm_type: Communication protocol (e.g. ``CommType.CANFD``).
        """
        self._product_type = product_type
        self._comm_type = comm_type
        self._product_config = load_product_config(product_type)
        self._joint_limits = self._product_config.joint_limits.copy()
        self._passive_joints = set(self._product_config.valid_joints) - set(
            self._joint_limits.keys()
        )
        self._has_tactile = self._product_config.has_tactile
        self._comm = self._create_comm(comm_type)
        self._hand_type = HandType.NONE
        self._firmware_version = ""
        self._opened = False
        self._tactile_opened = False
        self._safety_margin = 0.0
        self._collision_checker = None
        self._last_result = OperationResult(SdkError.OK, "", comm_type)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        try:
            if getattr(self, "_opened", False):
                self.close()
        except Exception:
            pass

    def _set_last_result(self, code: SdkError, message: str = "") -> None:
        self._last_result = OperationResult(code, message, self._comm_type)

    def get_last_result(self) -> OperationResult:
        """Return the latest SDK operation result."""
        return self._last_result

    def get_last_error(self) -> SdkError:
        """Return the latest SDK operation error code."""
        return self._last_result.code

    def get_last_error_message(self) -> str:
        """Return the latest SDK operation error message."""
        return self._last_result.message

    def get_diagnostics(self) -> Diagnostics:
        """Return machine-readable SDK diagnostics."""
        connected = False
        try:
            connected = self._comm.is_connected()
        except Exception:
            connected = False
        subscription = self._collect_subscription_diagnostics()
        return Diagnostics(
            connection=ConnectionDiagnostics(
                connected=connected,
                comm_type=self._comm_type,
                device="",
            ),
            identity=IdentityDiagnostics(
                product=self._product_type,
                hand_type=self._hand_type,
                firmware_version=self._firmware_version,
            ),
            subscription=subscription,
            error=ErrorDiagnostics(
                last_sdk_error=self._last_result.code,
                last_error_message=self._last_result.message,
            ),
        )

    def _collect_subscription_diagnostics(self) -> SubscriptionDiagnostics:
        sub_manager = getattr(self._comm, "_sub_manager", None)
        if sub_manager is not None:
            with sub_manager._lock:
                return SubscriptionDiagnostics(
                    active_subscriptions=len(sub_manager._subscribers),
                    received_frames=sub_manager._data_seq,
                    dispatched_frames=sub_manager._dispatched_seq,
                )
        callbacks = getattr(self._comm, "_callbacks", None)
        if callbacks is not None:
            return SubscriptionDiagnostics(active_subscriptions=len(callbacks))
        return SubscriptionDiagnostics()

    def _create_comm(self, comm_type: CommType) -> IComm:
        """Instantiate the appropriate IComm implementation."""
        return create_comm(comm_type, self._product_config)

    def _apply_product_config(self, config: ProductConfig) -> None:
        """Apply a new product configuration.

        Args:
            config: New product configuration to apply.
        """
        self._product_config = config
        self._joint_limits = config.joint_limits.copy()
        self._passive_joints = set(config.valid_joints) - set(self._joint_limits.keys())
        self._has_tactile = config.has_tactile
        self._tactile_opened = False
        self._comm.update_config(config)

    def _sync_product_config_from_comm(self) -> None:
        """Sync high-level cached config with protocol-selected runtime layout."""
        config = getattr(self._comm, "config", None)
        if config is None or config is self._product_config:
            return
        self._product_config = config
        self._joint_limits = config.joint_limits.copy()
        self._passive_joints = set(config.valid_joints) - set(self._joint_limits.keys())
        self._has_tactile = config.has_tactile
        self._tactile_opened = False

    @staticmethod
    def _check_joint_limit(joint: JointCommand, limit, mode: CtrlMode):
        """Clamp the joint angle to its configured limits.

        Args:
            joint: Joint to check and modify in place.
            limit: Tuple of (min, max) in degrees.
            mode: Current control mode.
        """
        if mode == CtrlMode.SPEED or mode == CtrlMode.CURRENT:
            logger.warning(
                "[Joint] ID: %s angle input is invalid in %s mode and will be ignored",
                JointId(joint.id).name, mode.name,
            )
        if joint.angle < limit[0]:
            joint.angle = limit[0]
            if mode == CtrlMode.POSITION:
                logger.warning(
                    "[Joint] ID: %s angle below limit, clamped to min value %.1f degrees",
                    JointId(joint.id).name, limit[0]
                )
        elif joint.angle > limit[1]:
            joint.angle = limit[1]
            if mode == CtrlMode.POSITION:
                logger.warning(
                    "[Joint] ID: %s angle above limit, clamped to max value %.1f degrees",
                    JointId(joint.id).name, limit[1]
                )

    @staticmethod
    def _check_speed_limit(joint: JointCommand, mode: CtrlMode):
        """Validate and clamp joint speed based on the control mode.

        Args:
            joint: Joint to check and modify in place.
            mode: current control mode.
        """
        if mode == CtrlMode.CURRENT:
            logger.warning(
                "[Joint] ID: %s speed input is invalid in current mode and will be ignored",
                JointId(joint.id).name,
            )
        original_speed = joint.speed
        if mode == CtrlMode.SPEED:
            joint.speed = max(-100, min(100, joint.speed))
        else:
            joint.speed = min(100, abs(joint.speed))

        if joint.speed != original_speed and mode != CtrlMode.CURRENT:
            logger.warning(
                "[Joint] ID: %s speed %s adjusted to %s in %s mode",
                JointId(joint.id).name,
                original_speed,
                joint.speed,
                mode.name,
            )

    @staticmethod
    def _check_current_limit(joint: JointCommand, mode: CtrlMode):
        """Validate and clamp joint current based on the control mode.

        Args:
            joint: Joint to check and modify in place.
            mode: current control mode.
        """
        original_current = joint.current
        if mode == CtrlMode.CURRENT:
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

    def _bitrate_units_to_try(
        self, baudrate_gear: int | None
    ) -> tuple[list[int | None], bool]:
        """Return baud rate gears to try and a quiet flag.

        When no gear is provided, the protocol default gear is used. Auto-scan
        across multiple gears is intentionally not performed because switching
        CANFD bitrates without knowing the device's current gear can leave the
        adapter or device in a bus-recovery state and cause all attempts to fail.
        """
        if baudrate_gear is not None:
            return [baudrate_gear], False
        default_gear = self._comm.get_default_baudrate_gear()
        if default_gear is not None:
            return [default_gear], True
        return [None], False

    def _baud_rate_to_gear(self, baud_rate: BaudRateSelection | None) -> int | None:
        if baud_rate is None:
            return None
        if self._comm_type == CommType.RS485:
            if not isinstance(baud_rate, RS485BaudRate):
                raise TypeError("RS485 communication requires RS485BaudRate")
            return int(baud_rate)
        if self._comm_type == CommType.CANFD:
            if not isinstance(baud_rate, CANFDBitTiming):
                raise TypeError("CANFD communication requires CANFDBitTiming")
            return int(baud_rate)
        raise TypeError("baud_rate is only supported for RS485 and CANFD")

    def open(
        self,
        id: str = "auto",
        slave_id: int | None = None,
        baud_rate: BaudRateSelection | None = None,
        *,
        baudrate_gear: int | None = None,
    ) -> bool:
        """Open the device connection.

        Args:
            id: Device ID. Use "auto" to search automatically.
            slave_id: Optional RS485/CANFD slave ID override for this connection.
            baud_rate: Optional RS485 baud rate or CANFD bit timing profile.
                Pass ``RS485BaudRate`` for RS485 and ``CANFDBitTiming`` for
                CANFD. When omitted, the protocol default is used. The legacy
                ``baudrate_gear`` keyword is accepted for compatibility but is
                not recommended for new code.

        Returns:
            True if the connection is established successfully.
        """
        if baud_rate is not None and baudrate_gear is not None:
            raise ValueError("Use either baud_rate or baudrate_gear, not both")
        if baud_rate is not None:
            baudrate_gear = self._baud_rate_to_gear(baud_rate)

        if slave_id is not None:
            self._product_config.slave_id = slave_id
            self._comm.update_config(self._product_config)

        if self._opened:
            try:
                if self._comm.is_connected():
                    self._set_last_result(SdkError.OK)
                    return True
            except Exception:
                logger.exception("Failed to query connection state before reopen")
            logger.warning("Connection state is stale; resetting before reopening")
            self._opened = False

        if id == "auto":
            adapters = self._comm.search_adapters()
            logger.info("Found IDs:\n\t%s", "\n\t".join(str(id) for id in adapters))
            gears, quiet = self._bitrate_units_to_try(baudrate_gear)
            for adapter in adapters:
                for gear in gears:
                    connected = self._comm.connect(
                        adapter, slave_id=slave_id, baudrate_gear=gear, quiet=quiet
                    )
                    if not connected:
                        continue

                    self._opened = True
                    if self._resolve_product_type():
                        self._sync_product_config_from_comm()
                        self._set_last_result(SdkError.OK)
                        if gear is None:
                            logger.info("Device opened successfully (ID: %s)", adapter)
                        else:
                            logger.info(
                                "Device opened successfully (ID: %s, baudrate_gear=0x%02X)",
                                adapter,
                                gear,
                            )
                        self._comm.stop()
                        time.sleep(0.1)
                        return True

                    logger.error("Device verification failed (ID: %s)", adapter)
                    self._comm.disconnect()
                    self._opened = False
                    self._set_last_result(
                        SdkError.DEVICE_REJECTED,
                        f"device verification failed: {adapter}",
                    )
                else:
                    logger.error("Failed to open device (ID: %s)", adapter)
            self._set_last_result(SdkError.TRANSPORT_ERROR, "failed to open device")
            return False
        else:
            connected = self._comm.connect(
                id, slave_id=slave_id, baudrate_gear=baudrate_gear,
            )
            if not connected:
                logger.error("Failed to open device (ID: %s)", id)
                self._set_last_result(SdkError.TRANSPORT_ERROR, f"failed to open {id}")
                return False
            self._opened = True
            logger.info("Device opened successfully (ID: %s)", id)

        if not self._opened:
            self._set_last_result(SdkError.TRANSPORT_ERROR, "device was not opened")
            return False
        if not self._resolve_product_type():
            self._comm.disconnect()
            self._opened = False
            self._set_last_result(SdkError.DEVICE_REJECTED, "product type mismatch")
            return False

        self._sync_product_config_from_comm()
        
        self._comm.stop()
        time.sleep(0.1)
        self._set_last_result(SdkError.OK)
        return True

    def set_slave_id(self, slave_id: int) -> bool:
        """Set the connected RS485/CANFD device slave ID.

        Args:
            slave_id: New slave ID written to holding register ``0x0000``.

        Returns:
            True if the device accepted the new ID.
        """
        if self._comm_type not in (CommType.CANFD, CommType.RS485):
            logger.error("set_slave_id is only supported for CANFD and RS485")
            self._set_last_result(SdkError.NOT_SUPPORTED, "set_slave_id is only supported for CANFD and RS485")
            return False
        if not self.is_connected():
            self._set_last_result(SdkError.NOT_CONNECTED, "device is not connected")
            raise RuntimeError("Device is not connected")

        result = self._comm.set_slave_id(slave_id)
        if result:
            self._product_config.slave_id = slave_id
            logger.info("Slave ID set to 0x%02X", slave_id)
            self._set_last_result(SdkError.OK)
        else:
            self._set_last_result(SdkError.DEVICE_REJECTED, "device rejected slave ID change")
        return result

    def set_baudrate_config(
        self,
        baud_rate: BaudRateSelection,
    ) -> bool:
        """Set the RS485 baud rate or CANFD bit timing (register 0x0004).

        The protocol gear mapped from the enum is stored in Flash and takes
        effect after the next power-up.

        Args:
            baud_rate: ``RS485BaudRate`` for RS485 connections, or
                ``CANFDBitTiming`` for CANFD connections.

        Returns:
            True if the device accepted the configuration.
        """
        if self._comm_type not in (CommType.CANFD, CommType.RS485):
            logger.error("set_baudrate_config is only supported for CANFD and RS485")
            self._set_last_result(SdkError.NOT_SUPPORTED, "set_baudrate_config is only supported for CANFD and RS485")
            return False
        if not self.is_connected():
            self._set_last_result(SdkError.NOT_CONNECTED, "device is not connected")
            raise RuntimeError("Device is not connected")

        baudrate_gear = self._baud_rate_to_gear(baud_rate)
        result = self._comm.set_baudrate_config(baudrate_gear)
        if result:
            logger.info(self._comm.describe_baudrate_config(baudrate_gear))
            self._set_last_result(SdkError.OK)
        else:
            self._set_last_result(SdkError.DEVICE_REJECTED, "device rejected baudrate configuration")
        return result

    def close(self) -> bool:
        """Close the device connection.

        Returns:
            True.
        """
        connected = self._opened
        try:
            connected = connected or self._comm.is_connected()
        except Exception:
            logger.exception("Failed to query connection state before close")

        if connected:
            self._comm.stop()
            time.sleep(1)
            self._comm.disconnect()
            logger.info("Disconnected from device")
        self._opened = False
        self._tactile_opened = False
        self._set_last_result(SdkError.OK)
        return True

    def is_connected(self) -> bool:
        """Return whether the device is currently connected."""
        if not self._opened:
            return False
        try:
            if self._comm.is_connected():
                return True
        except Exception:
            logger.exception("Failed to query connection state")
        self._opened = False
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
            self._set_last_result(SdkError.NOT_CONNECTED, "device is not connected")
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
        self._set_last_result(
            SdkError.OK if result else SdkError.INVALID_ARGUMENT,
            "" if result else f"unknown subscription id: {sub_id}",
        )
        return result

    def get_firmware_version(self) -> str:
        """Retrieve the firmware version.

        Returns:
            Firmware version string (e.g., "v1.0.0").
        """
        if self._firmware_version == "":
            self._firmware_version = self._comm.get_firmware_version()
        return self._firmware_version

    def get_device_name(self) -> str:
        """Retrieve the device name.

        Returns:
            Device name string.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_device_name()

    def get_firmware_package_version(self) -> str:
        """Retrieve the firmware package version.

        Returns:
            Version string, or "N/A" if the version is not available.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_firmware_package_version()

    def get_position_sensor_version(self) -> str:
        """Retrieve the position sensor version.

        Returns:
            Version string, or "N/A" if the version is not available.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_position_sensor_version()

    def get_tactile_sensor_version(self) -> str:
        """Retrieve the tactile MCU version.

        Returns:
            Version string, or "N/A" if the version is not available.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_tactile_sensor_version()

    def get_serial_number(self) -> str:
        """Retrieve the product serial number.

        Returns:
            Device ASCII serial string.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_serial_number()

    def set_serial_number(self, serial_number: str) -> bool:
        """Set the product serial number when supported by the active protocol."""
        result = self._comm.set_serial_number(serial_number)
        self._set_last_result(
            SdkError.OK if result else SdkError.DEVICE_REJECTED,
            "" if result else "device rejected serial number configuration",
        )
        return result

    def get_stall_tolerances(self) -> dict[JointId, int]:
        """Retrieve per-joint stall tolerances when supported."""
        return self._comm.get_stall_tolerances()

    def set_stall_tolerances(self, tolerances: dict[JointId, int]) -> bool:
        """Set per-joint stall tolerances when supported."""
        result = self._comm.set_stall_tolerances(tolerances)
        self._set_last_result(
            SdkError.OK if result else SdkError.DEVICE_REJECTED,
            "" if result else "device rejected stall tolerance configuration",
        )
        return result

    def get_pid_parameters(self) -> list[int]:
        """Retrieve the raw closed-loop PID parameter array when supported."""
        return self._comm.get_pid_parameters()

    def set_pid_parameters(self, parameters: list[int]) -> bool:
        """Set the raw closed-loop PID parameter array when supported."""
        result = self._comm.set_pid_parameters(parameters)
        self._set_last_result(
            SdkError.OK if result else SdkError.DEVICE_REJECTED,
            "" if result else "device rejected PID parameter configuration",
        )
        return result

    def get_hand_state_machine(self) -> HandStateMachine:
        """Retrieve the whole-hand runtime state."""
        return self._comm.get_hand_state_machine()

    def get_motor_driver_version(self) -> str:
        """Retrieve the motor driver version.

        Returns:
            Version string, or "N/A" if the version is not available.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_motor_driver_version()

    def get_thumb_tactile_sensor_version(self) -> str:
        """Retrieve the thumb tactile sensor version.

        Returns:
            Version string, or "N/A" if the version is not available.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_thumb_tactile_sensor_version()

    def get_finger_tactile_sensor_version(self) -> str:
        """Retrieve the finger tactile sensor version.

        Returns:
            Version string, or "N/A" if the version is not available.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_finger_tactile_sensor_version()

    def fault_clearance(self) -> bool:
        """Clear device faults.

        Returns:
            True on success, False on failure.
        """
        result = self._comm.clear_fault()
        if result:
            logger.info("Fault cleared successfully")
            self._set_last_result(SdkError.OK)
        else:
            logger.error("Failed to clear fault")
            self._set_last_result(SdkError.DEVICE_REJECTED, "failed to clear fault")
        return result

    def tactile_open(self) -> bool:
        """Enable the tactile sensors.

        Returns:
            True on success, False if the product has no tactile support or the command fails.
        """
        if not self._has_tactile:
            logger.warning("This product does not support tactile sensors")
            return False
        result = self._comm.open_tactile()
        if result:
            self._tactile_opened = True
            self._set_last_result(SdkError.OK)
        else:
            self._set_last_result(SdkError.DEVICE_REJECTED, "failed to open tactile sensors")
        return result

    def tactile_close(self) -> bool:
        """Disable the tactile sensors.

        Returns:
            True on success, False if the product has no tactile support or the command fails.
        """
        if not self._has_tactile:
            logger.warning("This product does not support tactile sensors")
            return False
        result = self._comm.close_tactile()
        if result:
            self._tactile_opened = False
            self._set_last_result(SdkError.OK)
        else:
            self._set_last_result(SdkError.DEVICE_REJECTED, "failed to close tactile sensors")
        return result

    def tactile_zero(self) -> bool:
        """Zero-calibrate the tactile sensors.

        Returns:
            True on success, False if the product has no tactile support or the command fails.
        """
        if not self._has_tactile:
            logger.warning("This product does not support tactile sensors")
            return False
        result = self._comm.zero_tactile()
        if result:
            logger.debug("Tactile zero calibration successful")
            self._set_last_result(SdkError.OK)
        else:
            logger.error("tactile_zero failed")
            self._set_last_result(SdkError.DEVICE_REJECTED, "failed to zero tactile sensors")
        return result

    def get_hand_type(self) -> HandType:
        """Retrieve the hand type (left or right).

        Returns:
            HandType.NONE, HandType.LEFT_HAND, or HandType.RIGHT_HAND.

        Raises:
            RuntimeError: If communication fails.
        """
        if self._hand_type == HandType.NONE:
            htype = self._comm.get_hand_type()
            if htype == 1:
                self._hand_type = HandType.LEFT_HAND
            elif htype == 2:
                self._hand_type = HandType.RIGHT_HAND
        return self._hand_type

    def move_joints(self, joints: list[JointCommand], mode: CtrlMode = CtrlMode.POSITION) -> bool:
        """Send joint control commands.

        Args:
            joints: List of JointCommand objects.
            mode: Control mode. Defaults to POSITION.

        Returns:
            True if the command is sent successfully.
        """
        if not self.is_connected():
            self._set_last_result(SdkError.NOT_CONNECTED, "device is not connected")
            return False

        active_joints = []
        for joint in joints:
            if joint.id in self._passive_joints:
                logger.warning("Passive joint %s will be ignored", JointId(joint.id).name)
                continue
            # Create a copy so the caller's original object is not mutated.
            joint_cmd = JointCommand(
                id=int(joint.id),
                mode=getattr(joint, "mode", mode),
                stop=joint.stop,
                angle=joint.angle,
                speed=joint.speed,
                current=joint.current,
                kp=joint.kp,
                kd=joint.kd,
            )
            effective_mode = mode
            if mode == CtrlMode.CUSTOM and joint_cmd.mode is not None:
                joint_mode_value = (
                    joint_cmd.mode.value
                    if isinstance(joint_cmd.mode, CtrlMode)
                    else int(joint_cmd.mode)
                )
                effective_mode = CtrlMode(joint_mode_value & 0x0F)
            self._check_speed_limit(joint_cmd, effective_mode)
            self._check_current_limit(joint_cmd, effective_mode)
            if joint.id in self._joint_limits:
                self._check_joint_limit(
                    joint_cmd, self._joint_limits[joint.id], effective_mode
                )
            active_joints.append(joint_cmd)

        if not active_joints:
            logger.warning("No active joints to move after filtering passive joints")
            self._set_last_result(SdkError.INVALID_ARGUMENT, "no active joints to move")
            return False

        try:
            result = self._comm.move_joints(active_joints, mode)
            self._set_last_result(
                SdkError.OK if result else SdkError.TRANSPORT_ERROR,
                "" if result else "move_joints failed",
            )
            return result
        except Exception as e:
            logger.error("Failed to move joints: %s", e)
            self._set_last_result(SdkError.TRANSPORT_ERROR, str(e))
            return False

    def disable_hand(self) -> bool:
        """Disable all active joints until the next move_joints command."""
        if not self.is_connected():
            self._set_last_result(SdkError.NOT_CONNECTED, "device is not connected")
            return False
        try:
            result = self._comm.disable_hand()
            self._set_last_result(
                SdkError.OK if result else SdkError.TRANSPORT_ERROR,
                "" if result else "disable_hand failed",
            )
            return result
        except Exception as e:
            logger.error("Failed to disable hand: %s", e)
            self._set_last_result(SdkError.TRANSPORT_ERROR, str(e))
            return False

    def stop(self) -> bool:
        """Stop all joint motion immediately."""
        try:
            result = self._comm.stop()
            self._set_last_result(
                SdkError.OK if result else SdkError.TRANSPORT_ERROR,
                "" if result else "stop failed",
            )
            return result
        except RuntimeError as e:
            logger.error("Failed to stop joints: %s", e)
            self._set_last_result(SdkError.TRANSPORT_ERROR, str(e))
            return False

    def get_joints(self) -> list[JointData]:
        """Retrieve the current state of all joints.

        Returns:
            List of JointData objects.
        """
        joints = self._comm.get_joints()
        return joints

    def get_hand_info(self) -> HandState:
        """Retrieve high-level hand status information.

        Returns:
            HandState instance.
        """
        return self._comm.get_hand_info()

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data.

        Returns:
            Dictionary mapping TactileSensorId to TactileData.
        """
        if not self._has_tactile:
            logger.warning("This product does not support tactile sensors")
            return {}
        data = self._comm.get_tactile_data()
        return data

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
        if self._opened:
            try:
                current_joints = self.get_joints()
            except Exception:
                logger.debug("Unable to get current joint state, using defaults (0 degrees)")

        target_angles = joints_to_nparray(joints, current_joints)
        if current_joints is None:
            neutral_angles = internal_radians_to_sdk_degrees(neutral_internal_radians())
            for index, joint_id in enumerate(_COLLISION_JOINT_ORDER):
                target_angles[int(joint_id)] = neutral_angles[index]
            for joint in joints:
                target_angles[int(joint.id)] = float(joint.angle)

        collision_angles = np.asarray(
            [target_angles[int(joint_id)] for joint_id in _COLLISION_JOINT_ORDER]
        )

        result = collision_checker.collision_check(
            target_angles=collision_angles, safety_margin=self._safety_margin
        )

        if result.has_collision:
            safe_angles = target_angles.copy()
            for index, joint_id in enumerate(_COLLISION_JOINT_ORDER):
                safe_angles[int(joint_id)] = result.safe_angles[index]
            result.safe_angles = safe_angles
        else:
            result.safe_angles = target_angles.copy()
            result.collision_pairs = None
        return result

    @staticmethod
    def _joints_to_angles(
        joints: list[JointCommand], current_joints: list[JointData] | None = None
    ) -> Any:
        """Convert a list of Joints to a numpy array.

        Args:
            joints: List of JointCommand objects.
            current_joints: Optional current joint states for filling unspecified joints.

        Returns:
            18-element numpy array of joint angles in degrees.
        """

        return joints_to_nparray(joints, current_joints)

    @staticmethod
    def _angles_to_joints(
        angles: Any, speed: int = 100, current: int = 100
    ) -> list[JointCommand]:
        """Convert a numpy array to a list of JointCommand objects.

        Args:
            angles: 18-element numpy array of joint angles in degrees.
            speed: Speed percentage applied to all joints. Defaults to 100.
            current: Current percentage applied to all joints. Defaults to 100.

        Returns:
            List of 18 JointCommand objects.
        """

        return nparray_to_joints(angles, speed, current)
