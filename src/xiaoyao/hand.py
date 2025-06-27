# src/xiaoyao/hand.py

import struct
import time
from ._internal.ethercat_client import (
    EtherCATClient, 
    OD_INDEX_DEVICE_IDENTITY, OD_SUBINDEX_VERSION_INFO, OD_SUBINDEX_SERIAL_NUMBER,
    OD_INDEX_PROTECTION_TEMP, OD_SUBINDEX_PROTECTION_TEMP, 
    OD_INDEX_MANU_CUSTOM, OD_SUBINDEX_HAND_ID, OD_SUBINDEX_REBOOT,
    OD_INDEX_FACTORY_RESET, OD_SUBINDEX_FACTORY_RESET
)
from .common import GestureType, RobotError, RobotStatus
from ._internal.ethercat_client import OD_INDEX_TEST_WRITE, OD_SUBINDEX_TEST_WRITE
from ._internal.ethercat_client import EC_STATE_SAFE_OP, EC_STATE_OPERATIONAL
# ==============================================================================
#  数据结构定义 (根据协议文档 3.1 RPDO 和 3.2 TPDO)
# ==============================================================================

# RPDO (PC接收, 来自灵巧手)
RPDO_FORMAT = (
    '< '      # 小端字节序
    '18h '    # finger_angle_list (18 * int16)
    '18H '    # finger_speed_list (18 * uint16)
    '18H '    # finger_torque_list (18 * uint16)
    '5x '     # 5字节填充
    '30h '    # 5个指尖位姿 (5 * 6 * int16)
    'B '      # operating_state (uint8)
    'b '      # hand_temperature (int8)
    'H'       # error_code (uint16)
)
RPDO_STRUCT = struct.Struct(RPDO_FORMAT)

# TPDO (PC发送, 去往灵巧手)
TPDO_FORMAT = (
    '< '      # 小端字节序
    # 单关节控制 (0x7001): ID(B)+pad(x)+angle(h)+speed(H)+torque(H)
    'BxhHH '
    # 所有关节控制 (0x7002): 13*2(角)+13*2(速)+13*2(力)
    '13h '
    '13H '
    '13H'
    # 其他控制模式可以根据需要继续添加
)
TPDO_STRUCT = struct.Struct(TPDO_FORMAT)


# ==============================================================================
#  1. 连接管理函数 (保持不变)
# ==============================================================================

def find_adapters():
    """查找可用的网络适配器。"""
    return EtherCATClient.get_instance().find_adapters()

def connect_to_hand(adapter_name: str, target_state_op: bool = True, target_state_safe_op: bool = False) -> bool:
    """
    初始化并连接到灵巧手。
    :param target_state_op: 是否尝试进入OP状态 (默认True)。
    :param target_state_safe_op: 是否尝试进入SAFE-OP状态。
    """
    client = EtherCATClient.get_instance()
    
    # 决定目标状态
    target_state = EC_STATE_OPERATIONAL
    if target_state_safe_op:
        target_state = EC_STATE_SAFE_OP
    elif not target_state_op: # 如果两个都False，就停在PRE-OP
        target_state = client.EC_STATE_PRE_OP

    try:
        return client.connect(adapter_name, target_state=target_state)
    except Exception as e:
        print(f"【Hand】连接过程中发生严重错误: {e}")
        return False

def close_device() -> bool:
    """断开与灵巧手的连接并释放资源。"""
    EtherCATClient.get_instance().disconnect()
    return True


# ==============================================================================
#  2. 核心通信与解析函数 (内部使用)
# ==============================================================================

def _update_and_get_rpdo_data() -> tuple:
    """执行一个PDO通信周期，并返回解析后的RPDO数据元组。"""
    client = EtherCATClient.get_instance()
    if not client.is_initialized:
        raise ConnectionError("设备未连接。")
    client.send_processdata()
    input_data = client.receive_processdata()
    if not input_data or len(input_data) < RPDO_STRUCT.size:
        return None
    try:
        return RPDO_STRUCT.unpack(input_data[:RPDO_STRUCT.size])
    except struct.error:
        return None


# ==============================================================================
#  3. 信息获取与配置层 (混合SDO和PDO实现)
# ==============================================================================

def get_all_basic_info() -> dict:
    """获取手部模块的所有基本信息。"""
    if not EtherCATClient.get_instance().is_initialized:
        raise ConnectionError("请先调用 connect_to_hand() 连接到设备。")
    print("【Hand】正在请求手部所有基本信息...")
    
    # 从PDO获取实时信息
    rpdo_data = _update_and_get_rpdo_data()
    
    info = {
        'device_id': get_device_id(), # SDO
        'software_version': get_software_version(), # SDO
        'hand_type_code': -1, # SDO (协议未定义，保留)
        # 'current_temperature': rpdo_data[86] if rpdo_data else 999, # PDO
        # 'operation_status_code': rpdo_data[85] if rpdo_data else RobotStatus.UNKNOWN.value, # PDO
    }
    
    if not info['device_id'] and not info['software_version']:
        print("【Hand】获取基本信息失败。")
        return {}
    
    print("【Hand】成功获取手部基本信息。")
    return info

def get_device_id() -> str:
    """获取设备序列号 (SDO Read - 标准对象)"""
    # 协议 4.2: 读取 0x1018, 0x04
    data_bytes = EtherCATClient.get_instance().sdo_read(OD_INDEX_DEVICE_IDENTITY, OD_SUBINDEX_SERIAL_NUMBER)
    return data_bytes.decode('utf-8', errors='ignore').strip('\x00') if data_bytes else ""

def get_software_version() -> str:
    """获取设备版本信息 (SDO Read - 标准对象)"""
    # 协议 4.1: 读取 0x1018, 0x03
    data_bytes = EtherCATClient.get_instance().sdo_read(OD_INDEX_DEVICE_IDENTITY, OD_SUBINDEX_VERSION_INFO)
    return data_bytes.decode('utf-8', errors='ignore').strip('\x00') if data_bytes else ""

def get_hand_type() -> int:
    """获取手部类型。协议中未定义此SDO，返回-1。"""
    print("【Hand】警告: 当前通信协议未定义获取手部类型的SDO。")
    return -1

def get_temperature() -> int:
    """从实时PDO数据中获取当前温度。"""
    rpdo_data = _update_and_get_rpdo_data()
    return rpdo_data[86] if rpdo_data else 999

def get_operation_status() -> RobotStatus:
    """从实时PDO数据中获取手部模块的当前运行状态。"""
    rpdo_data = _update_and_get_rpdo_data()
    if rpdo_data:
        try:
            return RobotStatus(rpdo_data[85])
        except (ValueError, IndexError):
            return RobotStatus.UNKNOWN
    return RobotStatus.UNKNOWN

def set_hand_id(hand_id: int) -> bool:
    """
    通过SDO写入手的节点ID (对应协议 4.4)。
    :param hand_id: 要设置的手的ID (有效范围: 0-255)。
    :return: True 如果指令被设备无错误接受，否则 False。
    """
    if not (0 <= hand_id <= 255):
        print(f"错误: hand_id ({hand_id}) 必须在 0-255 之间。")
        return False
    
    # 将整数打包成一个字节
    id_data = struct.pack('<B', hand_id)
    
    # 调用客户端的sdo_write。我们知道它在成功时不抛异常，失败时抛异常。
    try:
        EtherCATClient.get_instance().sdo_write(
            OD_INDEX_MANU_CUSTOM, 
            OD_SUBINDEX_HAND_ID, 
            id_data
        )
        return True # 没有异常，则写入被接受
    except Exception:
        return False # 任何异常都意味着失败

def set_temperature_threshold(min_temp: int, max_temp: int) -> bool:
    """
    通过SDO同时设置最低和最高保护温度 (对应协议 4.6)。

    此函数将根据协议定义，将 min_temp 和 max_temp 打包成两个
    连续的字节，并一次性写入到指定的对象字典地址。

    :param min_temp: 最低保护温度 (单位: °C, 例如: -10)。
    :param max_temp: 最高保护温度 (单位: °C, 例如: 60)。
    :return: True 如果写入指令被设备无错误接受，否则 False。
    """
    print(f"【Hand】正在通过SDO设置保护温度: Min={min_temp}°C, Max={max_temp}°C")
    
    # 检查输入值是否在单字节有符号整数的范围内 (-128 to 127)
    if not (-128 <= min_temp <= 127 and -128 <= max_temp <= 127):
        print(f"错误: 温度值必须在 -128 到 127 之间。")
        return False
        
    # 根据协议，将两个温度值打包为两个连续的有符号字节 (signed char)
    # 使用 '<bb' 格式符
    temp_data = struct.pack('<bb', min_temp, max_temp)
    
    try:
        # 调用客户端的sdo_write方法
        EtherCATClient.get_instance().sdo_write(
            OD_INDEX_PROTECTION_TEMP,     # 目标索引: 0x2001
            OD_SUBINDEX_PROTECTION_TEMP,  # 目标子索引: 0x01
            temp_data
        )
        # 如果代码能执行到这里，说明没有异常，写入被硬件接受
        return True
    except Exception as e:
        # 如果捕获到任何异常，说明写入操作被硬件拒绝
        print(f"  -> SDO写入失败，硬件返回异常: {e}")
        return False


# ==============================================================================
#  4. 动作与控制层
# ==============================================================================

def _send_control_command(command_data: dict):
    """内部函数，用于打包和发送TPDO控制指令。"""
    client = EtherCATClient.get_instance()
    if not client.is_op_state():
        print("错误：执行动作需要设备处于OP状态。")
        return
    
    # 创建一个空的、与协议匹配的TPDO字节包
    # 此处假设控制模式切换是通过不同索引的TPDO实现的，
    # 但协议似乎是单一TPDO，通过内容区分模式。
    # 我们需要一个“控制模式”字段，但协议中未明确给出。
    # 暂时我们将所有不用的字段填0。
    
    # 提取参数，提供默认值
    single_id = command_data.get('single_id', 0)
    single_angle = command_data.get('single_angle', 0)
    single_speed = command_data.get('single_speed', 0)
    single_torque = command_data.get('single_torque', 0)
    all_angles = command_data.get('all_angles', [0]*13)
    all_speeds = command_data.get('all_speeds', [0]*13)
    all_torques = command_data.get('all_torques', [0]*13)

    packed_data = TPDO_STRUCT.pack(
        single_id, single_angle, single_speed, single_torque,
        *all_angles, *all_speeds, *all_torques
    )
    
    client.set_output(packed_data)
    client.send_processdata()


def do_preset_gesture(gesture_type: GestureType) -> RobotError:
    """执行预定义的预设手势。"""
    print(f"【Hand】尝试执行预设手势: {gesture_type.name}...")
    
    # 将手势转换为所有关节的目标角度
    target_angles = [0] * 13
    # TODO: 向固件工程师咨询，填充真实的手势目标角度值
    if gesture_type == GestureType.FIST:
        target_angles = [90] * 13 # 示例值
    elif gesture_type == GestureType.OPEN_ALL_FINGERS:
        target_angles = [0] * 13
    
    command = {'all_angles': target_angles}
    _send_control_command(command)
    return RobotError.NO_ERROR

# 在 src/xiaoyao/hand.py 中添加这个新函数

def test_write_single_temperature(temp: int) -> bool:
    """
    【专用测试函数】
    通过SDO向 0x2001:01 写入一个单一的温度值。
    :param temp: 要写入的温度值。
    :return: True 如果写入成功，否则 False。
    """
    print(f"【Hand】[测试] 正在尝试向 0x2001:01 写入单个温度值: {temp}°C")
    
    # 根据协议，温度值是 signed char (1个字节)
    # 我们用 '<b' 来打包
    temp_data = struct.pack('<b', temp)
    
    try:
        EtherCATClient.get_instance().sdo_write(
            OD_INDEX_PROTECTION_TEMP, 
            0x01, # 直接使用子索引 1
            temp_data
        )
        return True
    except Exception as e:
        print(f" -> 写入失败，异常: {e}")
        return False

def initialize() -> bool:
    """
    初始化设备。协议中此功能对应于SDO写操作 "恢复出厂设置"。
    """
    # 协议 4.3: 写入 0x1011, 0x01
    print("【Hand】正在发送初始化(恢复出厂设置)指令...")
    print("【警告】此操作将恢复设备到出厂状态。")
    # 密码需要厂家提供，这里用一个占位符
    password = b'password' # <-- 必须用厂家提供的真实密码替换
    return EtherCATClient.get_instance().sdo_write(OD_INDEX_FACTORY_RESET, OD_SUBINDEX_FACTORY_RESET, password)


def reboot() -> bool:
    """
    通过SDO发送重启指令 (对应协议 4.5)。
    :return: True 如果指令被设备无错误接受，否则 False。
    """
    reboot_cmd = struct.pack('<B', 1) # 根据协议写入 0x01
    
    try:
        EtherCATClient.get_instance().sdo_write(
            OD_INDEX_MANU_CUSTOM, 
            OD_SUBINDEX_REBOOT, 
            reboot_cmd
        )
        return True
    except Exception:
        return False


def release_protection() -> bool:
    """
    解除保护状态。协议中未明确定义此接口。
    可能通过向特定控制字写入一个值来实现，暂时返回成功。
    """
    print("【Hand】尝试解除保护状态... (协议中未明确定义，返回成功)")
    # TODO: 确认解除保护状态的实现方式
    return True

def check_sensors() -> int:
    """
    传感器自检。协议中未明确定义此接口，返回成功。
    """
    print("【Hand】执行传感器自检... (协议中未明确定义，返回成功)")
    return 0

def check_motors() -> int:
    """
    电机自检。协议中未明确定义此接口，返回成功。
    """
    print("【Hand】执行电机自检... (协议中未明确定义，返回成功)")
    return 0

def upgrade_firmware(firmware_path: str) -> bool:
    """
    固件升级。这通常是一个复杂的文件传输过程，远超单次SDO/PDO。
    暂时返回不支持。
    """
    print(f"【Hand】固件升级功能 ({firmware_path}) 当前版本不支持。")
    return False

def test_write_to_2005(value: int) -> bool:
    """
    【专用测试函数】
    通过SDO向索引 0x2005, 子索引 0x01 写入一个整数值。
    :param value: 要写入的整数值。
    :return: True 如果写入成功，否则 False。
    """
    print(f"【Hand】[测试] 正在尝试向 0x2005:01 写入值: {value}")
    
    # 我们假设要写入的是一个4字节的有符号整数 (int32)
    # 这是最常见的数据类型之一。如果失败，可以尝试 '<h' (int16) 或 '<B' (uint8)
    # '<i' 代表小端字节序的有符号4字节整数 (signed int)
    data_to_write = struct.pack('<i', value)
    
    return EtherCATClient.get_instance().sdo_write(
        OD_INDEX_TEST_WRITE,
        OD_SUBINDEX_TEST_WRITE,
        data_to_write
    )

# 在 src/xiaoyao/hand.py 中添加这两个新函数

# 在 src/xiaoyao/hand.py 中

def get_hand_id() -> int:
    """【新增】通过SDO读取当前设置的手的ID。"""
    print("【Hand】[验证] 正在读回 Hand ID (0x2000:01)...")
    client = EtherCATClient.get_instance()
    
    data_bytes = client.sdo_read(OD_INDEX_MANU_CUSTOM, OD_SUBINDEX_HAND_ID)
    
    # --- 核心修改在这里 ---
    # 严格检查返回的数据不仅存在，而且长度必须是1字节
    if data_bytes and len(data_bytes) == 1:
        read_value = struct.unpack('<B', data_bytes)[0]
        return read_value
    
    # 如果 data_bytes 是空的或者长度不对，打印一个警告并返回失败
    print(f"  -> 【警告】读回Hand ID失败，从站返回的数据无效 (收到的数据: {data_bytes})。")

def get_temperature_threshold() -> tuple:
    """
    【新增】通过SDO读取当前设置的保护温度。
    对应协议文档 4.6: 从 0x2001 子索引 0x01 读取温度值。
    """
    print("【Hand】[验证] 正在读回保护温度 (0x2001:01)...")
    client = EtherCATClient.get_instance()

    # 假设返回的是两个字节 (min_temp, max_temp)
    data_bytes = client.sdo_read(OD_INDEX_PROTECTION_TEMP, OD_SUBINDEX_PROTECTION_TEMP)
    
    if data_bytes and len(data_bytes) >= 2:
        # '<bb' 代表两个有符号单字节整数 (signed char)
        min_temp, max_temp = struct.unpack('<bb', data_bytes)
        return (min_temp, max_temp)
        
    return (None, None) # 返回None表示读取失败