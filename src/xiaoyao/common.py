from enum import Enum
class GestureType(Enum):
    OK = 1
    OPEN_ALL_FINGERS = 2
    FIST = 3
    THUMBS_UP = 4
    GRIP_SIX = 5

class ObjectDictionary:
    class Identity:
        """对象 0x1018: 设备身份信息"""
        INDEX = 0x1018
        SUB_VERSION_INFO = 0x03
        SUB_SERIAL_NUMBER = 0x04

    class ManufacturerCustom:
        """对象 0x2000: 制造商自定义区域"""
        INDEX = 0x2000
        SUB_HAND_ID = 0x01
        SUB_REBOOT = 0x02

    class Protection:
        """对象 0x2001: 保护功能相关"""
        INDEX = 0x2001
        SUB_PROTECTION_TEMP = 0x01

    class HandInfo:
        """对象 0x2012: 手部基本信息"""
        INDEX = 0x2012
        SUB_HAND_TYPE = 0x00

    class SystemControl:
        """对象 0x1011: 系统控制相关"""
        INDEX = 0x1011
        SUB_FACTORY_RESET = 0x01    
class HandError(Enum):
    NO_ERROR = 0
    COMMUNICATION_ERROR = 1
class HandState(Enum):
    NORMAL_STOP = 0
    NORMAL_RUNNING = 1
    PROTECTIVE_STOP = 2
    ABNORMAL_RUNNING = 3
    UNKNOWN = -1
    
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
