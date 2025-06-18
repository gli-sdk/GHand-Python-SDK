from . import comm   # 从comm模块导入通讯相关的全局函数
from .common import GestureType, RobotError, RobotStatus # 从 common 导入所有需要的枚举

"""整手控制模块"""
    
def open_ethercat(device_id: str) -> bool:
    """
    设置指定设备 ID 的手部模块 EtherCAT 通讯的相关参数。
    此函数用于针对特定设备调整其 EtherCAT 接口的具体行为。
    请注意，此函数不用于切换通讯协议类型，仅用于配置已连接或预设的 EtherCAT 接口。
    """
    print(f"【Hand】尝试设置 EtherCAT 通讯参数，设备ID: {device_id}")
    result = comm.send_msg("SET_COMM_ETHERCAT", {'device_id': device_id})
    
    if result == RobotError.NO_ERROR.value:
        print(f"【Hand】EtherCAT 通讯参数设置指令发送成功。")
        return True
    else:
        print(f"【Hand】EtherCAT 通讯参数设置指令发送失败，错误码: {result}")
        return False

def open_rs485(port: str, baud_rate: int = 115200) -> bool:
    """
    设置手部模块 RS485 串行通讯的相关参数。
    此函数用于调整 RS485 接口的具体行为。
    请注意，此函数不用于切换通讯协议类型，仅用于配置已连接或预设的 RS485 接口。
    设置后可能需要重启模块才能生效。
    """
    print(f"【Hand】尝试设置 RS485 通讯参数，端口: {port}, 波特率: {baud_rate}")
    result = comm.send_msg("SET_COMM_RS485", {'port': port, 'baud_rate': baud_rate})
    
    if result == RobotError.NO_ERROR.value:
        print(f"【Hand】RS485 通讯参数设置指令发送成功。")
        return True
    else:
        print(f"【Hand】RS485 通讯参数设置指令发送失败，错误码: {result}")
        return False

def set_can_com(baud_rate: int, node_id: int) -> bool:
    """
    设置手部模块 CAN 总线通讯的相关参数。
    此函数用于调整 CAN 接口的具体行为。
    请注意，此函数不用于切换通讯协议类型，仅用于配置已连接或预设的 CAN 接口。
    设置后可能需要重启模块才能生效。
    """
    print(f"【Hand】尝试设置 CAN 通讯参数，波特率: {baud_rate}, 节点ID: {node_id}")
    result = comm.send_msg("SET_COMM_CAN", {'baud_rate': baud_rate, 'node_id': node_id})
    
    if result == RobotError.NO_ERROR.value:
        print(f"【Hand】CAN 通讯参数设置指令发送成功。")
        return True
    else:
        print(f"【Hand】CAN 通讯参数设置指令发送失败，错误码: {result}")
        return False

def close_device() -> bool:
    print("【Hand】正在关闭设备...")
    result = comm.send_msg("CLOSE_DEVICE")
    return True if result == RobotError.NO_ERROR.value else False


def get_all_basic_info() -> dict:
    """
    获取手部模块的所有可用的基本信息，包括设备 ID、软件版本以及手部类型。
    在真实的工程项目中，此函数将通过与硬件通讯来获取实时数据。
    """
    print("【Hand】正在请求手部所有基本信息...")
    response = comm.send_msg("GET_ALL_BASIC_INFO") 
    
    if isinstance(response, dict):
        print("【Hand】成功获取手部基本信息。")
        return response
    else:
        error_code = response if isinstance(response, int) else RobotError.GENERAL_ERROR.value
        print(f"【Hand】获取手部基本信息失败，错误码: {RobotError(error_code).name} ({error_code})")
        return {} # 保持返回类型为 dict
    
def do_preset_gesture(gesture_type: GestureType) -> RobotError:
    """
    手部执行预定义的预设手势。此函数将指令发送至手部，并立即返回操作结果状态码。
    """
    print(f"【Hand】尝试执行预设手势: {gesture_type.name} (值: {gesture_type.value})...")
    result = comm.send_msg("DO_PRESET_GESTURE", gesture_type.value)
    
    # 模拟返回，如果成功，返回手势的value；否则返回错误码
    if result == gesture_type.value: 
        return RobotError.NO_ERROR # 成功执行手势，视为无错误
    elif result in [e.value for e in RobotError]:
        return RobotError(result)
    else:
        return RobotError.GENERAL_ERROR # 默认错误
    
def get_operation_status() -> RobotStatus:
    """
    获取手部模块的当前运行状态。
    """
    print("【Hand】获取手部当前运行状态...")
    result = comm.send_msg("GET_OPERATION_STATUS")
    if result in [s.value for s in RobotStatus]:
        return RobotStatus(result)
    else:
        return RobotStatus.UNKNOWN # 无法识别的状态
    
def release_protection() -> bool:
    print("【Hand】正在解除保护状态...")
    result = comm.send_msg("RELEASE_PROTECTION")
    return True if result == RobotError.NO_ERROR.value else False
    
def get_temperature() -> int:
    """获取当前温度"""
    pass
    
def set_temperature_threshold(self, min_temp: int, max_temp: int) -> int:
    """设置温度阈值"""
    pass
    
def get_device_id(self) -> str:
    """获取设备序列号"""
    pass
    
def get_software_version(self) -> str:
    """获取软件版本号"""
    pass
    
def set_can_com(self, baud_rate: int, node_id: int) -> bool:
    """设置CAN通讯参数"""
    pass

def set_rs485_com(self, baud_rate: int, data_bits: int, stop_bits: int, parity: str) -> bool:
    """设置RS485通讯参数"""
    pass

def reboot(self) -> bool:
    """重启设备"""
    pass

def initialize(self) -> bool:
    """设备初始化"""
    pass

def check_sensors(self) -> int:
    """传感器自检"""
    pass

def check_motors(self) -> int:
    """电机自检"""
    pass

def upgrade_firmware(self, firmware_path: str) -> bool:
    """固件升级"""
    pass

def get_hand_type(self) -> int:
    """获取手部类型"""
    pass