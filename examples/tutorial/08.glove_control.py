import socket
import time

from ghand.ghand import CommType, GHand, JointCommand, JointId
from ghand import ProductType

UDP_IP = "192.168.1.19"
UDP_PORT = 8080


# Define thumb class
class ThumbFinger:

    def __init__(
        self,
        mcp_bend,
        mcp_sway,
        mcp_roll,
        pip_bend,
        pip_sway,
        pip_roll,
        dip_bend,
        dip_sway,
        dip_roll,
    ):
        self.mcp_bend = mcp_bend
        self.mcp_sway = mcp_sway
        self.mcp_roll = mcp_roll
        self.pip_bend = pip_bend
        self.pip_sway = pip_sway
        self.pip_roll = pip_roll
        self.dip_bend = dip_bend
        self.dip_sway = dip_sway
        self.dip_roll = dip_roll


# Define finger class
class Finger:

    def __init__(self, mcp_bend, mcp_sway, pip_bend, pip_sway):
        self.mcp_bend = mcp_bend
        self.mcp_sway = mcp_sway
        self.pip_bend = pip_bend
        self.pip_sway = pip_sway


# Define hand class
class Hand:

    def __init__(self, thumb, index, middle, ring, pinky):
        self.thumb = thumb
        self.index = index
        self.middle = middle
        self.ring = ring
        self.pinky = pinky


def process_glove_data(data):
    """
    Process glove data and return finger data for left and right hands

    Args:
        data: Raw data string

    Returns:
        tuple: (left_hand, right_hand) hand objects, or None if insufficient data
    """

    # Split data by comma
    data_items = data.decode().split(',')

    # Remove first item, convert remaining data to numeric values and store in array
    if len(data_items) > 1:
        # Remove first data item
        remaining_items = data_items[1:]

        # Convert strings to numeric values and store in array
        numeric_data = []
        for item in remaining_items:
            try:
                # Try converting to float
                numeric_value = float(item)
                numeric_data.append(numeric_value)
            except ValueError:
                # If conversion fails, keep as string
                numeric_data.append(item)

        # Extract required data directly from numeric_data array
        # Right hand data indices (based on groups of 6):
        right_hand_data = []
        if len(numeric_data) >= 192:  # Ensure sufficient data
            # Right thumb (groups 1, 2, 3)
            right_hand_data.extend([
                numeric_data[10],
                numeric_data[9],
                numeric_data[11],  # mcp bend, sway, roll (group1: indices 6-11)
                numeric_data[16],
                numeric_data[15],
                numeric_data[17],  # pip bend, sway, roll (group2: indices 12-17)
                numeric_data[22],
                numeric_data[21],
                numeric_data[23],  # dip bend, sway, roll (group3: indices 18-23)
            ])
            # Right index finger (groups 4, 5)
            right_hand_data.extend([
                numeric_data[28],
                numeric_data[27],  # mcp bend, sway (group4: indices 24-29)
                numeric_data[34],
                numeric_data[33],  # pip bend, sway (group5: indices 30-35)
            ])
            # Right middle finger (groups 7, 8)
            right_hand_data.extend([
                numeric_data[46],
                numeric_data[45],  # mcp bend, sway (group7: indices 42-47)
                numeric_data[52],
                numeric_data[51],  # pip bend, sway (group8: indices 48-53)
            ])
            # Right ring finger (groups 10, 11)
            right_hand_data.extend([
                numeric_data[64],
                numeric_data[63],  # mcp bend, sway (group10: indices 60-65)
                numeric_data[70],
                numeric_data[69],  # pip bend, sway (group11: indices 66-71)
            ])
            # Right little finger (groups 13, 14)
            right_hand_data.extend([
                numeric_data[82],
                numeric_data[81],  # mcp bend, sway (group13: indices 78-83)
                numeric_data[88],
                numeric_data[87],  # pip bend, sway (group14: indices 84-89)
            ])

        # Left hand data indices:
        left_hand_data = []
        if len(numeric_data) >= 192:  # Ensure sufficient data
            # Left thumb (groups 17, 18, 19)
            left_hand_data.extend([
                numeric_data[106],
                numeric_data[105],
                numeric_data[107],  # mcp bend, sway, roll (group17: indices 102-107)
                numeric_data[112],
                numeric_data[111],
                numeric_data[113],  # pip bend, sway, roll (group18: indices 108-113)
                numeric_data[118],
                numeric_data[117],
                numeric_data[119],  # dip bend, sway, roll (group19: indices 114-119)
            ])
            # Left index finger (groups 20, 21)
            left_hand_data.extend([
                numeric_data[124],
                numeric_data[123],  # mcp bend, sway (group20: indices 120-125)
                numeric_data[130],
                numeric_data[129],  # pip bend, sway (group21: indices 126-131)
            ])
            # Left middle finger (groups 23, 24)
            left_hand_data.extend([
                numeric_data[142],
                numeric_data[141],  # mcp bend, sway (group23: indices 138-143)
                numeric_data[148],
                numeric_data[147],  # pip bend, sway (group24: indices 144-149)
            ])
            # Left ring finger (groups 26, 27)
            left_hand_data.extend([
                numeric_data[160],
                numeric_data[159],  # mcp bend, sway (group26: indices 156-161)
                numeric_data[166],
                numeric_data[165],  # pip bend, sway (group27: indices 162-167)
            ])
            # Left little finger (groups 29, 30)
            left_hand_data.extend([
                numeric_data[178],
                numeric_data[177],  # mcp bend, sway (group29: indices 174-179)
                numeric_data[184],
                numeric_data[183],  # pip bend, sway (group30: indices 180-185)
            ])

        # Create right hand object
        right_hand = None
        if len(right_hand_data) >= 25:  # 9 data points for thumb + 4 fingers * 4 data points
            right_thumb = ThumbFinger(
                right_hand_data[0],
                right_hand_data[1],
                right_hand_data[2],
                right_hand_data[3],
                right_hand_data[4],
                right_hand_data[5],
                right_hand_data[6],
                right_hand_data[7],
                right_hand_data[8],
            )
            right_index = Finger(right_hand_data[9], right_hand_data[10], right_hand_data[11],
                                 right_hand_data[12])
            right_middle = Finger(right_hand_data[13], right_hand_data[14], right_hand_data[15],
                                  right_hand_data[16])
            right_ring = Finger(right_hand_data[17], right_hand_data[18], right_hand_data[19],
                                right_hand_data[20])
            right_pinky = Finger(right_hand_data[21], right_hand_data[22], right_hand_data[23],
                                 right_hand_data[24])
            right_hand = Hand(right_thumb, right_index, right_middle, right_ring, right_pinky)

        # Create left hand object
        left_hand = None
        if len(left_hand_data) >= 25:  # 5 fingers * 4 data points
            left_thumb = ThumbFinger(
                left_hand_data[0],
                left_hand_data[1],
                left_hand_data[2],
                left_hand_data[3],
                left_hand_data[4],
                left_hand_data[5],
                left_hand_data[6],
                left_hand_data[7],
                left_hand_data[8],
            )
            left_index = Finger(left_hand_data[9], left_hand_data[10], left_hand_data[11],
                                left_hand_data[12])
            left_middle = Finger(left_hand_data[13], left_hand_data[14], left_hand_data[15],
                                 left_hand_data[16])
            left_ring = Finger(left_hand_data[17], left_hand_data[18], left_hand_data[19],
                               left_hand_data[20])
            left_pinky = Finger(left_hand_data[21], left_hand_data[22], left_hand_data[23],
                                left_hand_data[24])
            left_hand = Hand(left_thumb, left_index, left_middle, left_ring, left_pinky)

        return left_hand, right_hand
    else:
        return None, None


def clip_angle_degrees(value, min_angle, max_angle):
    """
    Clipping function: restrict angle value within specified range

    Args:
        value: Input angle value (degrees)
        min_angle: Minimum angle value (degrees)
        max_angle: Maximum angle value (degrees)

    Returns:
        Angle value restricted to [min_angle, max_angle] range (degrees)
    """
    return max(min_angle, min(value, max_angle))


def main():
    """
    Main function, responsible for receiving data and processing display
    """
    # Create EtherCAT connection
    hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")
    if not connected:
        print("connect failed")
        return
    print("Connected to dexterous hand successfully!")

    # Create socket connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    print(f"Listening for data on {UDP_IP}:{UDP_PORT}...")

    # Set timed data processing
    last_process_time = time.time()
    process_interval = 0.02  # Process once

    # Main loop
    while True:
        data, addr = sock.recvfrom(32 * 1024)

        # Check if data needs processing
        current_time = time.time()
        if current_time - last_process_time >= process_interval:
            left_hand, right_hand = process_glove_data(data)
            print(
                f"thumb mcp bend sway roll: {left_hand.thumb.mcp_bend:.2f}, {left_hand.thumb.mcp_sway:.2f}, {left_hand.thumb.mcp_roll:.2f}"
            )

            if left_hand:
                joints = []
                # Index finger joints
                speed = 100
                torque = 100
                joints.append(
                    JointCommand(
                        id=JointId.THUMB_MCP,
                        angle=clip_angle_degrees(left_hand.thumb.pip_bend, 0, 75),
                        speed=speed,
                        torque=torque,
                    ))  # PIP bend: rotation around x-axis in MCP sensor coordinate system
                joints.append(
                    JointCommand(
                        id=JointId.THUMB_TMC_FE,
                        angle=clip_angle_degrees(left_hand.thumb.mcp_bend - 40, 0, 55),
                        speed=speed,
                        torque=torque,
                    ))  # MCP bend: rotation around z-axis in back of hand sensor coordinate system
                joints.append(
                    JointCommand(
                        id=JointId.THUMB_TMC_AA,
                        angle=clip_angle_degrees(
                            -(left_hand.thumb.mcp_roll + left_hand.thumb.pip_roll +
                              left_hand.thumb.dip_roll) - 85,
                            0,
                            90,
                        ),
                        speed=speed,
                        torque=90,
                    )
                )  # MCP abduction: in back of hand sensor coordinate system, DIP sensor rotates around y-axis
                joints.append(
                    JointCommand(
                        id=JointId.THUMB_TMC_PS,
                        angle=clip_angle_degrees(-left_hand.thumb.dip_sway, -30, 60),
                        speed=speed,
                        torque=90,
                    )
                )  # MCP rotation: in MCP sensor coordinate system, DIP sensor rotates around z-axis
                joints.append(
                    JointCommand(
                        id=JointId.FF_PIP,
                        angle=clip_angle_degrees(left_hand.index.pip_bend, 0, 75),
                        speed=speed,
                        torque=torque,
                    ))
                joints.append(
                    JointCommand(
                        id=JointId.FF_MCP,
                        angle=clip_angle_degrees(left_hand.index.mcp_bend, 0, 70),
                        speed=speed,
                        torque=torque,
                    ))
                joints.append(
                    JointCommand(
                        id=JointId.FF_MCP_AA,
                        angle=clip_angle_degrees(
                            left_hand.index.mcp_sway + left_hand.index.pip_sway, -15, 15),
                        speed=speed,
                        torque=torque,
                    ))
                joints.append(
                    JointCommand(
                        id=JointId.MF_PIP,
                        angle=clip_angle_degrees(left_hand.middle.pip_bend, 0, 75),
                        speed=speed,
                        torque=torque,
                    ))
                joints.append(
                    JointCommand(
                        id=JointId.MF_MCP,
                        angle=clip_angle_degrees(left_hand.middle.mcp_bend, 0, 70),
                        speed=speed,
                        torque=torque,
                    ))
                joints.append(
                    JointCommand(
                        id=JointId.RF_PIP,
                        angle=clip_angle_degrees(left_hand.ring.pip_bend, 0, 75),
                        speed=speed,
                        torque=torque,
                    ))
                joints.append(
                    JointCommand(
                        id=JointId.RF_MCP,
                        angle=clip_angle_degrees(left_hand.ring.mcp_bend, 0, 70),
                        speed=speed,
                        torque=torque,
                    ))
                joints.append(
                    JointCommand(
                        id=JointId.LF_PIP,
                        angle=clip_angle_degrees(left_hand.pinky.pip_bend, 0, 75),
                        speed=speed,
                        torque=torque,
                    ))
                joints.append(
                    JointCommand(
                        id=JointId.LF_MCP,
                        angle=clip_angle_degrees(left_hand.pinky.mcp_bend, 0, 70),
                        speed=speed,
                        torque=torque,
                    ))

                hand.move_joints(joints)
                hand.get_joints()

            # Update last processing time
            last_process_time = current_time


if __name__ == "__main__":
    main()
