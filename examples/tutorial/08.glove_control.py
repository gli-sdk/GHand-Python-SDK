import socket
import time
import math
from ghand.ghand import GHand, CommType, Joint, JointId

UDP_IP = "192.168.1.19"
UDP_PORT = 8080

# 定义大拇指类
class ThumbFinger:
    def __init__(self, mcp_bend, mcp_sway, mcp_roll, pip_bend, pip_sway, pip_roll, dip_bend, dip_sway, dip_roll):
        self.mcp_bend = mcp_bend
        self.mcp_sway = mcp_sway
        self.mcp_roll = mcp_roll
        self.pip_bend = pip_bend
        self.pip_sway = pip_sway
        self.pip_roll = pip_roll
        self.dip_bend = dip_bend
        self.dip_sway = dip_sway
        self.dip_roll = dip_roll

# 定义手指类
class Finger:
    def __init__(self, mcp_bend, mcp_sway, pip_bend, pip_sway):
        self.mcp_bend = mcp_bend
        self.mcp_sway = mcp_sway
        self.pip_bend = pip_bend
        self.pip_sway = pip_sway
# 定义手部类
class Hand:
    def __init__(self, thumb, index, middle, ring, pinky):
        self.thumb = thumb
        self.index = index
        self.middle = middle
        self.ring = ring
        self.pinky = pinky

def process_glove_data(data):
    """
    处理手套数据，返回左右手的手指数据
    
    Args:
        data: 原始数据字符串
        
    Returns:
        tuple: (left_hand, right_hand) 左右手对象,如果数据不足则返回None
    """
    
    # 将数据按逗号分隔
    data_items = data.decode().split(',')
    
    # 去除第一个数据，将剩余的数据转换为数值并存放在数组中
    if len(data_items) > 1:
        # 去除第一个数据项
        remaining_items = data_items[1:]
        
        # 将字符串转换为数值并存储在数组中
        numeric_data = []
        for item in remaining_items:
            try:
                # 尝试转换为浮点数
                numeric_value = float(item)
                numeric_data.append(numeric_value)
            except ValueError:
                # 如果转换失败，保持为字符串
                numeric_data.append(item)
        
        # 直接从numeric_data数组中提取需要的数据
        # 右手数据索引（基于每组6个数据）：
        right_hand_data = []
        if len(numeric_data) >= 192:  # 确保有足够的数据
            # 右手拇指 (组 1, 2, 3)
            right_hand_data.extend([
                numeric_data[10], numeric_data[9],  numeric_data[11],   # mcp bend, sway, roll (组1: 索引6-11)
                numeric_data[16], numeric_data[15], numeric_data[17],   # pip bend, sway, roll (组2: 索引12-17)
                 numeric_data[22], numeric_data[21],numeric_data[23]    # dip bend, sway, roll (组3: 索引18-23) 
            ])
            # 右手食指 (组 4, 5)
            right_hand_data.extend([
                numeric_data[28], numeric_data[27],  # mcp bend, sway (组4: 索引24-29)
                numeric_data[34], numeric_data[33]   # pip bend, sway (组5: 索引30-35)
            ])
            # 右手中指 (组 7, 8)
            right_hand_data.extend([
                numeric_data[46], numeric_data[45],  # mcp bend, sway (组7: 索引42-47)
                numeric_data[52], numeric_data[51]   # pip bend, sway (组8: 索引48-53)
            ])
            # 右手无名指 (组 10, 11)
            right_hand_data.extend([
                numeric_data[64], numeric_data[63],  # mcp bend, sway (组10: 索引60-65)
                numeric_data[70], numeric_data[69]   # pip bend, sway (组11: 索引66-71)
            ])
            # 右手小指 (组 13, 14)
            right_hand_data.extend([
                numeric_data[82], numeric_data[81],  # mcp bend, sway (组13: 索引78-83)
                numeric_data[88], numeric_data[87]   # pip bend, sway (组14: 索引84-89)
            ])

        # 左手数据索引：
        left_hand_data = []
        if len(numeric_data) >= 192:  # 确保有足够的数据
            # 左手拇指 (组 17, 18, 19)
            left_hand_data.extend([
                numeric_data[106], numeric_data[105], numeric_data[107],   # mcp bend, sway, roll (组17: 索引102-107)
                numeric_data[112], numeric_data[111], numeric_data[113],   # pip bend, sway, roll (组18: 索引108-113)
                numeric_data[118], numeric_data[117], numeric_data[119]    # dip bend, sway, roll (组19: 索引114-119) 
            ])
            # 左手食指 (组 20, 21)
            left_hand_data.extend([
                numeric_data[124], numeric_data[123],  # mcp bend, sway (组20: 索引120-125)
                numeric_data[130], numeric_data[129]   # pip bend, sway (组21: 索引126-131)
            ])
            # 左手中指 (组 23, 24)
            left_hand_data.extend([
                numeric_data[142], numeric_data[141],  # mcp bend, sway (组23: 索引138-143)
                numeric_data[148], numeric_data[147]   # pip bend, sway (组24: 索引144-149)
            ])
            # 左手无名指 (组 26, 27)
            left_hand_data.extend([
                numeric_data[160], numeric_data[159],  # mcp bend, sway (组26: 索引156-161)
                numeric_data[166], numeric_data[165]   # pip bend, sway (组27: 索引162-167)
            ])
            # 左手小指 (组 29, 30)
            left_hand_data.extend([
                numeric_data[178], numeric_data[177],  # mcp bend, sway (组29: 索引174-179)
                numeric_data[184], numeric_data[183]   # pip bend, sway (组30: 索引180-185)
            ])

        # 创建右手对象
        right_hand = None
        if len(right_hand_data) >= 25:  # 大拇指9个数据 + 4个手指 * 4个数据
            right_thumb = ThumbFinger(right_hand_data[0], right_hand_data[1], right_hand_data[2], right_hand_data[3], right_hand_data[4], right_hand_data[5], right_hand_data[6], right_hand_data[7], right_hand_data[8])
            right_index = Finger(right_hand_data[9], right_hand_data[10], right_hand_data[11], right_hand_data[12])
            right_middle = Finger(right_hand_data[13], right_hand_data[14], right_hand_data[15], right_hand_data[16])
            right_ring = Finger(right_hand_data[17], right_hand_data[18], right_hand_data[19], right_hand_data[20])
            right_pinky = Finger(right_hand_data[21], right_hand_data[22], right_hand_data[23], right_hand_data[24])
            right_hand = Hand(right_thumb, right_index, right_middle, right_ring, right_pinky)
        
        # 创建左手对象
        left_hand = None
        if len(left_hand_data) >= 25:  # 5个手指 * 4个数据
            left_thumb = ThumbFinger(left_hand_data[0], left_hand_data[1], left_hand_data[2], left_hand_data[3], left_hand_data[4], left_hand_data[5], left_hand_data[6], left_hand_data[7], left_hand_data[8])
            left_index = Finger(left_hand_data[9], left_hand_data[10], left_hand_data[11], left_hand_data[12])
            left_middle = Finger(left_hand_data[13], left_hand_data[14], left_hand_data[15], left_hand_data[16])
            left_ring = Finger(left_hand_data[17], left_hand_data[18], left_hand_data[19], left_hand_data[20])
            left_pinky = Finger(left_hand_data[21], left_hand_data[22], left_hand_data[23], left_hand_data[24])
            left_hand = Hand(left_thumb, left_index, left_middle, left_ring, left_pinky)
        
        return left_hand, right_hand
    else:
        return None, None
    
def clip_angle_radians(value, min_angle, max_angle):
    """
    Clipping算法函数:将角度值限制在指定范围内并以弧度返回
    
    Args:
        value: 输入角度值（度）
        min_angle: 最小角度值（度）
        max_angle: 最大角度值（度）
        
    Returns:
        被限制在[min_angle, max_angle]范围内的角度值（弧度）
    """
    return math.radians(max(min_angle, min(value, max_angle)))

def main():
    """
    主函数，负责接收数据并处理显示
    """
    # 创建EtherCAT连接
    hand = GHand()
    connected = hand.open(CommType.ETHERCAT,  "auto")
    if not connected:
        print("connect failed")
        return
    print("连接到灵巧手成功!")

    # 创建socket连接
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    
    print(f"正在监听 {UDP_IP}:{UDP_PORT} 上的数据...")

    # 设置定时处理数据
    last_process_time = time.time()
    process_interval = 0.02  # 处理一次数据
    
    # 主循环
    while True:
        data, addr = sock.recvfrom(32 * 1024)
        
        # 检查是否需要处理数据
        current_time = time.time()
        if current_time - last_process_time >= process_interval:
            left_hand, right_hand = process_glove_data(data)
            print(f"thumb mcp bend sway roll: {left_hand.thumb.mcp_bend:.2f}, {left_hand.thumb.mcp_sway:.2f}, {left_hand.thumb.mcp_roll:.2f}")
            
            if left_hand:
                joints = []
                # 食指关节
                speed = 100
                torque = 100
                joints.append(Joint(id=JointId.THUMB_PIP, 
                                   angle=clip_angle_radians(left_hand.thumb.pip_bend, 0, 75), speed=speed, torque=torque)) # pip弯曲：mcp传感器的坐标系下绕x轴旋转
                joints.append(Joint(id=JointId.THUMB_MCP, 
                                   angle=clip_angle_radians(left_hand.thumb.mcp_bend - 40, 0, 55), speed=speed, torque=torque)) # mcp弯曲：手背传感器坐标系下绕z轴旋转
                joints.append(Joint(id=JointId.THUMB_SWING, 
                                   angle=clip_angle_radians(-(left_hand.thumb.mcp_roll + left_hand.thumb.pip_roll + left_hand.thumb.dip_roll) - 85, 0, 90), 
                                   speed=speed, torque=90))    # mcp外展：手背传感器坐标系下，dip传感器绕y轴旋转
                joints.append(Joint(id=JointId.THUMB_ROTATION, 
                                   angle=clip_angle_radians(-left_hand.thumb.dip_sway, -30, 60), 
                                   speed=speed, torque=90))    # mcp旋转：在mcp传感器坐标系下，dip传感器绕z轴旋转
                joints.append(Joint(id=JointId.FF_PIP, 
                                   angle=clip_angle_radians(left_hand.index.pip_bend, 0, 75), speed=speed, torque=torque))
                joints.append(Joint(id=JointId.FF_MCP, 
                                   angle=clip_angle_radians(left_hand.index.mcp_bend, 0, 70), speed=speed, torque=torque))
                joints.append(Joint(id=JointId.FF_SWING, 
                                   angle=clip_angle_radians(left_hand.index.mcp_sway + left_hand.index.pip_sway, -15, 15), speed=speed, torque=torque))
                joints.append(Joint(id=JointId.MF_PIP, 
                                   angle=clip_angle_radians(left_hand.middle.pip_bend, 0, 75), speed=speed, torque=torque))
                joints.append(Joint(id=JointId.MF_MCP, 
                                   angle=clip_angle_radians(left_hand.middle.mcp_bend, 0, 70), speed=speed, torque=torque))
                joints.append(Joint(id=JointId.RF_PIP, 
                                   angle=clip_angle_radians(left_hand.ring.pip_bend, 0, 75), speed=speed, torque=torque))
                joints.append(Joint(id=JointId.RF_MCP, 
                                   angle=clip_angle_radians(left_hand.ring.mcp_bend, 0, 70), speed=speed, torque=torque))
                joints.append(Joint(id=JointId.LF_PIP, 
                                   angle=clip_angle_radians(left_hand.pinky.pip_bend, 0, 75), speed=speed, torque=torque))
                joints.append(Joint(id=JointId.LF_MCP, 
                                   angle=clip_angle_radians(left_hand.pinky.mcp_bend, 0, 70), speed=speed, torque=torque)) 
    
                hand.move_joints(joints)
                hand.get_joints()
            
            # 更新上次处理时间
            last_process_time = current_time



if __name__ == "__main__":
    main()