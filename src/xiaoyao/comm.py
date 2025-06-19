# comm.py
import sys
import time
import math
import numpy as np
from enum import IntEnum
from typing import Optional, Dict, Union, Any

# --- SDK 枚举定义 (为了 comm.py 独立模拟运行，这里暂时将枚举定义再次包含。)
class RobotStatus(IntEnum):
    IDLE = 0; RUNNING = 1; STOPPED = 2; DISABLED = 3; ENABLED = 4; CALIBRATING = 5; STANDBY = 6; LOW_POWER = 7; ERROR = 100; UNKNOWN = 999
class RobotError(IntEnum):
    NO_ERROR = 0; GENERAL_ERROR = 1; INVALID_PARAMETER = 2; COMMUNICATION_FAILURE = 3; TIMEOUT = 4; HARDWARE_FAILURE = 5; NOT_SUPPORTED = 6; BUSY = 7; NOT_INITIALIZED = 8; PROTECTION_TRIGGERED = 9; INVALID_STATE = 10; ACTION_FAILED = 11
class GestureType(IntEnum):
    OPEN_ALL_FINGERS = 0; OPPOSE_FINGERS = 1; FIST = 2; POINT_FINGER = 3; V_SIGN = 4; OK_SIGN = 5; GRIP_SIX = 6

class Message:
    """消息封装类，用于SDK内部通讯"""
    def __init__(self, msg_type, data=None):
        self.msg_type = msg_type
        self.data = data
        self.result: Optional[Union[int, float, Dict[str, Any]]] = None
class Dispatcher:
    """SDK内部事件调度器"""
    _instance = None
    _subscription_counter = 0
    _active_subscriptions = {}
    
    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = Dispatcher()
        return cls._instance

    def send(self, msg: Message):
        """
        模拟发送消息，并根据 msg.msg_type 返回专属的、不同的模拟结果。
        """
        time.sleep(0.05) # 模拟通讯延迟

        # --- Hand 模块消息处理 ---
        if msg.msg_type == "GET_ALL_BASIC_INFO":

            msg.result = {
                'current_temperature': 38,
                'operation_status_code': RobotStatus.IDLE.value,
                'device_id': 'SN_G5-13A28D_MOCK_001',
                'software_version': 'v1.1.0',
                'communication_method': 'ethernet',
                'hand_type_code': 1, # 1 for right_hand
                'hand_type_description': 'right_hand'
            }
        elif msg.msg_type == "DO_PRESET_GESTURE":
            if msg.data in [g.value for g in GestureType]:
                msg.result = msg.data
            else:
                msg.result = RobotError.INVALID_PARAMETER.value
        elif msg.msg_type == "GET_OPERATION_STATUS":
            msg.result = RobotStatus.IDLE.value
        
        # --- Joint 模块消息处理 ---
        elif msg.msg_type == "GET_JOINT_SPEED":
            # 返回一个独特的模拟速度值
            msg.result = np.random.uniform(0.1, 2.5) 
        elif msg.msg_type == "SET_JOINT_ANGLE":
            # 模拟设置成功
            msg.result = RobotError.NO_ERROR.value
        # (其他 joint 相关函数可以按需添加)

        # --- Tactile 模块消息处理 ---
        elif msg.msg_type == "GET_TACTILE_DATA":
            # 返回一个独特的模拟触觉数据
            msg.result = (np.random.rand(3, 3) * 10).tolist()

        # --- 其他模块可以继续添加 ---
        
        else:
            # 如果没有匹配任何已知的消息类型，返回 "不支持"
            msg.result = RobotError.NOT_SUPPORTED.value
        
        return msg.result
    def recv(self, msg_type: str, timeout: float = 1.0):
        return 


    def subscribe(self, msg_type, callback):
        self._subscription_counter += 1
        sub_id = self._subscription_counter
        self._active_subscriptions[sub_id] = {'msg_type': msg_type, 'callback': callback}
        return sub_id

    def unsubscribe(self, sub_id):
        if sub_id in self._active_subscriptions:
            del self._active_subscriptions[sub_id]
            return True
        return False

# 全局 Dispatcher 实例
_dispatcher_instance = Dispatcher.get_instance()

def send_msg(msg_type: str, data=None):
    """SDK 内部发送消息的全局函数。"""
    msg = Message(msg_type, data)
    return _dispatcher_instance.send(msg)

def recv_msg(msg_type: str, timeout: float = 1.0):
    """SDK 内部接收消息的全局函数。"""
    return _dispatcher_instance.recv(msg_type, timeout)

def subscribe(msg_type: str, callback):
    """SDK 内部订阅数据的全局函数。"""
    return _dispatcher_instance.subscribe(msg_type, callback)

def unsubscribe(subscription_id: int) -> bool:
    """SDK 内部取消订阅的全局函数。"""
    return _dispatcher_instance.unsubscribe(subscription_id)