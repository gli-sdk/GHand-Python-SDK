# common.py
# (请替换您现有的 common.py 内容)

from enum import IntEnum

# --- RobotStatus (通用运行状态枚举) ---
class RobotStatus(IntEnum):
    """机器人或模块的通用运行状态枚举。"""
    IDLE = 0            # 空闲状态，准备接收指令
    RUNNING = 1         # 正在执行任务或运动中
    STOPPED = 2         # 已停止运动或任务
    DISABLED = 3        # 功能被禁用，不响应指令（例如电机禁用）
    ENABLED = 4         # 功能已启用，可响应指令（例如电机启用）
    CALIBRATING = 5     # 正在执行校准或初始化过程
    STANDBY = 6         # 待机模式，通常为低功耗状态
    LOW_POWER = 7       # 低功功耗模式
    ERROR = 100         # 发生一般性错误，需要检查具体错误码
    UNKNOWN = 999       # 未知状态或无法获取当前状态

# --- RobotError (错误类型枚举) ---
class RobotError(IntEnum):
    """机器人或模块操作中可能遇到的错误类型枚举。"""
    NO_ERROR = 0                    # 操作成功，无错误
    GENERAL_ERROR = 1               # 一般性或未分类的错误
    INVALID_PARAMETER = 2           # 函数参数无效或超出指定范围
    COMMUNICATION_FAILURE = 3       # 与设备通讯故障或连接中断
    TIMEOUT = 4                     # 操作在指定时间内未能完成
    HARDWARE_FAILURE = 5            # 硬件故障，例如电机损坏、传感器故障
    NOT_SUPPORTED = 6               # 请求的操作或功能当前设备不支持
    BUSY = 7                        # 设备当前正忙于其他任务，无法执行当前操作
    NOT_INITIALIZED = 8             # 设备或模块未初始化或未校准
    PROTECTION_TRIGGERED = 9        # 保护机制被触发（如过温、过流、碰撞）
    INVALID_STATE = 10              # 当前设备状态下无法执行此操作
    ACTION_FAILED = 11              # 动作指令已发送，但实际动作未能成功完成

# --- GestureType (预设手势类型枚举) ---
class GestureType(IntEnum):
    """预设手势类型枚举"""
    OPEN_ALL_FINGERS = 0   # 将手部所有手指张开到最大位置
    OPPOSE_FINGERS = 1     # 将手部手指执行对指动作
    FIST = 2               # 握拳姿态
    POINT_FINGER = 3       # 食指指向姿态
    V_SIGN = 4             # 比V字手势
    GRIP_SIX = 6           # 将手部调整为预设的“6”姿态
    OK_SIGN = 5            # 比OK手势 (新增)

# --- JointInfo (关节信息类) ---
class JointInfo:
    """关节信息类，用于封装单个关节的完整信息(角度、速度、力矩、状态)的类。"""
    def __init__(self):
        self.joint_id: int = 0
        self.angle: float = 0.0
        self.speed: float = 0.0
        self.torque: float = 0.0
        self.status: int = 0 # 参考 RobotStatus 枚举