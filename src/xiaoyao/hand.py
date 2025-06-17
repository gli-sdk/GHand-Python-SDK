from enum import IntEnum
from . import module
from . import message
from . import event
from .errors import RobotError

class GestureType(IntEnum):
    """预设手势类型枚举"""
    OPEN_ALL_FINGERS = 0
    OPPOSE_FINGERS = 1
    FIST = 2
    POINT_FINGER = 3
    V_SIGN = 4
    GRIP_SIX = 6

class Hand(module.Module):
    """整手控制模块"""
    
    def open_ethercat(self, device_id: str) -> bool:
        """设置EtherCAT通讯参数"""
        pass
    
    def close_device(self) -> None:
        """关闭当前设备"""
        pass
    
    def get_all_basic_info(self) -> dict:
        """获取所有基本信息"""
        pass
    
    def do_preset_gesture(self, gesture_type: GestureType) -> RobotError:
        """执行预设手势"""
        pass
    
    def get_operation_status(self) -> int:
        """获取当前运行状态"""
        pass
    
    def release_protection(self) -> bool:
        """解除保护状态"""
        pass
    
    def get_temperature(self) -> int:
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