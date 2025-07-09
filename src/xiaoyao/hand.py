# src/xiaoyao/hand.py

import struct
import time
from ._internal.ethercat_client import (
    EtherCATClient, 
    OD_INDEX_DEVICE_IDENTITY, OD_SUBINDEX_VERSION_INFO, OD_SUBINDEX_SERIAL_NUMBER,
    OD_INDEX_PROTECTION_TEMP, OD_SUBINDEX_PROTECTION_TEMP, 
    OD_INDEX_MANU_CUSTOM, OD_SUBINDEX_HAND_ID, OD_SUBINDEX_REBOOT,
    OD_INDEX_FACTORY_RESET, OD_SUBINDEX_FACTORY_RESET,
    OD_INDEX_HAND_TYPE ,OD_SUBINDEX_HAND_TYPE 
)
from .common import GestureType, HandError, HandState
JOINT_BLOCK_SIZE = 16
NUM_JOINTS = 18
# ==============================================================================
#  1. 连接管理函数 (保持不变)
# ==============================================================================

def find_adapters():
    """查找可用的网络适配器。"""
    return EtherCATClient.get_instance().find_adapters()

def connect_to_hand(adapter_name: str, setup_only: bool = False) -> bool:
    """
    【核心底层连接函数】连接到灵巧手，并可选择最终状态。
    """
    try:
        # goto_op_state 的值为 True 当且仅当 setup_only 为 False
        return EtherCATClient.get_instance().connect(
            adapter_name=adapter_name, 
            goto_op_state=(not setup_only)
        )
    except Exception as e:
        print(f"【Hand】底层连接过程中发生错误: {e}")
        return False

def open_ethercat(adapter_name: str) -> bool:
    """
    打开EtherCAT设备并进入 PRE-OP (配置) 状态。
    """
    print(f"【Hand】正在打开 EtherCAT 设备至配置模式: {adapter_name}...")
    # 内部调用核心连接函数，并明确指定 setup_only=True
    return connect_to_hand(adapter_name, setup_only=True)

def close_device():
    print("【Hand】正在关闭设备连接...")
    EtherCATClient.get_instance().disconnect()

# ==============================================================================
#  2. 核心PDO通信函数 (以硬件要求为准)
# ==============================================================================

def _exchange_pdo_data(tpdo_value: int = 0) -> bytes:
    """
    执行一次完整的PDO数据交换。
    - 发送一个2字节的TPDO（默认为0，作为心跳）。
    - 接收硬件返回的RPDO数据。
    - 如果在交换后掉线，则抛出异常。
    """
    client = EtherCATClient.get_instance()

    # 1. 准备并发送TPDO (根据硬件要求的2字节长度构建)
    tpdo_data = struct.pack('<H', tpdo_value)
    client.set_output(tpdo_data)
    
    # 2. 执行发送和接收
    client.send_processdata()
    rpdo_data = client.receive_processdata()

    # 3. 交换后立即检查状态，确保链路稳定
    if not client.is_op_state():
        raise ConnectionError("设备在PDO交换后从OP状态掉线。请与硬件方确认2字节TPDO心跳包的正确内容。")
    
    return rpdo_data

# ==============================================================================
#  3. PDO数据解析与信息获取
# ==============================================================================

# --- 核心PDO通信 ---
def _execute_pdo_cycle(command_code: int = 0) -> bytes:
    """
    执行一次完整的PDO通信周期。
    :param command_code: 要发送的2字节指令码。
    :return: 接收到的48字节RPDO数据，失败则返回空bytes。
    """
    client = EtherCATClient.get_instance()
    if not client.is_op_state():
        print("错误: 设备未处于OP状态。")
        return b''
        
    client.set_output(struct.pack('<H', command_code))
    client.send_processdata()
    return client.receive_processdata()

# --- 数据解析与功能实现 ---

# 状态码到枚举的映射
_State_MAP = {
    0: HandState.IDLE,
    1: HandState.RUNNING,
    2: HandState.PROTECTIVE_STOP,
    3: HandState.ERROR,
}

def get_realtime_data() -> dict:
    """
    【PDO】从输入缓冲区获取并解析所有最新的实时数据。
    """
    client = EtherCATClient.get_instance()
    if not client.is_op_state():
        return {}

    # 假设 client.get_raw_pdo_inputs() 返回原始的PDO输入字节串
    raw_bytes = client.get_latest_rpdo() 

    if not raw_bytes or len(raw_bytes) < (NUM_JOINTS * JOINT_BLOCK_SIZE):
        # 字节太短，无法解析
        return {}
    
    # 初始化用于存放解析结果的列表
    joint_angles = []
    joint_speeds = []
    joint_torques = []
    
    # --- 核心解析逻辑 ---
    try:
        # 遍历18个关节的数据块
        for i in range(NUM_JOINTS):
            # 计算当前关节块的起始偏移量
            offset = i * JOINT_BLOCK_SIZE
            
            # 从偏移量处解析数据
            # 'B' = unsigned char (1 byte) for state
            # 'x' = padding byte
            # 'f' = float (4 bytes)
            # '<' 表示小端字节序 (Little-endian)，EtherCAT标准
            # 我们只关心 angle, speed, torque
            _state, angle, speed, torque = struct.unpack_from('<B 3x f f f', raw_bytes, offset)
            
            joint_angles.append(angle)
            joint_speeds.append(speed)
            joint_torques.append(torque)

        # --- 解析其他数据 ---
        # 假设关节数据块之后是整手信息 (0x6041)
        # 偏移量 = 18 * 16 = 288
        other_data_offset = NUM_JOINTS * JOINT_BLOCK_SIZE
        
        # 解析整手信息: operating_state(u8), hand_temperature(i8), error_code(u8)
        # '<B b B' -> u-char, char, u-char
        op_state, temp, err_code = struct.unpack_from('<B b B', raw_bytes, other_data_offset)

        # --- 构造返回字典 ---
        info_dict = {
            'operation_state_code': op_state,
            'current_temperature': temp,
            'error_code': err_code,
            'joint_angles': joint_angles,
            'joint_speeds': joint_speeds,
            'joint_torques': joint_torques,
            # 你可以继续在这里解析指尖、触觉等其他数据
        }
        return info_dict
        
    except struct.error as e:
        # 如果字节长度或格式不匹配，会抛出 struct.error
        print(f"【SDK内部错误】解析PDO字节流失败: {e}")
        return {}
    except Exception as e:
        print(f"【SDK内部错误】在 get_realtime_data 中发生未知错误: {e}")
        return {}

# --- 上层便捷API ---
def send_command(command_code: int) -> bool:
    """
    向设备发送一个2字节的指令码。
    这是改变设备应用状态的关键函数。
    :param command_code: 要发送的整数指令码。
    :return: True 如果指令被成功发送。
    """
    client = EtherCATClient.get_instance()
    if not client.is_op_state():
        print("错误: 设备未处于OP状态，无法发送指令。")
        return False
    
    # 直接使用 client 的底层方法来发送数据
    try:
        client.set_output(struct.pack('<H', command_code))
        client.master.send_processdata()
        client.master.receive_processdata(timeout=2000)
        return True
    except Exception as e:
        print(f"发送指令时发生错误: {e}")
        return False

def get_operation_State() -> HandState:
    """
    获取手部当前的运行状态。
    """
    data = get_realtime_data()
    if data and 'operating_State_code' in data:
        # 使用修正后的 _State_MAP，这里会返回一个枚举对象
        # .get() 方法能在字典中找不到键时，安全地返回默认值
        return _State_MAP.get(data['operating_State_code'], HandState.UNKNOWN)
    
    # 如果获取数据失败(data is None)，返回 UNKNOWN 枚举对象
    return HandState.UNKNOWN

def get_temperature() -> int:
    """获取手部当前的温度。"""
    data = get_realtime_data()
    return data.get('hand_temperature', 999) # 999 代表无效值

def get_error_code() -> int:
    """获取当前的错误码。"""
    data = get_realtime_data()
    return data.get('error_code', 0)

def get_sensor_data() -> list:
    """获取11个传感器的浮点型数据列表。"""
    data = get_realtime_data()
    return data.get('sensor_floats', [])


def execute_command(command_code: int) -> bool:
    """
    【内部函数】向设备发送一个2字节的指令码。
    这是在当前2字节TPDO配置下，唯一能做的控制。
    :param command_code: 要发送的整数指令码。
    :return: True 如果指令被成功发送，否则 False。
    """
    client = EtherCATClient.get_instance()
    if not client.is_op_state():
        print("错误: 设备未处于OP状态，无法发送指令。")
        return False
    
    try:
        # 将指令码打包成2个字节 (unsigned short)
        tpdo_data = struct.pack('<H', command_code)
        
        # 将数据写入输出缓冲区并发送
        client.set_output(tpdo_data)
        client.send_processdata()
        
        # 为了确保指令被接收，我们可以等待一个或两个通信周期
        time.sleep(0.004)
        
        return True
    except Exception as e:
        print(f"发送指令时发生错误: {e}")
        return False

def do_preset_gesture(gesture_type: GestureType) -> HandError:
    """
    手部执行预定义的预设手势。
    此函数通过PDO向手部发送一个代表特定手势的指令码，
    并立即返回操作结果状态码。
    """
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
        return HandError.COMMUNICATION_FAILURE

# ==============================================================================
#  5. SDO 信息获取与配置层 (包含您提供的所有函数)
# ==============================================================================
def connect_for_setup(adapter_name: str) -> bool:
    """第一步：连接并进入配置模式。"""
    return EtherCATClient.get_instance().connect_to_preop(adapter_name)

def start_pdo_communication() -> bool:
    """第二步：启动高速PDO通信。"""
    return EtherCATClient.get_instance().start_op_mode()

def get_all_basic_info() -> dict:
    """获取静态SDO信息。此函数必须在PRE-OP状态下调用。"""
    client = EtherCATClient.get_instance()
    if client.is_op_state():
        print("警告: 已处于OP运行状态，不应再调用此函数获取静态信息。")
        return {}
    # ... (只保留SDO读取的部分)
    info = {
        'device_id': get_device_id(),
        'software_version': get_software_version(),
        'hand_type': get_hand_type()
    }
    return info

def get_device_id() -> str:
    """【SDO】获取设备序列号。"""
    data_bytes = EtherCATClient.get_instance().sdo_read(OD_INDEX_DEVICE_IDENTITY, OD_SUBINDEX_SERIAL_NUMBER)
    return data_bytes.decode('utf-8', errors='ignore').strip('\x00') if data_bytes else ""

def get_software_version() -> str:
    """【SDO】获取设备软件版本。"""
    data_bytes = EtherCATClient.get_instance().sdo_read(OD_INDEX_DEVICE_IDENTITY, OD_SUBINDEX_VERSION_INFO)
    return data_bytes.decode('utf-8', errors='ignore').strip('\x00') if data_bytes else ""

def get_hand_type() -> int:
    """
    此函数通过 SDO 读取索引 0x2012, 子索引 0x00 来获取手部类型。
    根据协议，0 代表左手，1 代表右手。
    """
    try:
        # 调用底层的 SDO 读取方法
        # 假设 sdo_read 在失败时会抛出异常或返回 None
        data_bytes = EtherCATClient.get_instance().sdo_read(
            OD_INDEX_HAND_TYPE, 
            OD_SUBINDEX_HAND_TYPE
        )

        # 1. 检查读取是否成功（返回了有效的 bytes 对象）
        if data_bytes is None:
            # sdo_read 内部已经打印了错误日志，这里我们直接返回错误代码
            return -1

        # 2. 检查返回的字节长度是否为1
        if len(data_bytes) != 1:
            print(f"【Hand】警告: 获取手部类型时，期望得到1个字节，但实际收到了 {len(data_bytes)} 字节。")
            return -1
        
        # 3. 将字节转换为整数
        hand_type_val = int(data_bytes[0])
        
        # 4. 检查返回值是否在预期的 0 或 1 范围内
        if hand_type_val in [0, 1]:
            # 成功获取到有效值
            return hand_type_val
        else:
            # 收到了意外的值
            print(f"【Hand】警告: 获取手部类型时，收到了一个无效的值: {hand_type_val}。")
            return -1

    except Exception as e:
        # 捕获其他可能的未知异常，例如底层库的非 SdoError 异常
        print(f"【Hand】错误: 在 get_hand_type() 中发生未知异常: {e}")
        return -1            

def set_hand_id(hand_id: int) -> bool:
    """【SDO】通过SDO写入手的节点ID。"""
    if not (0 <= hand_id <= 255):
        print(f"错误: hand_id ({hand_id}) 必须在 0-255 之间。")
        return False
    id_data = struct.pack('<B', hand_id)
    try:
        EtherCATClient.get_instance().sdo_write(OD_INDEX_MANU_CUSTOM, OD_SUBINDEX_HAND_ID, id_data)
        return True
    except Exception:
        return False

def get_hand_id() -> int:
    """【SDO】通过SDO读取当前设置的手的ID。"""
    data_bytes = EtherCATClient.get_instance().sdo_read(OD_INDEX_MANU_CUSTOM, OD_SUBINDEX_HAND_ID)
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
        EtherCATClient.get_instance().sdo_write(OD_INDEX_PROTECTION_TEMP, OD_SUBINDEX_PROTECTION_TEMP, temp_data)
        return True
    except Exception as e:
        print(f"  -> SDO写入失败，硬件返回异常: {e}")
        return False
    

# ==============================================================================
#  6. 系统控制函数 (SDO及其他)
# ==============================================================================

def initialize() -> bool:
    """
    对手部进行初始化。
    """
    print("【Hand】正在请求初始化校准...")
    print("【警告】在执行此操作时，请确保机器人工作区域内无障碍物。")
    
    # 【注意】这里的指令码 10 是一个通用的猜测值。
    # 您必须与固件工程师确认“初始化校准”对应的真实指令码。
    INITIALIZE_COMMAND_CODE = 10 
    
    return execute_command(INITIALIZE_COMMAND_CODE)

def reboot() -> bool:
    """【SDO】通过SDO发送重启指令。"""
    print("【Hand】正在发送重启指令...")
    reboot_cmd = struct.pack('<B', 1)
    try:
        EtherCATClient.get_instance().sdo_write(OD_INDEX_MANU_CUSTOM, OD_SUBINDEX_REBOOT, reboot_cmd)
        return True
    except Exception:
        return False

def release_protection() -> bool:
    """
    尝试解除手部模块的保护状态。
    """
    print("【Hand】正在尝试解除设备保护状态...")
    
    # 【注意】这里的指令码 11 是一个通用的猜测值。
    # 您必须与固件工程师确认“解除保护”对应的真实指令码。
    RELEASE_PROTECTION_CODE = 11
    
    return execute_command(RELEASE_PROTECTION_CODE)

def test_sensors() -> int:
    """
    请求对所有传感器执行自检。
    """
    print("【Hand】正在请求传感器自检...")

    # 【注意】这里的指令码 12 是一个猜测值。
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

    # 【注意】这里的指令码 13 是一个猜测值。
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

# ==============================================================================
#  7. 灯光控制功能
# ==============================================================================

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