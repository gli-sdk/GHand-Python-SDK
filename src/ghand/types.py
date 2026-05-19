"""
GHand SDK 类型定义

所有枚举、数据类、异常类集中定义，避免循环导入。
"""
import enum
from dataclasses import dataclass, field
from typing import List, Optional


# ============================================================================
# 基础枚举
# ============================================================================

class JointId(enum.IntEnum):
    THUMB_DIP = 0
    THUMB_PIP = 1
    THUMB_MCP = 2
    THUMB_SWING = 3
    THUMB_ROTATION = 4
    FF_DIP = 5
    FF_PIP = 6
    FF_MCP = 7
    FF_SWING = 8
    MF_DIP = 9
    MF_PIP = 10
    MF_MCP = 11
    RF_DIP = 12
    RF_PIP = 13
    RF_MCP = 14
    LF_DIP = 15
    LF_PIP = 16
    LF_MCP = 17


class State(enum.IntEnum):
    STOPPED = 0
    RUNNING = 1
    ABNORMAL_RUNNING = 2
    PROTECTIVE_STOPPED = 3
    PROTECTIVE_STOPED = 3  # deprecated alias, kept for backward compatibility


class ErrorCode(enum.IntEnum):
    NORMAL = 0
    MOTOR_HARDWARE_OVERCURRENT = 1
    MOTOR_SOFTWARE_OVERCURRENT = 2
    MOTOR_BUS_OVERCURRENT = 3
    MOTOR_PHASE_LOST = 4
    MOTOR_STALLED = 5
    MOTOR_DRIVER_OVERTEMP = 6
    MOTOR_COMM_ERROR = 7
    JOINT_CONFLICT = 11
    TIP_CONFLICT = 12
    LOW_TEMP = 21
    HIGH_TEMP = 22
    LOW_VOLTAGE = 23
    HIGH_VOLTAGE = 24
    TACTILE_ERROR = 31
    PARAM_ERROR = 101
    TIMEOUT = 102
    UNKNOWN_ERROR = 201


class HandType(enum.Enum):
    UNKNOWN = "unknown"
    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"


class CommType(enum.Enum):
    UNKNOWN = "unknown"
    ETHERCAT = "ethercat"
    CANFD = "canfd"
    RS485 = "rs485"


class CtrlMode(enum.Enum):
    POSITION = 0
    TORQUE = 1
    SPEED = 2


class TactileSensorId(enum.Enum):
    THUMB = 'thumb'
    FOREFINGER = 'forefinger'
    MIDDLE_FINGER = 'middle_finger'
    RING_FINGER = 'ring_finger'
    LITTLE_FINGER = 'little_finger'


class ProductType(enum.Enum):
    AUTO = "auto"
    G5 = "G5"


class GestureType(enum.Enum):
    OPEN_HAND = "open_hand"
    FIST = "fist"
    OK = "ok"
    THUMBS_UP = "thumbs_up"
    SIX_SIGN = "six_sign"


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class TactileRegionConfig:
    name: str
    count: int


@dataclass
class ProductConfig:
    name: str = ""
    model: str = ""
    valid_joints: list[JointId] = field(default_factory=list)
    joint_limits: dict[JointId, tuple[float, float]] = field(default_factory=dict)
    has_tactile: bool = False
    tactile_regions: list[TactileRegionConfig] = field(default_factory=list)


@dataclass
class FaultInfo:
    error_code: ErrorCode
    state: State
    message: str

    def __str__(self):
        return f"State: {self.state.name}, Error: {self.error_code.name} ({self.error_code.value}) - {self.message}"


@dataclass
class JointFaultInfo:
    joint_id: str
    state: State
    error_code: ErrorCode

    def __str__(self):
        return f"{self.joint_id}: State={self.state.name}, Error={self.error_code.name}"


@dataclass
class HandInfo:
    state: State = State.STOPPED
    error: ErrorCode = ErrorCode.NORMAL
    temp: int = 0


@dataclass
class Joint:
    id: int = JointId.THUMB_DIP
    angle: float = 0.0  # radians
    speed: int = 0
    torque: int = 0
    state: State = State.STOPPED
    error: ErrorCode = ErrorCode.NORMAL

    @staticmethod
    def create_joint_positions(joint_angles_dict, speed=100, torque=100):
        joints = []
        for joint_id, angle in joint_angles_dict.items():
            joints.append(Joint(id=joint_id, angle=angle, speed=speed, torque=torque))
        return joints


@dataclass
class TactileInfo:
    state: bool = False
    resultant_force: list[int] = None
    distributed_force: list[int] = None

    def __post_init__(self):
        if self.resultant_force is None:
            self.resultant_force = [0, 0, 0]
        if self.distributed_force is None:
            self.distributed_force = []

    def get_force_x(self) -> float:
        return self.resultant_force[0] if len(self.resultant_force) > 0 else 0

    def get_force_y(self) -> float:
        return self.resultant_force[1] if len(self.resultant_force) > 1 else 0

    def get_force_z(self) -> float:
        return self.resultant_force[2] if len(self.resultant_force) > 2 else 0

    def get_distributed_force(self) -> list[int]:
        return self.distributed_force

    def get_distributed_force_at(self, index: int) -> int:
        if 0 <= index < len(self.distributed_force):
            return self.distributed_force[index]
        return 0

    def get_state(self) -> bool:
        return self.state


# ============================================================================
# 异常类
# ============================================================================

# 错误消息映射
_ERROR_MESSAGES = {
    ErrorCode.MOTOR_HARDWARE_OVERCURRENT: "电机硬件过流",
    ErrorCode.MOTOR_SOFTWARE_OVERCURRENT: "电机软件过流",
    ErrorCode.MOTOR_BUS_OVERCURRENT: "电机母线过流",
    ErrorCode.MOTOR_PHASE_LOST: "电机缺相",
    ErrorCode.MOTOR_STALLED: "电机堵转",
    ErrorCode.MOTOR_DRIVER_OVERTEMP: "电机驱动芯片过温",
    ErrorCode.MOTOR_COMM_ERROR: "电机通信错误",
    ErrorCode.JOINT_CONFLICT: "关节冲突",
    ErrorCode.TIP_CONFLICT: "指尖冲突",
    ErrorCode.LOW_TEMP: "温度过低",
    ErrorCode.HIGH_TEMP: "温度过高",
    ErrorCode.LOW_VOLTAGE: "电压过低",
    ErrorCode.HIGH_VOLTAGE: "电压过高",
    ErrorCode.TACTILE_ERROR: "触觉传感器错误",
    ErrorCode.PARAM_ERROR: "参数错误",
    ErrorCode.TIMEOUT: "超时",
    ErrorCode.UNKNOWN_ERROR: "未知错误",
}

_STATE_MESSAGES = {
    State.PROTECTIVE_STOPPED: "设备进入保护性停止状态",
    State.ABNORMAL_RUNNING: "设备运行异常",
}


def get_fault_message(error_code: ErrorCode, state: Optional[State] = None, **context) -> str:
    if error_code != ErrorCode.NORMAL:
        base_msg = _ERROR_MESSAGES.get(error_code, f"未知错误: {error_code.name}")
    else:
        base_msg = "设备正常运行"

    if state and state in [State.PROTECTIVE_STOPPED, State.ABNORMAL_RUNNING]:
        state_msg = _STATE_MESSAGES.get(state, f"异常状态: {state.name}")
        if error_code == ErrorCode.NORMAL:
            return f"{state_msg}，但错误码为0"
        else:
            return f"{state_msg}，{base_msg}"

    context_parts = []
    if 'temp' in context:
        context_parts.append(f"温度: {context['temp']}°C")
    if 'joint_id' in context:
        context_parts.append(f"关节: {context['joint_id']}")

    if context_parts:
        return f"{base_msg}（{', '.join(context_parts)}）"
    return base_msg


class GHandError(Exception):
    """GHand SDK 基础异常类"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message


class DeviceDisconnectedError(GHandError):
    def __init__(self, message: str, reason: Optional[str] = None):
        self.reason = reason
        super().__init__(message)

    def __str__(self):
        return self.message


class DeviceFaultError(GHandError):
    def __init__(self, message: str, fault_info: Optional[FaultInfo] = None):
        self.fault_info = fault_info
        super().__init__(message)

    def __str__(self):
        if self.fault_info:
            return f"{self.message} - {self.fault_info}"
        return self.message


class JointFaultError(GHandError):
    def __init__(self, message: str, faulty_joints: Optional[List[JointFaultInfo]] = None):
        self.faulty_joints: List[JointFaultInfo] = faulty_joints or []
        super().__init__(message)

    def __str__(self):
        if self.faulty_joints:
            joints_str = "\n  ".join(str(j) for j in self.faulty_joints)
            return f"{self.message}\n  故障关节:\n  {joints_str}"
        return self.message


class DataReceiveError(GHandError):
    def __init__(self, message: str, expected_length: Optional[int] = None, actual_length: Optional[int] = None):
        self.expected_length = expected_length
        self.actual_length = actual_length
        super().__init__(message)

    def __str__(self):
        if self.expected_length is not None and self.actual_length is not None:
            return f"{self.message} (期望: {self.expected_length} 字节, 实际: {self.actual_length} 字节)"
        return self.message
