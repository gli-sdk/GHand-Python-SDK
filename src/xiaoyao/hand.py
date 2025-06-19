import os
from . import comm   # 从comm模块导入通讯相关的全局函数
from .common import GestureType, RobotError, RobotStatus # 从 common 导入所有需要的枚举

"""整手控制模块"""
    
def open_ethercat(device_id: str) -> bool:
    """
    设置指定设备 ID 的手部模块 EtherCAT 通讯的相关参数。
    此函数用于针对特定设备调整其 EtherCAT 接口的具体行为。
    请注意，此函数不用于切换通讯协议类型，仅用于配置已连接或预设的 EtherCAT 接口。
    """
    print(f"【Hand】尝试设置 EtherCAT 通讯参数，设备ID: {device_id}")
    result = comm.send_msg("SET_COMM_ETHERCAT", {'device_id': device_id})
    
    if result == RobotError.NO_ERROR.value:
        print(f"【Hand】EtherCAT 通讯参数设置指令发送成功。")
        return True
    else:
        print(f"【Hand】EtherCAT 通讯参数设置指令发送失败，错误码: {result}")
        return False

def open_rs485(port: str, baud_rate: int = 115200) -> bool:
    """
    设置手部模块 RS485 串行通讯的相关参数。
    此函数用于调整 RS485 接口的具体行为。
    请注意，此函数不用于切换通讯协议类型，仅用于配置已连接或预设的 RS485 接口。
    设置后可能需要重启模块才能生效。
    """
    print(f"【Hand】尝试设置 RS485 通讯参数，端口: {port}, 波特率: {baud_rate}")
    result = comm.send_msg("SET_COMM_RS485", {'port': port, 'baud_rate': baud_rate})
    
    if result == RobotError.NO_ERROR.value:
        print(f"【Hand】RS485 通讯参数设置指令发送成功。")
        return True
    else:
        print(f"【Hand】RS485 通讯参数设置指令发送失败，错误码: {result}")
        return False

def close_device() -> bool:
    print("【Hand】正在关闭设备...")
    result = comm.send_msg("CLOSE_DEVICE")
    return True if result == RobotError.NO_ERROR.value else False

def do_preset_gesture(gesture_type: GestureType) -> RobotError:
    """
    手部执行预定义的预设手势。此函数将指令发送至手部，并立即返回操作结果状态码。
    """
    print(f"【Hand】尝试执行预设手势: {gesture_type.name} (值: {gesture_type.value})...")
    result = comm.send_msg("DO_PRESET_GESTURE", gesture_type.value)
    
    # 模拟返回，如果成功，返回手势的value；否则返回错误码
    if result == gesture_type.value: 
        return RobotError.NO_ERROR # 成功执行手势，视为无错误
    elif result in [e.value for e in RobotError]:
        return RobotError(result)
    else:
        return RobotError.GENERAL_ERROR # 默认错误
    
def get_all_basic_info() -> dict:
    """
    获取手部模块的所有可用的基本信息，包括设备 ID、软件版本以及手部类型。
    """
    print("【Hand】正在请求手部所有基本信息...")
    response = comm.send_msg("GET_ALL_BASIC_INFO") 
    
    if isinstance(response, dict):
        print("【Hand】成功获取手部基本信息。")
        return response
    else:
        error_code = response if isinstance(response, int) else RobotError.GENERAL_ERROR.value
        print(f"【Hand】获取手部基本信息失败，错误码: {RobotError(error_code).name} ({error_code})")
        return {} # 保持返回类型为 dict

def get_operation_status() -> RobotStatus:
    """
    获取手部模块的当前运行状态。
    """
    print("【Hand】获取手部当前运行状态...")
    result = comm.send_msg("GET_OPERATION_STATUS")
    if result in [s.value for s in RobotStatus]:
        return RobotStatus(result)
    else:
        return RobotStatus.UNKNOWN # 无法识别的状态 

def get_temperature() -> int:
    """获取手部传感器的当前温度。"""
    print("【Temperature】正在获取手部温度...")  
     # 发送获取温度的命令
    result = comm.send_msg("GET_TEMPERATURE")
        
        # 检查返回结果是否为有效整数
    if isinstance(result, int):
            # 简单验证温度范围
        if -30 <= result <= 80:
            print(f"【Temperature】当前温度: {result}°C")
            return result
        else:
            print(f"【Temperature】获取温度失败，值超出合理范围: {result}°C")
            return 999
    else:
        print(f"【Temperature】获取温度失败，返回非整数值: {result}")
        return 999
    
def set_temperature_threshold(self, min_temp: int, max_temp: int) -> int:
    """设置温度阈值"""
    if min_temp >= max_temp:
        print(f"【Temperature】设置失败：最低温度({min_temp})必须低于最高温度({max_temp})")
        return RobotError.INVALID_PARAMETER
    if not (-30 <= min_temp <= 10):
        print(f"【Temperature】设置失败：最低温度({min_temp})超出有效范围(-30~10)")
        return RobotError.INVALID_PARAMETER 
    if not (40 <= max_temp <= 80):
        print(f"【Temperature】设置失败：最高温度({max_temp})超出有效范围(40~80)")
        return RobotError.INVALID_PARAMETER
    
    data = {
        "min_temp": min_temp,
        "max_temp": max_temp
    }
    
    print(f"【Temperature】设置温度阈值：{min_temp}°C ~ {max_temp}°C")
    result = comm.send_msg("SET_TEMPERATURE_THRESHOLD", data)  
    if result == RobotError.NO_ERROR.value:
        print(f"【Temperature】温度阈值设置成功")
        return RobotError.NO_ERROR
    else:
        error_name = RobotError(result).name if result in RobotError.__members__.values() else "未知错误"
        print(f"【Temperature】温度阈值设置失败，错误码: {result} ({error_name})")
        return RobotError(result)

def release_protection() -> bool:
    print("【Hand】正在解除保护状态...")
    result = comm.send_msg("RELEASE_PROTECTION")
    return True if result == RobotError.NO_ERROR.value else False

def reboot() -> bool:
    """重启设备"""
    print("【Device】正在发送重启命令...")   
    result = comm.send_msg("REBOOT_DEVICE")
    
    if result == RobotError.NO_ERROR.value:
        print("【Device】重启命令发送成功，设备将在几秒后重启")
        return True
    else:
        error_name = RobotError(result).name if result in RobotError.__members__.values() else "未知错误"
        print(f"【Device】重启命令发送失败，错误码: {result} ({error_name})")
        return False

def initialize() -> bool:
    """设备初始化"""
    print("【Device】重置设备状态...")
    result = comm.send_msg("RESET_DEVICE")
    if result != RobotError.NO_ERROR.value:
        error_name = RobotError(result).name if result in RobotError.__members__.values() else "未知错误"
        print(f"【Device】重置失败，错误码: {result} ({error_name})")
        return False
    
    print("【Device】检查连接状态...")
    status = get_operation_status()
    if status != RobotStatus.CALIBRATING:
        print(f"【Device】连接状态异常: {status.name}")
        return False
    
    print("【Device】初始化成功")
    return True

def check_sensors() -> int:
    """对手部所有传感器执行自检，检查其功能是否正常。"""
    print("【Sensors】开始传感器自检...")    
        # 发送传感器自检命令
    result = comm.send_msg("CHECK_SENSORS")
        
        # 检查返回结果
    if isinstance(result, int):
        if result == 0:
            print("【Sensors】所有传感器自检通过")
            return 0
        elif result < 0:
            # 负整数表示特定传感器故障
            sensor_id = abs(result)
            print(f"【Sensors】传感器 {sensor_id} 自检失败")
            return result
        else:
            print(f"【Sensors】自检返回无效状态码: {result}")
            return -999 
    else:
        print(f"【Sensors】自检返回非整数值: {result}")
        return -999
    
def can_com(baud_rate: int, node_id: int) -> bool:
    """
    设置手部模块 CAN 总线通讯的相关参数。
    此函数用于调整 CAN 接口的具体行为。
    请注意，此函数不用于切换通讯协议类型，仅用于配置已连接或预设的 CAN 接口。
    设置后可能需要重启模块才能生效。
    """
    print(f"【Hand】尝试设置 CAN 通讯参数，波特率: {baud_rate}, 节点ID: {node_id}")
    result = comm.send_msg("SET_COMM_CAN", {'baud_rate': baud_rate, 'node_id': node_id})
    
    if result == RobotError.NO_ERROR.value:
        print(f"【Hand】CAN 通讯参数设置指令发送成功。")
        return True
    else:
        print(f"【Hand】CAN 通讯参数设置指令发送失败，错误码: {result}")
        return False


     
def get_device_id(self) -> str:
    print("【Device】正在获取设备序列号...")
    result = comm.send_msg("GET_DEVICE_ID")
    if isinstance(result, dict) and "device_id" in result:
        device_id = result["device_id"]
        print(f"【Device】设备序列号: {device_id}")
        return device_id
    elif isinstance(result, int):
        error_name = RobotError(result).name if result in RobotError.__members__.values() else "未知错误"
        print(f"【Device】获取设备序列号失败，错误码: {result} ({error_name})")
    else:
        print(f"【Device】获取设备序列号失败，未知返回类型: {type(result)}")
    
    return ""

    
def get_software_version(self) -> str:
    result = comm.send_msg("GET_SOFTWARE_VERSION")
    if isinstance(result, str):
        if '.' in result:
            print(f"【Device】软件版本号: {result}")
            return result
        else:
            print(f"【Device】获取软件版本号失败，无效格式: {result}")
    elif isinstance(result, int):
        error_name = RobotError(result).name if result in RobotError.__members__.values() else "未知错误"
        print(f"【Device】获取软件版本号失败，错误码: {result} ({error_name})")
    else:
        print(f"【Device】获取软件版本号失败，未知返回类型: {type(result)}")
    
    return ""
    
def check_motors() -> int:
    """电机自检"""
    result = comm.send_msg("CHECK_MOTORS")
    
    if result == RobotError.NO_ERROR.value:
        print("【Motors】电机自检完成：所有电机正常")
        return 0
    
    elif isinstance(result, int):
        motor_id = (result >> 8) & 0xFF
        error_type = result & 0xFF
        error_name = RobotError(result).name if result in RobotError.__members__.values() else "未知错误"
        
        if motor_id < 0:
            print(f"【Motors】电机自检失败：电机ID={motor_id}，错误类型={error_type} ({error_name})")
        else:
            print(f"【Motors】电机自检失败，错误码: {result} ({error_name})")
        
        return result
    
    else:
        print(f"【Motors】电机自检失败，未知返回类型: {type(result)}")
        return RobotError.COMMUNICATION_FAILURE.value   

def upgrade_firmware(self, firmware_path: str) -> bool:
    """固件升级"""
    print(f"【Firmware】开始固件升级，文件: {firmware_path}")
    
    # 1. 检查固件文件是否存在
    if not os.path.exists(firmware_path):
        print(f"【Firmware】错误：固件文件不存在: {firmware_path}")
        return False
    
    # 2. 获取固件文件大小
    try:
        file_size = os.path.getsize(firmware_path)
        print(f"【Firmware】固件文件大小: {file_size} 字节")
    except OSError as e:
        print(f"【Firmware】无法获取文件大小: {e}")
        return False
    
    # 3. 准备升级（发送开始命令）
    print("【Firmware】准备升级...")
    result = comm.send_msg("START_FIRMWARE_UPGRADE", {
        "file_size": file_size
    })
    
    if result != RobotError.NO_ERROR.value:
        error_name = RobotError(result).name if result in RobotError.__members__.values() else "未知错误"
        print(f"【Firmware】升级准备失败，错误码: {result} ({error_name})")
        return False
    
    # 4. 分块发送固件数据
    CHUNK_SIZE = 4096  # 每次发送4KB
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"【Firmware】开始发送固件数据，共{total_chunks}块")
    
    try:
        with open(firmware_path, 'rb') as f:
            for chunk_idx in range(total_chunks):
                # 读取一块数据
                data = f.read(CHUNK_SIZE)
                
                # 发送数据块
                chunk_info = {
                    "chunk_index": chunk_idx,
                    "total_chunks": total_chunks,
                    "data": data
                }
                
                result = comm.send_msg("UPLOAD_FIRMWARE_CHUNK", chunk_info)
                
                if result != RobotError.NO_ERROR.value:
                    error_name = RobotError(result).name if result in RobotError.__members__.values() else "未知错误"
                    print(f"【Firmware】发送块 {chunk_idx+1}/{total_chunks} 失败，错误码: {result} ({error_name})")
                    return False
                
                # 打印进度
                progress = (chunk_idx + 1) / total_chunks * 100
                print(f"【Firmware】进度: {progress:.1f}% ({chunk_idx+1}/{total_chunks})")
    
    except Exception as e:
        print(f"【Firmware】发送固件过程中发生异常: {e}")
        return False
    
    # 5. 完成升级（发送结束命令）
    print("【Firmware】固件数据发送完成，开始安装...")
    result = comm.send_msg("FINISH_FIRMWARE_UPGRADE")
    
    if result != RobotError.NO_ERROR.value:
        error_name = RobotError(result).name if result in RobotError.__members__.values() else "未知错误"
        print(f"【Firmware】固件安装失败，错误码: {result} ({error_name})")
        return False
    
    # 6. 等待升级完成（设备重启）
    print("【Firmware】固件升级已提交，设备将重启并完成安装")
    print("【Firmware】请等待几分钟后再尝试连接")
    return True
