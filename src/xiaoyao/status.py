from enum import IntEnum

class RobotStatus(IntEnum):
    """机器人状态枚举"""
    IDLE = 0
    RUNNING = 1
    STOPPED = 2
    DISABLED = 3
    ENABLED = 4
    CALIBRATING = 5
    STANDBY = 6
    LOW_POWER = 7
    ERROR = 100
    UNKNOWN = 999