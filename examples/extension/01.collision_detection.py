"""
Online collision detection example

Demonstrates how to decouple collision detection from joint motion:
1. Call check_collision() to detect target pose
2. Check result and print angle comparison
3. Call move_joints() to execute motion (or choose not to move when collision detected)
"""

import logging
import time

from ghand import (
    ProductType,
    CommType,
    GHand,
    JointCommand,
    JointId,
    configure_logging,
    joints_to_nparray,
    nparray_to_joints,
)
from ghand.types import GHandError

# Configure logging
configure_logging(level=logging.INFO)

# Default speed and torque
DEFAULT_SPEED = 100
DEFAULT_TORQUE = 100


def main():
    print("===== GHand SDK - Online Collision Detection Demo =====\n")

    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)

    try:
        print("Connecting to device...")
        connected = hand.open("auto")

        if not connected:
            print("[ERROR] Device connection failed")
            return

        print("[OK] Device connected successfully\n")

        # Set safety margin
        hand.set_safety_margin(1)
        print("[OK] Safety margin set to 0.3mm\n")

        # Test: attempt pose that may cause collision
        print("--- Test: Detect collision and avoid ---")
        target_joints = [
            JointCommand(
                id=JointId.THUMB_PIP,
                angle=66,
                speed=DEFAULT_SPEED,
                torque=DEFAULT_TORQUE,
            ),
            JointCommand(
                id=JointId.THUMB_SWING,
                angle=52,
                speed=DEFAULT_SPEED,
                torque=DEFAULT_TORQUE,
            ),
            JointCommand(
                id=JointId.THUMB_ROTATION,
                angle=-10,
                speed=DEFAULT_SPEED,
                torque=DEFAULT_TORQUE,
            ),
            JointCommand(
                id=JointId.FF_PIP,
                angle=70,
                speed=DEFAULT_SPEED,
                torque=DEFAULT_TORQUE,
            ),
            JointCommand(
                id=JointId.FF_MCP,
                angle=70,
                speed=DEFAULT_SPEED,
                torque=DEFAULT_TORQUE,
            ),
        ]

        # Step 1: Perform collision detection (without executing motion)
        result = hand.check_collision(target_joints)

        if result.has_collision:
            print("Collision detected!")
            collision_info = " <-> ".join(result.collision_pairs or ["unknown"])
            print(f"Collision pairs: {collision_info}\n")

            # Print comparison of target and safe angles
            target_angles = joints_to_nparray(target_joints, hand.get_joints())
            print("=== Collision Detection - Angle Comparison (unit: degrees) ===")
            print("-" * 70)
            print(f"{'Joint Name':<18} {'Target Angle':<12} {'Safe Angle':<12}")
            print("-" * 70)
            for i in range(18):
                if JointId(i) in (
                        JointId.THUMB_DIP,
                        JointId.FF_DIP,
                        JointId.MF_DIP,
                        JointId.RF_DIP,
                        JointId.LF_DIP,
                ):
                    continue
                joint_name = JointId(i).name
                target_deg = target_angles[i]
                safe_deg = result.safe_angles[i]
                print(f"{joint_name:<25} {target_deg:<12.2f} {safe_deg:<12.2f}")
            print("-" * 70)
            print()

            # Step 2: Use safe angles for motion
            safe_joints = nparray_to_joints(
                result.safe_angles,
                speed=DEFAULT_SPEED,
                torque=DEFAULT_TORQUE,
            )
            print("Executing motion with safe angles...")
            success = hand.move_joints(safe_joints)
        else:
            print("No collision detected, using target angles directly.")
            success = hand.move_joints(target_joints)

        if success:
            time.sleep(2)

        # Get current joint states and print
        current_joints = hand.get_joints()
        print(f"Current angle: Thumb PIP={current_joints[JointId.THUMB_PIP.value].angle:.1f}°")
        print(f"Current angle: Thumb SWING={current_joints[JointId.THUMB_SWING.value].angle:.1f}°")
        print(
            f"Current angle: Thumb ROTATION={current_joints[JointId.THUMB_ROTATION.value].angle:.1f}°"
        )
        print(f"Current angle: Index PIP={current_joints[JointId.FF_PIP.value].angle:.1f}°")
        print(f"Current angle: Index MCP={current_joints[JointId.FF_MCP.value].angle:.1f}°")

        print("\n===== Demo complete =====")

    except GHandError as e:
        print(f"\n[ERROR] Error: {type(e).__name__}: {e}")

    finally:
        hand.close()
        print("\nDevice disconnected")


if __name__ == "__main__":
    main()
