from enum import Enum
class GestureType(Enum):
    OK = 1
    OPEN_ALL_FINGERS = 2
    FIST = 3
    THUMBS_UP = 4
    GRIP_SIX = 5
class HandError(Enum):
    NO_ERROR = 0
    COMMUNICATION_ERROR = 1
class HandState(Enum):
    """
    根据硬件协议文档定义的设备运行状态。
    """
    IDLE = 0            # 对应协议中的 "0: 空闲"
    RUNNING = 1         # 对应协议中的 "1: 运行中"
    PROTECTIVE_STOP = 2 # 对应协议中的 "2: 保护性停止"
    ERROR = 3           # 对应协议中的 "3: 错误"
    UNKNOWN = -1        # 对应协议中的 "255: 未知"
class TipPose:
    """
    表示指尖的位姿信息，包括位置和姿态。
    """
    def __init__(self, x: float, y: float, z: float, roll: float, pitch: float, yaw: float):
        self.x = x
        self.y = y
        self.z = z
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw

class JointInfo:
    """
    用于存储单个关节完整信息的数据结构。
    """
    def __init__(self):
        self.joint_id: int = -1
        self.angle: float = 0.0
        self.speed: float = 0.0
        self.torque: float = 0.0
        self.status: int = -1 # 使用整数以匹配 HandState 枚举的 .value
    
    def __repr__(self):
        # 提供一个友好的打印输出格式，便于调试
        return (f"JointInfo(id={self.joint_id}, angle={self.angle:.2f}, "
                f"speed={self.speed:.2f}, torque={self.torque:.2f}, "
                f"status={self.status})")

JOINT_NAMES = [
    # 拇指 (Thumb)
    'Thumb_J1', 'Thumb_J2', 'Thumb_J3', 'Thumb_J4', 'Thumb_J5',
    # 食指 (Forefinger, FF)
    'FF_J1', 'FF_J2', 'FF_J3', 'FF_J4',
    # 中指 (Middle Finger, MF)
    'MF_J1', 'MF_J2', 'MF_J3', 'MF_J4',
    # 无名指 (Ring Finger, RF)
    'RF_J1', 'RF_J2', 'RF_J3', 'RF_J4',
    # 小指 (Little Finger, LF)
    'LF_J1', 'LF_J2', 'LF_J3', 'LF_J4',
]

# 关节总数
NUM_JOINTS = len(JOINT_NAMES) # 结果应该是 18

# --- 其他可能需要的公共定义 ---
# 例如可以把 HandState, HandError, GestureType 等枚举也放在这里
# from enum import IntEnum
# class HandState(IntEnum):
#     ...

# ... 文件的其他内容 ...    
