import socket

UDP_IP = "192.168.1.19"
UDP_PORT = 8080


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

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

while True:
    data, addr = sock.recvfrom(32 * 1024)
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
        
        # 从192个数据中提取需要的数据（每6个为一组，取每组的第4和第5个数据）
        # 根据您的描述，数据顺序为:
        # RightHand, RightHandThumb1, RightHandThumb2, RightHandThumb3, RightHandIndex1, ...
        # LeftHand, LeftHandThumb1, LeftHandThumb2, LeftHandThumb3, LeftHandIndex1, ...
        # 其中我们只需要pip和mcp传感器的数据，即每根手指的第2和第3传感器的数据
        right_hand_data = []
        left_hand_data = []
        
        # 右手数据 (第2组到第16组)
        for i in range(1, 16, 3):  # 每根手指3个传感器，跳过手背传感器
            # 正确的顺序应该是：i是mcp，i+1是pip，i+2是dip
            mcp_group_index = i * 6
            pip_group_index = (i + 1) * 6
            
            if pip_group_index + 5 < len(numeric_data) and mcp_group_index + 5 < len(numeric_data):
                # 提取pip传感器的第5和第4个数据 (索引4和3)
                pip_bend = numeric_data[pip_group_index + 4]
                pip_sway = numeric_data[pip_group_index + 3]
                
                # 提取mcp传感器的第5和第4个数据 (索引4和3)
                mcp_bend = numeric_data[mcp_group_index + 4]
                mcp_sway = numeric_data[mcp_group_index + 3]
                
                right_hand_data.extend([mcp_bend, mcp_sway, pip_bend, pip_sway])
        
        # 左手数据 (第18组到第32组)
        for i in range(17, 32, 3):  # 每根手指3个传感器，跳过手背传感器
            # 正确的顺序应该是：i是mcp，i+1是pip，i+2是dip
            mcp_group_index = i * 6
            pip_group_index = (i + 1) * 6
            
            if pip_group_index + 5 < len(numeric_data) and mcp_group_index + 5 < len(numeric_data):
                # 提取pip传感器的第5和第4个数据 (索引4和3)
                pip_bend = numeric_data[pip_group_index + 4]
                pip_sway = numeric_data[pip_group_index + 3]
                
                # 提取mcp传感器的第5和第4个数据 (索引4和3)
                mcp_bend = numeric_data[mcp_group_index + 4]
                mcp_sway = numeric_data[mcp_group_index + 3]
                
                left_hand_data.extend([mcp_bend, mcp_sway, pip_bend, pip_sway])
        
        # 创建右手对象
        if len(right_hand_data) >= 20:  # 5个手指 * 4个数据
            right_thumb = Finger(right_hand_data[0], right_hand_data[1], right_hand_data[2], right_hand_data[3])
            right_index = Finger(right_hand_data[4], right_hand_data[5], right_hand_data[6], right_hand_data[7])
            right_middle = Finger(right_hand_data[8], right_hand_data[9], right_hand_data[10], right_hand_data[11])
            right_ring = Finger(right_hand_data[12], right_hand_data[13], right_hand_data[14], right_hand_data[15])
            right_pinky = Finger(right_hand_data[16], right_hand_data[17], right_hand_data[18], right_hand_data[19])
            right_hand = Hand(right_thumb, right_index, right_middle, right_ring, right_pinky)
        
        # 创建左手对象
        if len(left_hand_data) >= 20:  # 5个手指 * 4个数据
            left_thumb = Finger(left_hand_data[0], left_hand_data[1], left_hand_data[2], left_hand_data[3])
            left_index = Finger(left_hand_data[4], left_hand_data[5], left_hand_data[6], left_hand_data[7])
            left_middle = Finger(left_hand_data[8], left_hand_data[9], left_hand_data[10], left_hand_data[11])
            left_ring = Finger(left_hand_data[12], left_hand_data[13], left_hand_data[14], left_hand_data[15])
            left_pinky = Finger(left_hand_data[16], left_hand_data[17], left_hand_data[18], left_hand_data[19])
            left_hand = Hand(left_thumb, left_index, left_middle, left_ring, left_pinky)
        
        # 显示提取后的数据
        print(f"Right hand: {right_hand_data}")
        print(f"Left hand: {left_hand_data}")
        print(f"Total data count: {len(numeric_data)} from {addr}")
    else:
        print(f"Received message: {data.decode()} from {addr}")
        