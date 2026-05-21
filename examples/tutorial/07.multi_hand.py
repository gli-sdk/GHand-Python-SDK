"""
Example: Multi-GHand Controller (supports any number)

This example shows how to create a generic controller class that automatically
connects to any number of dexterous hands and provides a simple interface
to control them.
"""

import logging
import time
from typing import Dict, List, Optional

from ghand import ProductType, configure_logging
from ghand.ghand import CommType, GHand, JointCommand, JointId
from ghand.types import GHandError

# Configure SDK logging
configure_logging(level=logging.INFO)


class MultiGHandController:
    """
    Multi-GHand Controller

    Automatically connects to any number of dexterous hands and provides
    convenient interfaces to control them.
    Supports auto-discovery or manual network interface specification.

    Usage example:
        # Method 1: Auto-discover all available interfaces and connect
        controller = MultiGHandController(auto_search=True)

        # Method 2: Manually specify network interfaces
        controller = MultiGHandController(
            interfaces=["\\Device\\NPF_{...}", "\\Device\\NPF_{...}"]
        )

        # Initialize (automatically connects all found devices)
        if controller.initialize():
            # Get info for all hands
            all_hands = controller.get_all_hands()

            # Control a specific hand
            controller.move_hand("hand_0", joints)

            # Or control all hands simultaneously
            controller.move_all_hands([joints0, joints1, ...])

        # Close all connections when done
        controller.close_all()
    """

    def __init__(self, interfaces: List[str] = None, auto_search: bool = False):
        """
        Initialize multi-GHand controller

        Args:
            interfaces: List of network interface IDs (optional)
            auto_search: Whether to auto-discover all available network interfaces (recommended)
        """
        self.auto_search = auto_search
        self.interfaces = interfaces or []

        # Store info for all hands
        self.hands: Dict[str, GHand] = {}
        self.hand_info: Dict[str, dict] = {}
        self.interface_to_hand: Dict[str, str] = {}  # interface -> hand_name

        # Connection state
        self._initialized = False

        # If auto-search is enabled, get all available interfaces
        if auto_search:
            temp_hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
            self.interfaces = temp_hand.get_connectable_devices()
            del temp_hand
            print(f"Auto-discovered {len(self.interfaces)} connectable devices")

    def _detect_connected_interfaces(self, available_interfaces: List[str]) -> List[str]:
        """
        Detect which interfaces are actually connected to devices

        Args:
            available_interfaces: List of all available network interfaces

        Returns:
            list: List of interfaces with actual device connections
        """
        connected_interfaces = []

        print("\nDetecting which interfaces have devices connected...")
        for i, iface in enumerate(available_interfaces):
            print(f"  Testing interface {i}: {iface}")

            # Attempt connection
            test_hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
            try:
                if test_hand.open(iface):
                    # Device detected successfully
                    connected_interfaces.append(iface)
                    print(f"    ✓ Device detected")
                    test_hand.close()
                else:
                    print(f"    ✗ Connection failed")
            except GHandError as e:
                print(f"    ✗ Error: {e}")
            finally:
                del test_hand

        print(f"\nDetected {len(connected_interfaces)} devices in total")
        return connected_interfaces

    def initialize(self) -> bool:
        """
        Automatically connect all devices and read device info

        Returns:
            bool: True if at least one device connected successfully, False otherwise
        """
        print("\n=== Initializing Multi-GHand Controller ===")

        if not self.interfaces:
            print("No available network interfaces")
            return False

        # Step 1: Connect all devices
        print(f"\nStep 1: Connecting {len(self.interfaces)} devices...")
        connected_hands = []
        connected_interfaces = []

        for i, interface in enumerate(self.interfaces):
            print(f"  Connecting device {i}: {interface}")

            hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
            try:
                if hand.open(interface):
                    hand_name = f"hand_{i}"
                    self.hands[hand_name] = hand
                    self.interface_to_hand[interface] = hand_name
                    connected_hands.append((hand_name, hand))
                    connected_interfaces.append(interface)
                    print(f"    ✓ Connection successful")
                else:
                    print(f"    ✗ Connection failed")
                    del hand
            except GHandError as e:
                print(f"    ✗ Error: {e}")
                del hand

        if not connected_hands:
            print("No devices connected successfully")
            return False

        print(f"\n✓ Successfully connected {len(connected_hands)} devices")

        # Step 2: Get info for all devices
        print(f"\nStep 2: Getting info for all devices...")
        for hand_name, hand in connected_hands:
            try:
                hand_info = {
                    'name': hand.get_device_name(),
                    'hardware_version': hand.get_hardware_version(),
                    'firmware_version': hand.get_firmware_version(),
                    'serial_number': hand.get_serial_number(),
                    'hand_type': hand.get_hand_type().value,
                    'interface': self.interface_to_hand.get(hand_name, ''),
                }
                self.hand_info[hand_name] = hand_info

                print(f"  {hand_name}: {hand_info['name']} "
                      f"({hand_info['hand_type']}, "
                      f"SN: {hand_info['serial_number']}, "
                      f"FW: {hand_info['firmware_version']}, "
                      f"HW: {hand_info['hardware_version']})")
            except GHandError as e:
                print(f"  Failed to get info for {hand_name}: {e}")

        self._initialized = True
        print(f"\n✓ Initialization complete")
        return True

    def get_hand_names(self) -> List[str]:
        """
        Get names of all connected hands

        Returns:
            list: List of hand names
        """
        return list(self.hands.keys())

    def get_hand_count(self) -> int:
        """
        Get number of connected hands

        Returns:
            int: Number of hands
        """
        return len(self.hands)

    def get_hand_info(self, hand_name: str) -> Optional[dict]:
        """
        Get info for specified hand

        Args:
            hand_name: Hand name

        Returns:
            dict: Hand info dictionary, or None if not found
        """
        return self.hand_info.get(hand_name)

    def get_all_hands_info(self) -> Dict[str, dict]:
        """
        Get info for all hands

        Returns:
            dict: Keys are hand names, values are info dictionaries
        """
        return self.hand_info.copy()

    def move_hand(self, hand_name: str, joints: List[JointCommand]) -> bool:
        """
        Control specified hand

        Args:
            hand_name: Hand name
            joints: List of joint commands

        Returns:
            bool: True on success
        """
        if not self._initialized:
            print("Controller not initialized")
            return False

        if hand_name not in self.hands:
            print(f"Hand '{hand_name}' not found")
            return False

        hand = self.hands[hand_name]
        return hand.move_joints(joints)

    def move_all_hands(self, joints_list: List[List[JointCommand]]) -> bool:
        """
        Control all hands simultaneously

        Args:
            joints_list: List of joint command lists, each element corresponds to one hand

        Returns:
            bool: True if all succeeded
        """
        if not self._initialized:
            print("Controller not initialized")
            return False

        hand_names = self.get_hand_names()

        if len(joints_list) != len(hand_names):
            print(f"Joint count mismatch: {len(hand_names)} hands, "
                  f"but {len(joints_list)} joint command sets provided")
            return False

        success_all = True
        for hand_name, joints in zip(hand_names, joints_list):
            print(f"Controlling {hand_name}...")
            if not self.move_hand(hand_name, joints):
                success_all = False

        return success_all

    def get_hand_joints(self, hand_name: str) -> List[JointCommand]:
        """
        Get joint states for specified hand

        Args:
            hand_name: Hand name

        Returns:
            list: List of joint states
        """
        if not self._initialized:
            print("Controller not initialized")
            return []

        if hand_name not in self.hands:
            print(f"Hand '{hand_name}' not found")
            return []

        hand = self.hands[hand_name]
        return hand.get_joints()

    def get_all_joints(self) -> Dict[str, List[JointCommand]]:
        """
        Get joint states for all hands

        Returns:
            dict: Keys are hand names, values are joint state lists
        """
        if not self._initialized:
            print("Controller not initialized")
            return {}

        result = {}
        for hand_name in self.get_hand_names():
            result[hand_name] = self.get_hand_joints(hand_name)

        return result

    def close_all(self):
        """Close all connections"""
        if self._initialized:
            for hand_name, hand in self.hands.items():
                try:
                    hand.close()
                    print(f"Closed {hand_name}")
                except GHandError as e:
                    print(f"Failed to close {hand_name}: {e}")

            self.hands.clear()
            self.hand_info.clear()
            self._initialized = False
            print("All connections closed")

    def __enter__(self):
        """Support context manager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Auto-close on exit"""
        self.close_all()


def main():
    """Example: Using multi-GHand controller"""

    # Method 1: Auto-discover and connect all available devices (recommended)
    print("=== Method 1: Auto-search mode ===")
    controller = MultiGHandController(auto_search=True)

    # Method 2: Manually specify network interfaces
    # controller = MultiGHandController(
    #     interfaces=[
    #         "\\Device\\NPF_{FDC7358F-FC71-4446-8247-A53015F23C29}",
    #         "\\Device\\NPF_{D40A6875-C1A4-499A-BD51-273F04D08604}"
    #     ]
    # )

    # Automatically connect all devices
    if not controller.initialize():
        print("Initialization failed")
        return

    # Display device info
    print(f"\n=== Successfully connected {controller.get_hand_count()} dexterous hands ===")
    all_info = controller.get_all_hands_info()
    for hand_name, info in all_info.items():
        print(f"{hand_name}: {info['name']} "
              f"({info['hand_type']}, SN: {info['serial_number']})")

    # Example: Control each hand individually
    print("\n=== Example: Individual control ===")

    # Prepare joint commands
    test_joints = [
        JointCommand(id=JointId.THUMB_PIP, angle=30, speed=100, torque=100),
        JointCommand(id=JointId.FF_PIP, angle=45, speed=100, torque=100),
        JointCommand(id=JointId.FF_MCP, angle=30, speed=100, torque=100),
    ]

    # Control all hands
    for hand_name in controller.get_hand_names():
        print(f"Controlling {hand_name}...")
        if controller.move_hand(hand_name, test_joints):
            print(f"  ✓ Command sent successfully")
            time.sleep(1)

            # Read joint states
            joints = controller.get_hand_joints(hand_name)
            print(f"  Current joint count: {len(joints)}")

    # Example: Control all hands simultaneously
    print("\n=== Example: Simultaneous control ===")

    # Prepare reset commands
    reset_joints = [
        JointCommand(id=JointId.THUMB_PIP, angle=0, speed=100, torque=100),
        JointCommand(id=JointId.FF_PIP, angle=0, speed=100, torque=100),
        JointCommand(id=JointId.FF_MCP, angle=0, speed=100, torque=100),
    ]

    # Prepare commands for each hand
    all_joints = [reset_joints] * controller.get_hand_count()

    print("Controlling all hands simultaneously...")
    if controller.move_all_hands(all_joints):
        print("  ✓ All hand commands sent successfully")
        time.sleep(1)

    # Get joint states for all hands
    print("\n=== Joint States ===")
    all_joints_state = controller.get_all_joints()
    for hand_name, joints in all_joints_state.items():
        print(f"\n{hand_name}: {len(joints)} joints")
        for joint in joints:
            print(f"  {JointId(joint.id).name:<15}- angle: {joint.angle:.2f}°, "
                  f"speed: {joint.speed}, torque: {joint.torque}")

    print("\n=== Complete ===")

    # Close all connections
    controller.close_all()


if __name__ == "__main__":
    main()
