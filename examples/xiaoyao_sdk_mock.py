import sys
import time
import math
import numpy as np
from enum import IntEnum

# --- SDK 枚举定义 (与您的正式 SDK 定义一致) ---
class RobotStatus(IntEnum):
    IDLE = 0            # 空闲状态，准备接收指令
    RUNNING = 1         # 正在执行任务或运动中
    STOPPED = 2         # 已停止运动或任务
    DISABLED = 3        # 功能被禁用，不响应指令（例如电机禁用）
    ENABLED = 4         # 功能已启用，可响应指令（例如电机启用）
    CALIBRATING = 5     # 正在执行校准或初始化过程
    STANDBY = 6         # 待机模式，通常为低功耗状态
    LOW_POWER = 7       # 低功耗模式
    ERROR = 100         # 发生一般性错误，需要检查具体错误码
    UNKNOWN = 999       # 未知状态或无法获取当前状态

class RobotError(IntEnum):
    NO_ERROR = 0                    # 操作成功，无错误
    GENERAL_ERROR = 1               # 一般性或未分类的错误
    INVALID_PARAMETER = 2           # 函数参数无效或超出指定范围
    COMMUNICATION_FAILURE = 3       # 与设备通讯故障或连接中断
    TIMEOUT = 4                     # 操作在指定时间内未能完成
    HARDWARE_FAILURE = 5            # 硬件故障，例如电机损坏、传感器故障
    NOT_SUPPORTED = 6               # 请求的操作或功能当前设备不支持
    BUSY = 7                        # 设备当前正忙于其他任务，无法执行当前操作
    NOT_INITIALIZED = 8             # 设备或模块未初始化或未校准
    PROTECTION_TRIGGERED = 9        # 保护机制被触发（如过温、过流、碰撞）
    INVALID_STATE = 10              # 当前设备状态下无法执行此操作
    ACTION_FAILED = 11              # 动作指令已发送，但实际动作未能成功完成

class GestureType(IntEnum):
    OPEN_ALL_FINGERS = 0   # 将手部所有手指张开到最大位置
    OPPOSE_FINGERS = 1     # 将手部手指执行对指动作
    FIST = 2               # 握拳姿态
    POINT_FINGER = 3       # 食指指向姿态
    V_SIGN = 4             # 比V字手势
    OK_SIGN = 5            # 比OK手势 (新增)
    GRIP_SIX = 6           # 将手部调整为预设的“6”姿态

# --- 模拟 SDK 基础架构 ---
class Module:
    def __init__(self, client_dispatcher=None):
        self._dispatcher = client_dispatcher

class Message:
    def __init__(self, msg_type, data=None, effect=None):
        self.msg_type = msg_type
        self.data = data
        self.effect = effect
        self.result = None

class Dispatcher:
    _instance = None
    _subscription_counter = 0
    _active_subscriptions = {}

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = Dispatcher()
        return cls._instance

    def send(self, msg):
        # 模拟消息发送和结果返回
        # print(f"[Mock Dispatcher] Sending: {msg.msg_type}, Data: {msg.data}")
        if msg.msg_type == "get_info_basic":
            msg.result = {
                'current_temperature': 35,
                'operation_status_code': RobotStatus.IDLE.value,
                'operation_status_description': 'idle',
                'device_id': 'XYZ123456',
                'software_version': 'v1.0.1',
                'communication_method': 'ethercat',
                'hand_type_code': 1,
                'hand_type_description': 'right_hand'
            }
        elif msg.msg_type == "get_tactile_data":
            # 模拟一个 3x3 触觉矩阵数据
            msg.result = np.random.rand(3, 3).tolist()
        elif msg.msg_type == "get_joint_speed":
            msg.result = np.random.uniform(0.1, 5.0) # 模拟一个关节速度
        elif msg.msg_type == "set_preset_gesture":
            if isinstance(msg.data, GestureType):
                msg.result = msg.data.value # 成功执行手势，返回手势对应的数值
            else:
                msg.result = RobotError.INVALID_PARAMETER.value
        elif msg.msg_type == "set_angle":
            # Simplistic mock for set_angle, just returns success
            msg.result = RobotError.NO_ERROR.value
        else:
            msg.result = RobotError.NOT_SUPPORTED.value # 模拟未支持的请求
        return msg.result

    def subscribe(self, msg_type, callback):
        # 模拟订阅逻辑，返回一个订阅ID
        self._subscription_counter += 1
        sub_id = self._subscription_counter
        self._active_subscriptions[sub_id] = {'msg_type': msg_type, 'callback': callback}
        # print(f"[Mock Dispatcher] Subscribed to {msg_type} with ID: {sub_id}")
        return sub_id

    def unsubscribe(self, sub_id):
        if sub_id in self._active_subscriptions:
            del self._active_subscriptions[sub_id]
            # print(f"[Mock Dispatcher] Unsubscribed ID: {sub_id}")
            return True
        return False

# --- 模拟 SDK 模块类 (基于文档签名) ---
class Hand(Module):
    def get_all_basic_info(self) -> dict:
        msg = Message("get_info_basic")
        return self._dispatcher.send(msg)
    
    def set_preset_gesture(self, gesture_type: GestureType) -> int:
        msg = Message("set_preset_gesture", data=gesture_type)
        return self._dispatcher.send(msg)
    
    def get_operation_status(self) -> int:
        # Simplified mock, always returns IDLE for hand status
        return RobotStatus.IDLE.value

class Joint(Module):
    def set_angle(self, joint_targets, callback=None) -> int:
        msg = Message("set_angle", data=joint_targets, effect=callback)
        return self._dispatcher.send(msg)

    def get_angle(self, joint_id) -> float:
        # Mock angle
        return 0.0 # Placeholder
    
    def get_speed(self, joint_id) -> float:
        msg = Message("get_joint_speed", data={'joint_id': joint_id})
        return self._dispatcher.send(msg)
    
    def get_all_angles(self) -> list:
        # Mock all angles
        return [{'joint_id': i, 'angle': math.degrees(math.sin(time.time() + i))} for i in range(5)] # 5 joints
    
    def get_all_speeds(self) -> list:
        # Mock all speeds
        return [{'joint_id': i, 'speed': np.random.uniform(0.1, 5.0)} for i in range(5)]
    
    def subscribe_joint_data(self, callback) -> int:
        return self._dispatcher.subscribe("joint_data_stream", callback)
    
    def cancel_subscription(self, subscription_id) -> bool:
        return self._dispatcher.unsubscribe(subscription_id)

class Tip(Module):
    def set_posture(self, tip_id, x, y, z, tx, ty, tz) -> int:
        # Simplistic mock
        return RobotError.NO_ERROR.value
    
    def set_all_tips_posture(self, tip_targets) -> int:
        # Simplistic mock
        return RobotError.NO_ERROR.value
    
    def sub_tip_position(self, callback) -> int:
        return self._dispatcher.subscribe("tip_position_stream", callback)
    
    def unsub_tip_position(self, subscription_id) -> bool:
        return self._dispatcher.unsubscribe(subscription_id)

class Tactile(Module):
    def get_data(self, sensor_id) -> list:
        msg = Message("get_tactile_data", data={'sensor_id': sensor_id})
        result = self._dispatcher.send(msg)
        return result if result else [] # Ensure list return
    
    def get_all_tactile_data(self) -> list:
        # Mock multiple sensors
        return [{'sensor_id': i, 'data': np.random.rand(3,3).tolist()} for i in range(2)] # 2 sensors
    
    def subscribe_data(self, callback) -> int:
        return self._dispatcher.subscribe("tactile_data_stream", callback)
    
    def cancel_subscription(self, subscription_id) -> bool:
        return self._dispatcher.unsubscribe(subscription_id)

class LED(Module):
    def set_color(self, r, g, b) -> bool:
        # Mock LED, always success
        return True

# --- 模拟 SDK 客户端 ---
class XiaoyaoClient:
    def __init__(self):
        self._dispatcher = Dispatcher.get_instance()
        self.hand = Hand(self._dispatcher)
        self.joint = Joint(self._dispatcher)
        self.tip = Tip(self._dispatcher)
        self.tactile = Tactile(self._dispatcher)
        self.led = LED(self._dispatcher) # Kept for completeness but not used in examples

    def connect(self):
        print("Connecting to Xiaoyao Hand (Mock)...")
        time.sleep(0.5)
        print("Connected.")
        return True

    def disconnect(self):
        print("Disconnecting from Xiaoyao Hand (Mock)...")
        time.sleep(0.5)
        print("Disconnected.")
        return True

    def send(self, msg):
        return self._dispatcher.send(msg)

# end of xiaoyao_sdk_mock.py