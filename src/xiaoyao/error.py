from enum import IntEnum


class State(IntEnum):
    STOPPED = 0  # 停止
    RUNNING = 1  # 运行中
    ABNORMAL_RUNNING = 2  # 异常运行
    PROTECTIVE_STOPED = 3  # 保护性停止


class ErrorCode(IntEnum):
    NORMAL = 0  # 正常
    # Motor
    MOTOR_HARDWARE_OVERCURRENT = 1  # 电机硬件过流
    MOTOR_SOFTWARE_OVERCURRENT = 2  # 电机软件过流
    MOTOR_BUS_OVERCURRENT = 3  # 电机母线过流
    MOTOR_PHASE_LOST = 4  # 电机缺相
    MOTOR_STALLED = 5  # 电机堵转
    MOTOR_DRIVER_OVERTEMP = 6  # 电机驱动芯片过温
    MOTOR_COMM_ERROR = 7  # 电机通信错误
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
