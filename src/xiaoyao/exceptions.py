"""
Xiaoyao SDK 自定义异常类

提供结构化的异常信息，包含详细的故障数据和错误码。
"""

from dataclasses import dataclass
from typing import List, Optional
from .error import ErrorCode, State


# 错误消息映射
_ERROR_MESSAGES = {
    # 电机错误
    ErrorCode.MOTOR_HARDWARE_OVERCURRENT: "电机硬件过流",
    ErrorCode.MOTOR_SOFTWARE_OVERCURRENT: "电机软件过流",
    ErrorCode.MOTOR_BUS_OVERCURRENT: "电机母线过流",
    ErrorCode.MOTOR_PHASE_LOST: "电机缺相",
    ErrorCode.MOTOR_STALLED: "电机堵转",
    ErrorCode.MOTOR_DRIVER_OVERTEMP: "电机驱动芯片过温",
    ErrorCode.MOTOR_COMM_ERROR: "电机通信错误",

    # 手指错误
    ErrorCode.JOINT_CONFLICT: "关节冲突",
    ErrorCode.TIP_CONFLICT: "指尖冲突",

    # 手部错误
    ErrorCode.LOW_TEMP: "温度过低",
    ErrorCode.HIGH_TEMP: "温度过高",
    ErrorCode.LOW_VOLTAGE: "电压过低",
    ErrorCode.HIGH_VOLTAGE: "电压过高",

    # 触觉传感器错误
    ErrorCode.TACTILE_ERROR: "触觉传感器错误",

    # 数据处理错误
    ErrorCode.PARAM_ERROR: "参数错误",
    ErrorCode.TIMEOUT: "超时",

    # 未知错误
    ErrorCode.UNKNOWN_ERROR: "未知错误",
}

_STATE_MESSAGES = {
    State.PROTECTIVE_STOPED: "设备进入保护性停止状态",
    State.ABNORMAL_RUNNING: "设备运行异常",
}


def get_fault_message(error_code: ErrorCode, state: Optional[State] = None, **context) -> str:
    """
    根据错误码和状态生成故障描述消息

    Args:
        error_code: 错误码枚举
        state: 状态枚举（可选）
        **context: 额外的上下文信息（如 temp、joint_id 等）

    Returns:
        str: 人类可读的故障描述
    """
    # 优先使用错误码消息
    if error_code != ErrorCode.NORMAL:
        base_msg = _ERROR_MESSAGES.get(error_code, f"未知错误: {error_code.name}")
    else:
        base_msg = "设备正常运行"

    # 如果有状态异常，添加状态信息
    if state and state in [State.PROTECTIVE_STOPED, State.ABNORMAL_RUNNING]:
        state_msg = _STATE_MESSAGES.get(state, f"异常状态: {state.name}")
        if error_code == ErrorCode.NORMAL:
            return f"{state_msg}，但错误码为0"
        else:
            return f"{state_msg}，{base_msg}"

    # 添加额外的上下文信息
    context_parts = []
    if 'temp' in context:
        context_parts.append(f"温度: {context['temp']}°C")
    if 'joint_id' in context:
        context_parts.append(f"关节: {context['joint_id']}")

    if context_parts:
        return f"{base_msg}（{', '.join(context_parts)}）"

    return base_msg


class XiaoyaoError(Exception):
    """Xiaoyao SDK 基础异常类"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message


class DeviceDisconnectedError(XiaoyaoError):
    """设备断连异常

    当设备通信失败、连接丢失或无法接收数据时抛出。
    """

    def __init__(self, message: str, reason: Optional[str] = None):
        """
        Args:
            message: 错误消息
            reason: 断连原因（可选）
        """
        self.reason = reason
        super().__init__(message)

    def __str__(self):
        return self.message


@dataclass
class FaultInfo:
    """设备故障信息

    包含设备的错误码、状态和描述信息。
    """
    error_code: ErrorCode
    state: State
    message: str

    def __str__(self):
        return f"State: {self.state.name}, Error: {self.error_code.name} ({self.error_code.value}) - {self.message}"


class DeviceFaultError(XiaoyaoError):
    """设备故障异常

    当设备处于故障状态时抛出，包括：
    - state = 2 (ABNORMAL_RUNNING)
    - state = 3 (PROTECTIVE_STOPED)
    - error != 0
    """

    def __init__(self, message: str, fault_info: Optional[FaultInfo] = None):
        """
        Args:
            message: 错误消息
            fault_info: 详细的故障信息
        """
        self.fault_info = fault_info
        super().__init__(message)

    def __str__(self):
        if self.fault_info:
            return f"{self.message} - {self.fault_info}"
        return self.message


@dataclass
class JointFaultInfo:
    """关节故障信息

    包含单个关节的故障详情。
    """
    joint_id: str
    state: State
    error_code: ErrorCode

    def __str__(self):
        return f"{self.joint_id}: State={self.state.name}, Error={self.error_code.name}"


class JointFaultError(XiaoyaoError):
    """关节故障异常

    当一个或多个关节处于故障状态时抛出。
    包含所有故障关节的列表。
    """

    def __init__(self, message: str, faulty_joints: Optional[List[JointFaultInfo]] = None):
        """
        Args:
            message: 错误消息
            faulty_joints: 故障关节列表
        """
        self.faulty_joints: List[JointFaultInfo] = faulty_joints or []
        super().__init__(message)

    def __str__(self):
        if self.faulty_joints:
            joints_str = "\n  ".join(str(j) for j in self.faulty_joints)
            return f"{self.message}\n  故障关节:\n  {joints_str}"
        return self.message


class DataReceiveError(XiaoyaoError):
    """数据接收异常

    当接收到的数据格式不正确或长度不符时抛出。
    """

    def __init__(self, message: str, expected_length: Optional[int] = None, actual_length: Optional[int] = None):
        """
        Args:
            message: 错误消息
            expected_length: 期望的数据长度
            actual_length: 实际的数据长度
        """
        self.expected_length = expected_length
        self.actual_length = actual_length
        super().__init__(message)

    def __str__(self):
        if self.expected_length is not None and self.actual_length is not None:
            return f"{self.message} (期望: {self.expected_length} 字节, 实际: {self.actual_length} 字节)"
        return self.message
