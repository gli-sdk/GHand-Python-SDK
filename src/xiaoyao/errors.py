from enum import IntEnum

class RobotError(IntEnum):
    """机器人错误枚举"""
    NO_ERROR = 0
    GENERAL_ERROR = 1
    INVALID_PARAMETER = 2
    COMMUNICATION_FAILURE = 3
    TIMEOUT = 4
    HARDWARE_FAILURE = 5
    NOT_SUPPORTED = 6
    BUSY = 7
    NOT_INITIALIZED = 8
    PROTECTION_TRIGGERED = 9
    INVALID_STATE = 10
    ACTION_FAILED = 11