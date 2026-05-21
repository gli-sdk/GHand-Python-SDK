"""EtherCAT communication implementation.

Wraps EthercatClient and handles PDO encoding/decoding.
"""

import logging
import math

from .._subscription import SubscriptionManager
from ..types import (
    CommunicationError,
    CtrlMode,
    ErrorCode,
    HandState,
    JointCommand,
    JointData,
    ProductConfig,
    State,
    TactileInfo,
)
from .ethercat_driver import EthercatClient
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

    def __init__(self, config: ProductConfig):
        self._client = EthercatClient()
        self._config = config
        self._expected_tpdo_size = compute_tpdo_size(
            len(config.valid_joints),
            [r.count for r in config.tactile_regions] if config.has_tactile else None,
        )
        self._controlled_joints = [j for j in config.valid_joints if j in config.joint_limits]
        self._expected_rpdo_size = 2 + len(self._controlled_joints) * 6
        self._sub_manager = SubscriptionManager(self)

    def update_config(self, config: ProductConfig) -> None:
        """Update the cached product configuration and derived constants."""
        self._config = config
        self._expected_tpdo_size = compute_tpdo_size(
            len(config.valid_joints),
            [r.count for r in config.tactile_regions] if config.has_tactile else None,
        )
        self._controlled_joints = [j for j in config.valid_joints if j in config.joint_limits]
        self._expected_rpdo_size = 2 + len(self._controlled_joints) * 6

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
        connected = self._client.connect(device_name)
        if not connected:
            return False
        if not self._client.run(self._expected_tpdo_size, self._expected_rpdo_size):
            self._client.disconnect()
            return False
        logger.info("Device connected via EtherCAT (%s)", device_name)
        return True

    def disconnect(self) -> bool:
        """Disconnect from the EtherCAT device and stop subscriptions."""
        self._sub_manager.stop()
        self._client.disconnect()
        logger.info("Device disconnected")
        return True

    def is_connected(self) -> bool:
        """Return whether the EtherCAT client is connected."""
        return self._client._connected

    # ===== Low-level data I/O =====

    def recv_data(self) -> bytes:
        """Receive raw TPDO bytes from the device."""
        return self._client.recv_data()

    def send_data(self, data: bytes) -> None:
        """Send raw RPDO bytes to the device."""
        self._client.send_data(data)

    # ===== Joint control =====

    def move_joints(self, joints: list[JointCommand], mode: CtrlMode) -> bool:
        """Send joint control commands via RPDO.

        Args:
            joints: List of JointCommand objects.
            mode: Control mode (position, speed, or torque).

        Returns:
            True if the command is sent successfully.
        """
        rpdo = Rpdo(self._controlled_joints)
        rpdo.mode = mode.value
        rpdo.stop = 0

        for joint in joints:
            rpdo.joints[joint.id] = (math.radians(joint.angle), joint.speed, joint.torque)

        self._client.send_data(rpdo.to_bytes())
        return True

    def stop(self) -> bool:
        """Send an immediate stop command to all joints."""
        rpdo = Rpdo(self._controlled_joints)
        rpdo.mode = 0
        rpdo.stop = 1
        self._client.send_data(rpdo.to_bytes())
        return True

    # ===== State retrieval =====

    def get_joints(self) -> list[JointData]:
        """Retrieve the current state of all joints from TPDO.

        Returns:
            List of JointData objects.

        Raises:
            CommunicationError: If the received data is shorter than expected.
        """
        data = self._client.recv_data()

        tpdo = Tpdo.from_bytes(data, self._config)

        joints = []
        for joint_id, joint_tpdo in tpdo.joints.items():
            angle = math.degrees(joint_tpdo.angle)
            if abs(angle) < 1e-10:
                angle = 0.0
            joints.append(
                JointData(
                    id=joint_id,
                    angle=angle,
                    speed=joint_tpdo.speed,
                    torque=joint_tpdo.torque,
                    state=State(joint_tpdo.state),
                    error=ErrorCode(joint_tpdo.error),
                )
            )
        return joints

    def get_hand_info(self) -> HandState:
        """Retrieve high-level hand status from TPDO.

        Returns:
            HandState instance.

        Raises:
            CommunicationError: If the received data is shorter than expected.
        """
        data = self._client.recv_data()

        hand_tpdo = HandTpdo.from_bytes(data)
        return HandState(
            state=State(hand_tpdo.state),
            error=ErrorCode(hand_tpdo.error),
            temperature=hand_tpdo.temperature,
        )

    def get_tactile_data(self) -> dict:
        """Retrieve tactile sensor data from TPDO.

        Returns:
            Dictionary mapping TactileSensorId to TactileInfo.

        Raises:
            CommunicationError: If the received data is shorter than expected.
        """
        data = self._client.recv_data()
        if len(data) < self._expected_tpdo_size:
            raise CommunicationError(
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
            True on success, False on failure.
        """
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x01')
            result = self._client.sdo_read(0x2004, 0x03)
            return result == b'\x00'
        except Exception:
            return False

    def close_tactile(self) -> bool:
        """Disable the tactile sensors.

        Returns:
            True on success, False on failure.
        """
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x02')
            result = self._client.sdo_read(0x2004, 0x03)
            return result == b'\x00'
        except Exception:
            return False

    def zero_tactile(self) -> bool:
        """Zero-calibrate the tactile sensors.

        Returns:
            True on success, False on failure.
        """
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x04')
            result = self._client.sdo_read(0x2004, 0x03)
            return result == b'\x00'
        except Exception:
            return False

    # ===== Device operations =====

    def clear_fault(self) -> bool:
        """Clear device faults.

        Returns:
            True on success, False on failure.
        """
        try:
            self._client.sdo_write(0x2002, 0x01, b'\x01')
            logger.info("Fault cleared")
            return True
        except Exception:
            return False

    def init_joint(self) -> bool:
        """Initialize joint positions.

        Returns:
            True on success, False on failure.
        """
        try:
            self._client.sdo_write(0x2003, 0x01, b'\x01')
            logger.info("Joint initialization completed")
            return True
        except Exception:
            return False

    def get_device_name(self) -> str:
        """Retrieve the device name via SDO."""
        return self._client.sdo_read(0x1008, 0x00).decode("utf-8")

    def get_hardware_version(self) -> str:
        """Retrieve the hardware version via SDO."""
        return self._client.sdo_read(0x1009, 0x00).decode("utf-8")

    def get_firmware_version(self) -> str:
        """Retrieve the firmware version via SDO."""
        return self._client.sdo_read(0x100A, 0x00).decode("utf-8")

    def get_serial_number(self) -> int:
        """Retrieve the product serial number via SDO."""
        return int.from_bytes(self._client.sdo_read(0x1018, 0x04), byteorder="little")

    def get_motor_driver_version(self) -> tuple:
        """Retrieve the motor driver version via SDO."""
        return (
            int.from_bytes(self._client.sdo_read(0x2007, 0x01), byteorder="little"),
            int.from_bytes(self._client.sdo_read(0x2007, 0x02), byteorder="little"),
            int.from_bytes(self._client.sdo_read(0x2007, 0x03), byteorder="little"),
        )

    def get_hand_type(self) -> int:
        """Retrieve the hand type via SDO.

        Returns:
            0 for unknown, 1 for left hand, 2 for right hand.
        """
        try:
            return int.from_bytes(self._client.sdo_read(0x2001, 0x00), byteorder="little")
        except Exception:
            return 0

    # ===== Subscription =====

    def subscribe(self, callback, *args, **kwargs) -> int:
        """Subscribe to device data updates.

        Internally parses raw bytes into a Tpdo before invoking the callback.

        Args:
            callback: Callable invoked with a Tpdo instance.

        Returns:
            Subscription ID.
        """

        def wrapper(data_bytes, *args, **kwargs):
            tpdo = Tpdo.from_bytes(data_bytes, self._config)
            callback(tpdo, *args, **kwargs)

        return self._sub_manager.subscribe(wrapper, *args, **kwargs)

    def unsubscribe(self, sub_id) -> bool:
        """Remove a previously registered subscription.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription existed and was removed.
        """
        return self._sub_manager.unsubscribe(sub_id)
