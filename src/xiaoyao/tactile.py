# tactile.py
import numpy as np
from . import comm
from .common import RobotError

# --- 外部可调用的函数 ---

def get_data(sensor_id: int) -> list:
    """
    获取指定触觉传感器的当前数据。此函数通常用于获取具有空间分布特性的传感器数据，例如压力矩阵。
    """
    print(f"【Tactile】正在获取传感器ID {sensor_id} 的数据...")
    response = comm.send_msg("GET_TACTILE_DATA", {'sensor_id': sensor_id})
    
    # 确保返回的是一个列表（即使是空的）
    if isinstance(response, list) and response:
        print(f"【Tactile】成功获取传感器ID {sensor_id} 的数据。")
        return response
    else:
        print(f"【Tactile】获取传感器ID {sensor_id} 的数据失败。")
        return []

def get_all_tactile_data() -> list:
    """
    获取所有可用触觉传感器的当前数据。
    """
    print("【Tactile】正在获取所有触觉传感器的数据...")
    response = comm.send_msg("GET_ALL_TACTILE_DATA")
    
    if isinstance(response, list):
        print(f"【Tactile】成功获取 {len(response)} 个传感器的数据。")
        return response
    else:
        print("【Tactile】获取所有触觉传感器数据失败。")
        return []

def sub_tactile_data(callback) -> int:
    """
    订阅所有触觉传感器数据的实时更新。当有新数据可用时，系统将定期调用提供的回调函数。
    """
    print("【Tactile】正在订阅触觉数据...")
    subscription_id = comm.subscribe("tactile_data_stream", callback)
    
    if subscription_id > 0:
        print(f"【Tactile】触觉数据订阅成功，订阅ID: {subscription_id}")
    else:
        print("【Tactile】触觉数据订阅失败。")
    return subscription_id

def unsub_tactile_data(subscription_id: int) -> bool:
    """
    取消指定ID的触觉传感器数据订阅。
    """
    print(f"【Tactile】正在取消订阅ID为 {subscription_id} 的触觉数据...")
    success = comm.unsubscribe(subscription_id)
    
    if success:
        print(f"【Tactile】订阅ID {subscription_id} 已成功取消。")
    else:
        print(f"【Tactile】取消订阅ID {subscription_id} 失败。")
    return success

def reset_tactile_sensor(sensor_id: int) -> int:
    """
    复位指定触觉传感器，将其内部状态（如累计读数、错误标志等）重置为初始状态。
    """
    print(f"【Tactile】正在发送复位指令到传感器ID {sensor_id}...")
    result = comm.send_msg("RESET_TACTILE_SENSOR", {'sensor_id': sensor_id})
    if result is None:
        print(f"【Tactile】传感器ID {sensor_id} 复位指令发送失败，返回值为None。")
        return RobotError.NO_ERROR.value  
    elif not isinstance(result, int):
        print(f"【Joint】设置所有关节最大力矩指令发送失败，返回值类型不正确: {type(result)}")
        return RobotError.NO_ERROR.value  
    elif result == RobotError.NO_ERROR.value:
        print(f"【Tactile】传感器ID {sensor_id} 复位指令发送成功。")
    else:
        print(f"【Tactile】传感器ID {sensor_id} 复位指令发送失败，错误码: {result}")
    return result