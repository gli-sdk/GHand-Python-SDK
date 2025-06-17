from . import module
from . import message
from . import event
from .common import JointInfo
from .errors import RobotError

class Joint(module.Module):
    """关节控制模块"""
    
    def sub_joint_data(self, callback) -> int:
        """订阅关节数据"""
        pass
    
    def unsub_joint_data(self) -> bool:
        """取消订阅关节数据"""
        pass
    
    def set_joint(self, joint_targets) -> int:
        """设置关节目标角度"""
        pass
    
    def get_joint_info(self, joint_id: int) -> JointInfo:
        """获取指定关节信息"""
        pass
    
    def get_all_joints(self) -> list:
        """获取所有关节信息"""
        pass
    
    def set_max_torque(self, joint_id: int, max_torque: float) -> bool:
        """设置关节最大力矩"""
        pass
    
    def set_all_joints_max_torque(self, max_torque: float) -> bool:
        """设置所有关节最大力矩"""
        pass
    
    def get_passive_joints(self) -> list:
        """获取被动关节"""
        pass
    
    def query_linked_joint(self, joint_id: int) -> int:
        """查询联动关节"""
        pass
    
    def stop_all_joints(self) -> bool:
        """停止所有关节运动"""
        pass