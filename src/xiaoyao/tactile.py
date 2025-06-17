import numpy as np
from . import module
from . import message
from . import event
from .errors import RobotError

class Tactile(module.Module):
    """触觉传感器模块"""
    
    def get_data(self, sensor_id: int) -> np.ndarray:
        """获取触觉传感器数据"""
        pass
    
    def get_all_tactile_data(self) -> list:
        """获取所有触觉传感器数据"""
        pass
    
    def sub_tactile_data(self, callback) -> int:
        """订阅触觉数据"""
        pass
    
    def unsub_tactile_data(self) -> bool:
        """取消订阅触觉数据"""
        pass
    
    def reset_tactile_sensor(self, sensor_id: int) -> int:
        """复位触觉传感器"""
        pass