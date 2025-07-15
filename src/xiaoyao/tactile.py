# src/xiaoyao/tactile.py

import struct
from ._internal.ethercat_client import EtherCATClient
from .common import HandError, ObjectDictionary

# --- 外部可调用的函数 ---

def get_all_tactile_data() -> list:
    
    all_data = EtherCATClient.get_instance().get_latest_parsed_data()
    # .get() 方法确保即使没有触觉数据，也能安全地返回一个空列表
    return all_data.get('tactile_data', [])

def get_data(sensor_id: int) -> list:
    
    all_tactile_data = get_all_tactile_data()
    for sensor_data in all_tactile_data:
        if sensor_data.get('sensor_id') == sensor_id:
            return sensor_data.get('data', [])
    
    # 如果循环结束仍未找到
    return []

def sub_tactile_data(callback) -> int:
    
    if not callable(callback):
        print("错误: 提供的 'callback' 不是一个可调用的函数。")
        return -1
    
    client = EtherCATClient.get_instance()
    # 使用客户端的通用订阅机制，为 'tactile_data' 类型添加订阅者
    return client.add_subscriber('tactile_data', callback)

def unsub_tactile_data(subscription_id: int) -> bool:
    
    return EtherCATClient.get_instance().remove_subscriber(subscription_id)

def reset_tactile_sensor(sensor_id: int) -> bool:
    
    print(f"【Tactile】正在通过SDO发送复位指令到传感器ID {sensor_id}...")
    client = EtherCATClient.get_instance()
    
    try:
        # 将传感器ID打包成一个字节 (假设协议要求)
        reset_payload = struct.pack('<B', sensor_id)
        
        # 使用 ObjectDictionary 中定义的常量进行SDO写操作
        client.sdo_write(
            ObjectDictionary.TactileControl.INDEX,
            ObjectDictionary.TactileControl.SUB_RESET,
            reset_payload
        )
        print(f"【Tactile】传感器ID {sensor_id} 复位指令已成功发送。")
        return True
    except Exception as e:
        print(f"【Tactile】传感器ID {sensor_id} 复位指令发送失败: {e}")
        return False

def tactile_sensors_selftest() -> int:
    print("【Tactile】正在请求传感器自检...")
    CHECK_SENSORS_CODE = 12
    
    if EtherCATClient.execute_command(CHECK_SENSORS_CODE):
        print("  -> 传感器自检指令已发送。请稍后查询设备状态。")
        return 0
    else:
        print("  -> 传感器自检指令发送失败。")
        return -1 # 表示指令发送失败
