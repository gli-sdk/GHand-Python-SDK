# src/xiaoyao/hand.py

import struct
import time
from ._internal.ethercat_client import EtherCATClient,execute_command,get_realtime_data, start_pdo_communication,find_adapters, auto_connect_to_hand
from .common import GestureType, HandError, HandState, ObjectDictionary

def close_device():
    print("【Hand】正在关闭设备连接...")
    EtherCATClient.get_instance().disconnect()

def get_operation_state() -> HandState:
    data = get_realtime_data()
    if data:
        state_code = data.get('operation_state_code')
        if state_code is not None:
            try:
                return HandState(state_code)
            except ValueError:
                print(f"【Hand】警告: 从设备收到一个未在协议中定义的未知状态码: {state_code}。")
                return HandState.UNKNOWN
    return HandState.UNKNOWN

def get_temperature() -> int:
    """获取手部当前的温度。"""
    data = EtherCATClient.get_realtime_data()
    return data.get('hand_temperature', 999) # 999 代表无效值

def do_preset_gesture(gesture_type: GestureType) -> HandError:
    
    print(f"【Hand】正在请求执行预设手势: {gesture_type.name}...")
    command_code_map = {
        GestureType.OK: 1, 
        GestureType.OPEN_ALL_FINGERS: 2,
        GestureType.FIST: 3,
        GestureType.THUMBS_UP: 4,
        GestureType.GRIP_SIX: 5,
    }

    # 获取对应手势的指令码
    command_code = command_code_map.get(gesture_type)
    
    # 检查手势是否被支持
    if command_code is None:
        print(f"错误: 不支持的手势类型 {gesture_type.name}")
        return HandError.INVALID_PARAMETER

    # 调用内部函数发送指令码
    if execute_command(command_code):
        print(f"  -> 指令码 {command_code} 已成功发送。")
        return HandError.NO_ERROR
    else:
        print(f"  -> 指令码 {command_code} 发送失败。")
        return HandError.COMMUNICATION_ERROR

def get_all_basic_info() -> dict:
    """获取静态SDO信息。此函数必须在PRE-OP状态下调用。"""
    client = EtherCATClient.get_instance()
    if client.is_op_state():
        print("警告: 已处于OP运行状态，不应再调用此函数获取静态信息。")
        return {}
    
    info = {
        'device_id': get_device_id(),
        'software_version': get_software_version(),
        'hand_type': get_hand_type()
    }
    return info

def get_device_id() -> str:
    """【SDO】获取设备序列号。"""
    data_bytes = EtherCATClient.get_instance().sdo_read(
        ObjectDictionary.Identity.INDEX, 
        ObjectDictionary.Identity.SUB_SERIAL_NUMBER
    )
    return data_bytes.decode('utf-8', errors='ignore').strip('\x00') if data_bytes else ""

def get_software_version() -> str:
    """【SDO】获取设备软件版本。"""
    data_bytes = EtherCATClient.get_instance().sdo_read(
        ObjectDictionary.Identity.INDEX, 
        ObjectDictionary.Identity.SUB_VERSION_INFO
    )
    return data_bytes.decode('utf-8', errors='ignore').strip('\x00') if data_bytes else ""

def get_hand_type() -> int:
    """
    此函数通过 SDO 读取手部类型。
    """
    try:
        data_bytes = EtherCATClient.get_instance().sdo_read(
            ObjectDictionary.HandInfo.INDEX, 
            ObjectDictionary.HandInfo.SUB_HAND_TYPE
        )
        if data_bytes is None: return -1
        if len(data_bytes) != 1:
            print(f"【Hand】警告: 获取手部类型时，期望1字节，收到 {len(data_bytes)} 字节。")
            return -1
        
        hand_type_val = int(data_bytes[0])
        return hand_type_val if hand_type_val in [0, 1] else -1

    except Exception as e:
        print(f"【Hand】错误: 在 get_hand_type() 中发生未知异常: {e}")
        return -1            

def set_hand_id(hand_id: int) -> bool:
    """【SDO】通过SDO写入手的节点ID。"""
    if not (0 <= hand_id <= 255):
        print(f"错误: hand_id ({hand_id}) 必须在 0-255 之间。")
        return False
    id_data = struct.pack('<B', hand_id)
    try:
        EtherCATClient.get_instance().sdo_write(
            ObjectDictionary.ManufacturerCustom.INDEX, 
            ObjectDictionary.ManufacturerCustom.SUB_HAND_ID, 
            id_data
        )
        return True
    except Exception:
        return False

def get_hand_id() -> int:
    """【SDO】通过SDO读取当前设置的手的ID。"""
    data_bytes = EtherCATClient.get_instance().sdo_read(
        ObjectDictionary.ManufacturerCustom.INDEX, 
        ObjectDictionary.ManufacturerCustom.SUB_HAND_ID
    )
    if data_bytes and len(data_bytes) == 1:
        return struct.unpack('<B', data_bytes)[0]
    print(f"  -> 【警告】读回Hand ID失败，从站返回的数据无效。")
    return -1

def set_temperature_threshold(min_temp: int, max_temp: int) -> bool:
    """【SDO】通过SDO同时设置最低和最高保护温度。"""
    if not (-30 <= min_temp <= 0 and 50 <= max_temp <= 90):
        print(f"错误: 温度值必须在 -30 到 0 之间 (最低) 和 50 到 90 之间 (最高)。")
        return False
    temp_data = struct.pack('<bb', min_temp, max_temp)
    try:
        EtherCATClient.get_instance().sdo_write(
            ObjectDictionary.Protection.INDEX, 
            ObjectDictionary.Protection.SUB_PROTECTION_TEMP, 
            temp_data
        )
        return True
    except Exception as e:
        print(f"  -> SDO写入失败，硬件返回异常: {e}")
        return False
    
def initialize() -> bool:
    """
    对手部进行初始化。
    """
    print("【Hand】正在请求初始化校准...")
    print("【警告】在执行此操作时，请确保机器人工作区域内无障碍物。")
    INITIALIZE_COMMAND_CODE = 10 
    
    return execute_command(INITIALIZE_COMMAND_CODE)

def reboot() -> bool:
    """【SDO】通过SDO发送重启指令。"""
    print("【Hand】正在发送重启指令...")
    reboot_cmd = struct.pack('<B', 1)
    try:
        EtherCATClient.get_instance().sdo_write(
            ObjectDictionary.ManufacturerCustom.INDEX, 
            ObjectDictionary.ManufacturerCustom.SUB_REBOOT, 
            reboot_cmd
        )
        return True
    except Exception:
        return False

def release_protection() -> bool:
    """
    尝试解除手部模块的保护状态。
    """
    print("【Hand】正在尝试解除设备保护状态...")
    RELEASE_PROTECTION_CODE = 11
    
    return execute_command(RELEASE_PROTECTION_CODE)

def test_sensors() -> int:
    """
    请求对所有传感器执行自检。
    """
    print("【Hand】正在请求传感器自检...")
    CHECK_SENSORS_CODE = 12
    
    if execute_command(CHECK_SENSORS_CODE):
        print("  -> 传感器自检指令已发送。请稍后查询设备状态。")
        return 0
    else:
        print("  -> 传感器自检指令发送失败。")
        return -1 # 表示指令发送失败

def test_motors() -> int:
    """
    请求对所有电机执行自检。
    """
    print("【Hand】正在请求电机自检...")
    CHECK_MOTORS_CODE = 13
    
    if execute_command(CHECK_MOTORS_CODE):
        print("  -> 电机自检指令已发送。请稍后查询设备状态。")
        return 0
    else:
        print("  -> 电机自检指令发送失败。")
        return -1

def update_firmware(firmware_path: str) -> bool:

    print(f"【Hand】固件升级功能 ({firmware_path}) 当前版本不支持。")
    return False

def set_light(mode: int, color: tuple, frequency_ms: int = 1000) -> bool:
    """
    设置灵巧手上的状态指示灯。
    """
    print(f"【Hand】正在设置灯光: 模式={mode}, 颜色={color}, 频率={frequency_ms}ms")
    
    client = EtherCATClient.get_instance()
    # 【注意】这个索引是假设的，需要确认
    OD_INDEX_LIGHT_CONTROL = 0x2100
    try:
        # 1. 写入灯光模式 (Subindex 1, uint8)
        mode_data = struct.pack('<B', mode)
        client.sdo_write(OD_INDEX_LIGHT_CONTROL, 1, mode_data)
        print("  -> 模式写入成功。")

        # 2. 写入颜色RGB值 (Subindex 2, uint8[3])
        r, g, b = color
        color_data = struct.pack('<BBB', r, g, b)
        client.sdo_write(OD_INDEX_LIGHT_CONTROL, 2, color_data)
        print("  -> 颜色写入成功。")

        # 3. 写入频率 (Subindex 3, uint16)
        freq_data = struct.pack('<H', frequency_ms)
        client.sdo_write(OD_INDEX_LIGHT_CONTROL, 3, freq_data)
        print("  -> 频率写入成功。")
        
        # 所有写入都未抛出异常，则视为成功
        return True
        
    except Exception as e:
        print(f"【Hand】设置灯光失败: {e}")
        return False