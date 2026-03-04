from enum import IntEnum


class State(IntEnum):
    STOPPED = 0  # 停止
    RUNNING = 1  # 运行中
    ABNORMAL_RUNNING = 2  # 异常运行
    PROTECTIVE_STOP = 3  # 保护性停止


class ErrorCode(IntEnum):
    NORMAL = 0  # 正常
    # Motor
    HIGH_CURRENT = 1
    ENCODER_ERROR = 2
    # Finger
    JOINT_CONFLICT = 11
    TIP_CONFLICT = 12
    # HAND
    LOW_TEMP = 21
    HIGH_TEMP = 22
    LOW_VOLTAGE = 23
    HIGH_VOLTAGE = 24
    # Tactile sensor
    TACTILE_ERROR = 31
    # Data process
    PARAM_ERROR = 101
    TIMEOUT = 102
    # Others
    UNKNOWN_ERROR = 201
