# src/xiaoyao/tip.py

import struct
from ._internal.ethercat_client import EtherCATClient
from .common import HandError, TipPose # 假设common中有TipPose数据类
import time

# 导入 joint 模块中的内部发送函数
from . import joint

def set_tip_pose(tip_id: int, pose: TipPose) -> HandError:
    """
    设置单个指尖的目标位姿。(对应 0x7021-0x7025)
    """
    print(f"【Tip】正在为指尖ID {tip_id} 设置姿态...")
    
    # 根据协议，指尖位姿控制也是独立的 SDO 对象
    # 我们通过一个特殊的 TPDO 来发送
    target_index = 0x7021 + tip_id
    
    success = joint._send_pdo_command(
        target_index, 'ffffff', # 6个 float
        pose.x, pose.y, pose.z, pose.roll, pose.pitch, pose.yaw
    )
    
    return HandError.NO_ERROR if success else HandError.COMMUNICATION_ERROR

def set_all_tips_pose(tip_targets: list) -> HandError:
    """
    为多个指尖设置其在机器人坐标系中的精确姿态。
    """
    print(f"【Tip】正在为 {len(tip_targets)} 个指尖设置姿态...")
    success = True
    for tip_id, pose in tip_targets:
        if not set_tip_pose(tip_id, pose):
            success = False
            print(f"  -> 设置指尖 {tip_id} 姿态失败。")
            break
        time.sleep(0.002)
        
    return HandError.NO_ERROR if success else HandError.COMMUNICATION_ERROR

def sub_tip_position(callback) -> int:
    """订阅指尖位置数据。在当前SDK模式下不受支持。"""
    print("【Tip】警告: sub_tip_position 在当前SDK模式下不受支持。")
    return -1

def unsub_tip_position(subscription_id: int) -> bool:
    """取消订阅。"""
    print("【Tip】警告: unsub_tip_position 在当前SDK模式下不受支持。")
    return True