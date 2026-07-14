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

from ._config import load_product_config
from .comm.canfd_comm import CanfdComm
from .comm.ethercat_comm import EthercatComm
from .comm.ethercat_protocol import Tpdo
from .comm.rs485_comm import Rs485Comm
from collision_sdk import CollisionSDK
import numpy as np
from collision_sdk import CollisionCheckResult
from ._converter import joints_to_nparray
from ._converter import nparray_to_joints
from .types import (
    CommType,
    CtrlMode,
    DeviceData,
    ErrorCode,
    HandState,
    HandType,
    JointCommand,
    JointData,
    JointId,
    ProductConfig,
    ProductType,
    State,
    TactileInfo,
    TactileSensorId,
)

logger = logging.getLogger("ghand.ghand")


class GHand:
    """High-level API for the GHand dexterous hand."""

    def __init__(
        self, product_type: ProductType, comm_type: CommType
    ):
        """Initialize the GHand instance.

        Args:
            product_type: Product model (e.g. ``ProductType.G5``).
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
        self._hand_type = HandType.UNKNOWN
        self._firmware_version = ""
        self._opened = False
        self._safety_margin = 0.0
        self._collision_checker = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _create_comm(self, comm_type: CommType):
        """Instantiate the appropriate IComm implementation."""
        if comm_type == CommType.ETHERCAT:
            return EthercatComm(self._product_config)
        elif comm_type == CommType.CANFD:
            return CanfdComm(self._product_config)
        elif comm_type == CommType.RS485:
            return Rs485Comm(self._product_config)
        else:
            raise ValueError(f"Unknown communication type: {comm_type}")

    def _apply_product_config(self, config: ProductConfig) -> None:
        """Apply a new product configuration.

        Args:
            config: New product configuration to apply.
        """
        self._product_config = config
        self._joint_limits = config.joint_limits.copy()
        self._passive_joints = set(config.valid_joints) - set(self._joint_limits.keys())
        self._has_tactile = config.has_tactile
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

    def _check_joint_limit(self, joint: JointCommand, limit):
        """Clamp the joint angle to its configured limits.

        Args:
            joint: Joint to check and modify in place.
            limit: Tuple of (min, max) in degrees.
        """
        if joint.angle < limit[0]:
            joint.angle = limit[0]
            logger.warning(
                "[Joint] ID: %s angle below limit, clamped to min value %.1f degrees",
                JointId(joint.id).name, limit[0]
            )
        elif joint.angle > limit[1]:
            joint.angle = limit[1]
            logger.warning(
                "[Joint] ID: %s angle above limit, clamped to max value %.1f degrees",
                JointId(joint.id).name, limit[1]
            )

    def _check_speed_limit(self, joint: JointCommand, mode: CtrlMode):
        """Validate and clamp joint speed based on the control mode.

        Args:
            joint: Joint to check and modify in place.
            mode: Current control mode.
        """
        original_speed = joint.speed
        if mode in (CtrlMode.POSITION, CtrlMode.SPEED):
            joint.speed = max(-100, min(100, joint.speed))
        elif mode == CtrlMode.TORQUE:
            joint.speed = min(100, abs(joint.speed))

        if joint.speed != original_speed:
            logger.warning(
                "[Joint] ID: %s speed %s adjusted to %s in %s mode",
                JointId(joint.id).name,
                original_speed,
                joint.speed,
                mode.name,
            )

    def _check_torque_limit(self, joint: JointCommand, mode: CtrlMode):
        """Validate and clamp joint torque based on the control mode.

        Args:
            joint: Joint to check and modify in place.
            mode: Current control mode.
        """
        original_torque = joint.torque
        if mode in (CtrlMode.POSITION, CtrlMode.TORQUE):
            joint.torque = max(-100, min(100, joint.torque))
        elif mode == CtrlMode.SPEED and abs(joint.torque) > 100:
            joint.torque = 100

        if joint.torque != original_torque:
            logger.warning(
                "[Joint] ID: %s torque %s adjusted to %s in %s mode",
                JointId(joint.id).name,
                original_torque,
                joint.torque,
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

        expected_names = [self._product_config.name, *self._product_config.aliases]
        if device_name.lower() not in {name.lower() for name in expected_names if name}:
            logger.error(
                "Product type mismatch: expected one of %s, got %s",
                expected_names,
                device_name,
            )
            return False
        return True

    def open(self, id: str = "auto") -> bool:
        """Open the device connection.

        Args:
            id: Device ID. Use "auto" to search automatically.

        Returns:
            True if the connection is established successfully.
        """
        if self._opened:
            try:
                if self._comm.is_connected():
                    return True
            except Exception:
                logger.exception("Failed to query connection state before reopen")
            logger.warning("Connection state is stale; resetting before reopening")
            self._opened = False

        if id == "auto":
            id_list = self._comm.search_adapters()
            logger.info("Found IDs:\n\t%s", "\n\t".join(str(id) for id in id_list))
            for aid in id_list:
                if not self._comm.connect(aid):
                    logger.error("Failed to open device (ID: %s)", aid)
                    continue

                self._opened = True
                if self._resolve_product_type():
                    self._sync_product_config_from_comm()
                    logger.info("Device opened successfully (ID: %s)", aid)
                    return True

                logger.error("Device verification failed (ID: %s)", aid)
                self._comm.disconnect()
                self._opened = False

            return False
        else:
            if not self._comm.connect(id):
                logger.error("Failed to open device (ID: %s)", id)
                return False
            self._opened = True
            logger.info("Device opened successfully (ID: %s)", id)

        if not self._opened:
            return False
        if not self._resolve_product_type():
            self._comm.disconnect()
            self._opened = False
            return False

        self._sync_product_config_from_comm()
        return True

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
            self._comm.disconnect()
            logger.info("Disconnected from device")
        self._opened = False
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

    def subscribe(self, callback):
        """Subscribe to device data updates.

        The callback receives a unified `DeviceData` object regardless of the
        underlying communication protocol.

        Args:
            callback: Callable invoked with a `DeviceData` instance.

        Returns:
            Subscription ID.
        """
        if isinstance(self._comm, EthercatComm):
            def adapter(data_bytes, *args, **kwargs):
                tpdo = Tpdo.from_bytes(data_bytes, self._product_config)
                device_data = self._tpdo_to_device_data(tpdo)
                callback(device_data, *args, **kwargs)
        elif isinstance(self._comm, (CanfdComm, Rs485Comm)):
            def adapter(hand_state, joints, *args, **kwargs):
                tactile = self._comm.get_tactile_data()
                if not tactile:
                    tactile = None
                device_data = DeviceData(
                    hand=hand_state, joints=joints, tactile=tactile
                )
                callback(device_data, *args, **kwargs)
        else:
            raise TypeError(f"Unsupported comm type: {type(self._comm)}")
        return self._comm.subscribe(adapter)

    def _tpdo_to_device_data(self, tpdo) -> DeviceData:
        """Convert an EtherCAT Tpdo to a protocol-agnostic DeviceData."""
        hand = HandState(
            state=State(tpdo.hand.state),
            error=ErrorCode(tpdo.hand.error),
            temperature=tpdo.hand.temperature,
        )
        joints = [
            JointData(
                id=jid.value,
                state=State(jtpdo.state),
                error=ErrorCode(jtpdo.error),
                angle=jtpdo.angle,
                speed=jtpdo.speed,
                torque=jtpdo.torque,
            )
            for jid, jtpdo in tpdo.joints.items()
        ]
        tactile = None
        if self._product_config.has_tactile:
            tactile = {}
            for region in self._product_config.tactile_regions:
                attr = f"{region.id.name.lower()}_tactile"
                tdata = getattr(tpdo, attr, None)
                if tdata is not None:
                    tactile[region.id] = TactileInfo(
                        state=bool(tpdo.tactile_state.state & (1 << region.id.value)),
                        resultant_force=tdata.resultant_force,
                        distributed_force=tdata.sample_force,
                    )
        return DeviceData(hand=hand, joints=joints, tactile=tactile)

    def unsubscribe(self, sub_id):
        """Unsubscribe from data updates.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription was removed successfully.
        """
        return self._comm.unsubscribe(sub_id)

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

    def get_hardware_version(self) -> str:
        """Retrieve the hardware version.

        Returns:
            Hardware version string.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_hardware_version()

    def get_serial_number(self) -> int:
        """Retrieve the product serial number.

        Returns:
            Serial number.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_serial_number()

    def get_motor_driver_version(self) -> tuple:
        """Retrieve the motor driver version.

        Returns:
            Tuple of (major, minor, patch) version numbers.

        Raises:
            RuntimeError: If communication fails.
        """
        return self._comm.get_motor_driver_version()

    def fault_clearance(self) -> bool:
        """Clear device faults.

        Returns:
            True on success, False on failure.
        """
        result = self._comm.clear_fault()
        if result:
            logger.info("Fault cleared successfully")
        else:
            logger.error("Failed to clear fault")
        return result

    def joint_init(self) -> bool:
        """Initialize joint positions.

        Returns:
            True on success, False on failure.
        """
        result = self._comm.init_joint()
        if result:
            logger.info("Joint initialization completed successfully")
        else:
            logger.error("Failed to initialize joints")
        return result

    def tactile_open(self) -> bool:
        """Enable the tactile sensors.

        Returns:
            True on success, False if the product has no tactile support or the command fails.
        """
        if not self._has_tactile:
            logger.warning("This product does not support tactile sensors")
            return False
        return self._comm.open_tactile()

    def tactile_close(self) -> bool:
        """Disable the tactile sensors.

        Returns:
            True on success, False if the product has no tactile support or the command fails.
        """
        if not self._has_tactile:
            logger.warning("This product does not support tactile sensors")
            return False
        return self._comm.close_tactile()

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
        else:
            logger.error("tactile_zero failed")
        return result

    def get_hand_type(self) -> HandType:
        """Retrieve the hand type (left or right).

        Returns:
            HandType.LEFT_HAND or HandType.RIGHT_HAND.

        Raises:
            RuntimeError: If communication fails.
        """
        if self._hand_type == HandType.UNKNOWN:
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
        active_joints = []
        for joint in joints:
            if joint.id in self._passive_joints:
                logger.warning("Passive joint %s will be ignored", JointId(joint.id).name)
                continue
            # Create a copy so the caller's original object is not mutated.
            joint_cmd = JointCommand(
                id=joint.id,
                angle=joint.angle,
                speed=joint.speed,
                torque=joint.torque,
            )
            self._check_speed_limit(joint_cmd, mode)
            self._check_torque_limit(joint_cmd, mode)
            if joint.id in self._joint_limits:
                self._check_joint_limit(joint_cmd, self._joint_limits[joint.id])
            active_joints.append(joint_cmd)

        if not active_joints:
            logger.warning("No active joints to move after filtering passive joints")
            return False

        try:
            result = self._comm.move_joints(active_joints, mode)
            if result:
                logger.info("Command sent successfully")
            return result
        except RuntimeError as e:
            logger.error("Failed to move joints: %s", e)
            return False

    def stop(self) -> bool:
        """Stop all joint motion immediately."""
        try:
            result = self._comm.stop()
            if result:
                logger.info("Stop command sent successfully")
            return result
        except RuntimeError as e:
            logger.error("Failed to stop joints: %s", e)
            return False

    def get_joints(self) -> list[JointData]:
        """Retrieve the current state of all joints.

        Returns:
            List of JointData objects.
        """
        joints = self._comm.get_joints()
        logger.info("Joint data received successfully")
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
            Dictionary mapping TactileSensorId to TactileInfo.
        """
        if not self._has_tactile:
            logger.warning("This product does not support tactile sensors")
            return {}
        data = self._comm.get_tactile_data()
        logger.info("Tactile data received successfully")
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

    def _ensure_collision_checker(self) -> CollisionSDK:
        """Lazy initialization of the collision checker."""

        if self._collision_checker is None:
            self._collision_checker = CollisionSDK()
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

        result = collision_checker.collision_check(
            target_angles=np.radians(target_angles), safety_margin=self._safety_margin
        )

        if not result.has_collision:
            result = CollisionCheckResult(
                has_collision=False,
                safe_angles=target_angles.copy(),
                collision_pairs=None,
            )
        return result

    def _joints_to_angles(
        self, joints: list[JointCommand], current_joints: list[JointData] | None = None
    ) -> np.ndarray:
        """Convert a list of Joints to a numpy array.

        Args:
            joints: List of JointCommand objects.
            current_joints: Optional current joint states for filling unspecified joints.

        Returns:
            18-element numpy array of joint angles in degrees.
        """

        return joints_to_nparray(joints, current_joints)

    def _angles_to_joints(
        self, angles: np.ndarray, speed: int = 100, torque: int = 100
    ) -> list[JointCommand]:
        """Convert a numpy array to a list of JointCommand objects.

        Args:
            angles: 18-element numpy array of joint angles in degrees.
            speed: Speed percentage applied to all joints. Defaults to 100.
            torque: Torque percentage applied to all joints. Defaults to 100.

        Returns:
            List of 18 JointCommand objects.
        """

        return nparray_to_joints(angles, speed, torque)
