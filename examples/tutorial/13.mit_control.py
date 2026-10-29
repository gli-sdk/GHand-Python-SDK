"""MIT grasp demo: soft-close, hold after tactile contact, release after 5 s."""

# Mode notes
# 1. Whole-hand MIT (mode=3) drives every active joint in MIT mode; the CUSTOM in-group
#    mode consistency rule does not apply. Joint loop_type only takes effect in CUSTOM;
#    other whole-hand modes default to closed loop.
# 2. Within an enabled hand, each joint's control_state decides execution: 0 disabled,
#    1 running, 2 stopped/holding. Whole-hand disabled takes priority, and a
#    communication loss leaves all joints idle.
# 3. MIT conventions: angle in degrees, velocity/current in %; kp=10-2000, kd=0-50,
#    kp>kd; suggested |velocity|<=5%, |current|<=20%; tune the gains for the actual
#    load. Velocity/current are targets (current is feed-forward), not limits; zero
#    feed-forward does not disable the motor.
# 4. move_joints() returning True only means the command was sent; check
#    get_hand_info() and get_joints() for actual execution.
# 5. close() only shuts down the communication link; it does not call stop() or
#    disable_hand(). Stop or release the hand explicitly before closing.

import logging
import time

from ghand import (
    CommType,
    GHand,
    HandControlMode,
    JointCommand,
    JointId,
    ProductType,
    configure_logging,
)


def main():
    configure_logging(level=logging.INFO)
    # For CAN FD / RS485, change comm_type and use the adapter port in open().
    hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)
    try:
        if not hand.open("auto"):
            print("Connection failed")
            return
        if not hand.tactile_open():
            print("Failed to open tactile sensors")
            return

        # Close with low kp/kd: the fingers stop on the object instead of crushing it.
        grasp = [
            JointCommand(id=JointId.THUMB_MCP, angle=66.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.THUMB_TMC_FE, angle=50.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.THUMB_TMC_AA, angle=90.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.THUMB_TMC_PS, angle=0.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.FF_PIP, angle=80.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.FF_MCP, angle=90.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.FF_MCP_AA, angle=0.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.MF_PIP, angle=90.0, velocity=7, current=0, kp=10, kd=0),
            JointCommand(id=JointId.MF_MCP, angle=90.0, velocity=7, current=0, kp=10, kd=0),
            JointCommand(id=JointId.RF_PIP, angle=90.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.RF_MCP, angle=90.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.LF_PIP, angle=74.0, velocity=5, current=0, kp=10, kd=0),
            JointCommand(id=JointId.LF_MCP, angle=90.0, velocity=5, current=0, kp=10, kd=0),
        ]
        if not hand.move_joints(grasp, hand_control_mode=HandControlMode.MIT):
            print("Failed to send MIT command")
            return

        # Watch tactile normal force; three touching fingers mean contact (up to 5 s).
        forces = {}
        for _ in range(100):
            forces = {
                finger: info.resultant_force[2] if info.resultant_force else 0.0
                for finger, info in hand.get_tactile_data().items()
            }
            if sum(fz >= 0.8 for fz in forces.values()) >= 3:
                break
            time.sleep(0.1)
        else:
            print("No contact detected, opening hand")
            hand.tactile_close()
            hand.disable_hand()
            return

        # Grasp: raise kp/kd a little and add feed-forward current for grip force.
        print(f"Contact detected: {forces}")
        for joint in grasp:
            joint.kp = 25
            joint.kd = 2
            joint.current = 5
        if not hand.move_joints(grasp, hand_control_mode=HandControlMode.MIT):
            print("Failed to send MIT command")
            return

        # Hold for 5 s, then release by driving the joints back to zero.
        time.sleep(5)
        for joint in grasp:
            joint.angle = 0.0
            joint.kp = 10
            joint.kd = 0
            joint.current = 0
        hand.move_joints(grasp, hand_control_mode=HandControlMode.MIT)
        time.sleep(2)
    except KeyboardInterrupt:
        print("Demo interrupted")
    finally:
        if hand.is_connected():
            hand.tactile_close()
            hand.disable_hand()
        hand.close()
        print("\n=== Demo ended, disconnected ===")


if __name__ == "__main__":
    main()
