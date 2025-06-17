from . import module
from . import message
from . import event
from .errors import RobotError

class Tip(module.Module):
    """指尖控制模块"""
    
    def set_posture(self, tip_id: int, x: float, y: float, z: float, tx: float, ty: float, tz: float) -> int:
        """设置指尖姿态"""
        pass
    
    def set_all_tips_posture(self, tip_targets: list) -> int:
        """设置所有指尖姿态"""
        pass
    
    def sub_tip_position(self, callback) -> int:
        """订阅指尖位置数据"""
        pass
    
    def unsub_tip_position(self) -> bool:
        """取消订阅指尖位置数据"""
        pass