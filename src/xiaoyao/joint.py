# src/xiaoyao/joint.py

import struct
import time
from ._internal.ethercat_client import EtherCATClient
from .common import JointInfo, HandError, HandState

# RPDO (PC接收, 来自灵巧手 - 0x6001)
RPDO_FORMAT = (
    '< 18h 18H 18H 5x 30h B b H'
)
RPDO_STRUCT = struct.Struct(RPDO_FORMAT)

# TPDO (PC发送, 去往灵巧手)
# 假设第一个字节为控制模式: 1=单关节, 2=所有关节
TPDO_BUFFER = bytearray(1 + 8 + 78) # 1(mode) + 8(single) + 78(all) = 87 bytes

def _update_and_get_rpdo_data() -> tuple:
    """执行一个PDO通信周期，并返回解析后的RPDO数据元组。"""
    client = EtherCATClient.get_instance()
    if not client.is_op_state():
        print("警告: PDO通信需要设备处于OP状态。")
        return None
        
    client.send_processdata()
    input_data = client.receive_processdata()

    if not input_data or len(input_data) < RPDO_STRUCT.size:
        # print(f"【PDO调试】: 长度不匹配! 期望: {RPDO_STRUCT.size}, 实际: {len(input_data)}")
        return None

    try:
        return RPDO_STRUCT.unpack(input_data[:RPDO_STRUCT.size])
    except struct.error as e:
        print(f"【PDO调试】: 数据解析错误: {e}.")
        return None

def sub_joint_data(callback) -> int:
    """
    订阅所有关节的实时数据更新。
    """
    if not callable(callback):
        print("错误: 提供的 'callback' 不是一个可调用的函数。")
        return -1
    
    print("【Joint】正在注册关节数据回调...")
    sub_id = EtherCATClient.get_instance().add_subscriber('joint_data', callback)
    print(f"【Joint】关节数据订阅成功，订阅ID: {sub_id}")
    return sub_id

def unsub_joint_data(subscription_id: int) -> bool:
    """
    根据订阅ID，取消对关节数据的订阅。
    """
    print(f"【Joint】正在取消订阅ID {subscription_id} ...")
    success = EtherCATClient.get_instance().remove_subscriber(subscription_id)
    if success:
        print(f"【Joint】订阅ID {subscription_id} 已成功取消。")
    else:
        print(f"【Joint】取消订阅失败，未找到ID {subscription_id}。")
    return success

def _send_pdo_command(target_index_start: int, data_format: str, *data_args):
    """【内部函数】用于构造并发送一个通用的TPDO指令。"""
    client = EtherCATClient.get_instance()
    if not client.is_op_state():
        print("错误：设置关节需要设备处于OP状态。")
        return False

    try:
        command_type = 0x01 # 关节指令
        buffer = struct.pack(f'<BH{data_format}', command_type, target_index_start, *data_args)
        
        client.set_output(buffer)
        client.send_processdata()
        return True
    except struct.error as e:
        print(f"打包PDO指令时发生错误: {e}")
        return False

def set_joint(joint_targets: list) -> HandError:
    """
    设置一个或多个主动关节的目标。
    """
    client = EtherCATClient.get_instance()
    if not client.is_op_state():
        return HandError.NOT_INITIALIZED
    
    # 【注意】这里的TPDO布局需要与固件工程师最终确认
    # TPDO总大小: 13个主动关节 * 每个关节(angle,speed,torque都是float) 12字节 = 156字节
    tpdo_buffer = bytearray(13 * 12) 

    # 遍历用户传入的目标，填充缓冲区
    for target in joint_targets:
        # 【注意】这里的 joint_id 需要是从0开始的、代表13个主动关节的逻辑ID
        joint_id = target.joint_id
        if 0 <= joint_id < 13:
            offset = joint_id * 12 # 每个关节目标占12字节 (3个float)
            struct.pack_into('<fff', tpdo_buffer, offset,
                             target.angle, target.speed, target.torque)
    
    client.set_output(tpdo_buffer)
    return HandError.NO_ERROR

def stop_all_joints() -> bool:
    """停止所有关节运动。通过发送速度为0的指令实现。"""
    targets = []
    for i in range(13): # 13个主动关节
        info = JointInfo()
        info.joint_id = i
        info.speed = 0.0
        # 理想情况下，目标角度应设为当前角度，但为简化，设为0
        info.angle = 0.0
        info.torque = 0.0
        targets.append(info)
    
    return set_joint(targets) == HandError.NO_ERROR

def get_all_joints() -> list:
    """
    从缓存中获取所有18个关节的最新信息列表。
    此函数执行速度极快，因为它不涉及任何IO操作。
    """
    all_data = EtherCATClient.get_instance().get_latest_parsed_data()
    return all_data.get('joints', [])

def get_joint_info(joint_id: int) -> JointInfo:
    """获取指定ID的单个关节的完整信息。"""
    all_joints_data = get_all_joints()
    if all_joints_data and 0 <= joint_id < len(all_joints_data):
        return all_joints_data[joint_id]
    return None

def set_max_torque(joint_id: int, max_torque: float) -> int:
    """设置指定关节的最大力矩。"""
    target = JointInfo()
    target.joint_id = joint_id
    target.torque = max_torque
    # 保持角度和速度为当前值是最佳实践，简化为0
    target.angle = 0.0 
    target.speed = 0.0
    return set_joint([target])

def set_all_joints_max_torque(max_torque: float) -> int:
    """设置所有关节的最大力矩。协议中此功能在 set_joint 中实现。"""
    print("【Joint】信息: 设置所有关节最大力矩请使用 set_joint 函数。")
    targets = []
    for i in range(13):
        info = JointInfo()
        info.joint_id = i
        info.torque = max_torque
        targets.append(info)
    return set_joint(targets)

def get_passive_joints() -> list:
    """
    查询并列出所有被动关节的ID。
    """
    print("【Joint】正在根据开发规范查询被动关节...")
    # 2,3,4,5 (Thumb), 8,9,10 (FF), 13,14 (MF), 17,18 (RF), 21,22 (LF)
    active_joint_ids = {2, 3, 4, 5, 8, 9, 10, 13, 14, 17, 18, 21, 22}
    
    # 总关节ID范围是 0-22
    all_joint_ids = set(range(23))
    
    # 从所有关节中减去主动关节，剩下的就是被动关节
    passive_joint_ids_int = sorted(list(all_joint_ids - active_joint_ids))
    
    # 转换为字符串列表
    passive_joint_ids_str = [str(i) for i in passive_joint_ids_int]
    
    print(f"【Joint】查询到被动关节列表: {passive_joint_ids_str}")
    return passive_joint_ids_str

def query_linked_joint(joint_id: int) -> int:
    """
    查询与指定关节存在联动关系的关节ID。
    """
    print(f"【Joint】正在查询关节ID {joint_id} 的联动关系...")
    LINKAGE_MAP = {
        # 食指: FF2(8) 带动 FF1(7)
        8: 7,
        # 中指: MF2(13) 带动 MF1(12)
        13: 12,
        # 无名指: RF2(17) 带动 RF1(16)
        17: 16,
        # 小拇指: LF2(21) 带动 LF1(20)
        21: 20,
        # 拇指的联动关系通常更复杂，此处暂不猜测
    }
    
    linked_id = LINKAGE_MAP.get(joint_id, -1)
    
    if linked_id != -1:
        print(f"【Joint】关节ID {joint_id} 的联动关节为: {linked_id}")
    else:
        print(f"【Joint】关节ID {joint_id} 没有在预设的联动表中找到关系。")
        
    return linked_id