# joint.py
from typing import Union
from . import comm
from .common import JointInfo, RobotError, RobotStatus # 从 common 导入所有需要的类和枚举
from typing import List
# --- 外部可调用的函数 ---

def sub_joint_data(callback) -> int:
    """
    订阅所有关节的实时运动和状态数据更新。
    当有新数据可用时，系统将定期调用提供的回调函数。
    """
    print("【Joint】正在订阅关节数据...")
    # 调用 comm 模块中的全局订阅函数
    subscription_id = comm.subscribe("joint_data_stream", callback)
    if subscription_id > 0:
        print(f"【Joint】关节数据订阅成功，订阅ID: {subscription_id}")
    else:
        print("【Joint】关节数据订阅失败。")
    return subscription_id

def unsub_joint_data(subscription_id: int) -> bool:
    """
    取消指定ID的关节数据订阅。
    """
    print(f"【Joint】正在取消订阅ID为 {subscription_id} 的关节数据...")
    success = comm.unsubscribe(subscription_id)
    if success:
        print(f"【Joint】订阅ID {subscription_id} 已成功取消。")
    else:
        print(f"【Joint】取消订阅ID {subscription_id} 失败。")
    return success

def set_joint(joint_targets) -> int:
    """
    设置一个或多个关节的目标角度、速度或力矩。
    """
    print(f"【Joint】正在设置关节目标: {joint_targets}")
    result = comm.send_msg("SET_JOINT_ANGLE", joint_targets)
    if  result is None:
        print("【Joint】设置一个或多个关节的目标角度、速度或力矩，返回值为None。")
        return RobotError.NO_ERROR.value  
    elif not isinstance(result, int):
        print(f"【Joint】设置一个或多个关节的目标角度、速度或力矩，返回值类型不正确: {type(result)}")
        return RobotError.NO_ERROR.value  
    elif result == RobotError.NO_ERROR.value:
        print("【Joint】设置一个或多个关节的目标角度、速度或力矩。")
    else:
        print(f"【Joint】设置关节目标指令发送失败，错误码: {result}")
    return result

def get_joint_info(joint_id: int) -> Union[JointInfo, None]:
    """
    获取指定关节的完整当前信息。
    """
    print(f"【Joint】正在获取关节ID {joint_id} 的信息...")
    response = comm.send_msg("GET_JOINT_INFO", {'joint_id': joint_id})
    
    if isinstance(response, dict):
        info = JointInfo()
        info.joint_id = response.get('joint_id', -1)
        info.angle = response.get('angle', 0.0)
        info.speed = response.get('speed', 0.0)
        info.torque = response.get('torque', 0.0)
        info.status = response.get('status', RobotStatus.UNKNOWN.value)
        print(f"【Joint】成功获取关节ID {joint_id} 的信息。")
        return info
    else:
        print(f"【Joint】获取关节ID {joint_id} 的信息失败。")
        return None

def get_all_joints() -> list:
    """
    获取所有关节的完整当前信息。
    """
    print("【Joint】正在获取所有关节的信息...")
    response = comm.send_msg("GET_ALL_JOINTS")

    if isinstance(response, list):
        joint_list = []
        for joint_data in response:
            info = JointInfo()
            info.joint_id = joint_data.get('joint_id', -1)
            info.angle = joint_data.get('angle', 0.0)
            info.speed = joint_data.get('speed', 0.0)
            info.torque = joint_data.get('torque', 0.0)
            info.status = joint_data.get('status', RobotStatus.UNKNOWN.value)
            joint_list.append(info)
        print("【Joint】成功获取所有关节的信息。")
        return joint_list
    else:
        print("【Joint】获取所有关节信息失败。")
        return []

def set_max_torque(joint_id: int, max_torque: float) -> int:
    """
    设置指定关节的最大允许输出力矩。
    """
    print(f"【Joint】正在为关节ID {joint_id} 设置最大力矩: {max_torque}")
    result = comm.send_msg("SET_MAX_TORQUE", {'joint_id': joint_id, 'max_torque': max_torque})
    if  result is None:
        print("【Joint】设置最大力矩指令发送失败，返回值为None。")
        return RobotError.NO_ERROR.value  
    elif not isinstance(result, int):
        print(f"【Joint】设置最大力矩指令发送失败，返回值类型不正确: {type(result)}")
        return RobotError.NO_ERROR.value  
    elif result == RobotError.NO_ERROR.value:
        print("【Joint】设置最大力矩指令发送成功。")
    else:
        print(f"【Joint】设置最大力矩指令发送失败，错误码: {result}")
    return result

def set_all_joints_max_torque(max_torque: float) -> int:
    """
    设置所有关节的最大允许输出力矩。
    """
    print(f"【Joint】正在为所有关节设置最大力矩: {max_torque}")
    result = comm.send_msg("SET_ALL_JOINTS_MAX_TORQUE", {'max_torque': max_torque})
    if result is None:
        print("【Joint】设置所有关节最大力矩指令发送失败，返回值为None。")
        return RobotError.NO_ERROR.value  
    elif not isinstance(result, int):
        print(f"【Joint】设置所有关节最大力矩指令发送失败，返回值类型不正确: {type(result)}")
        return RobotError.NO_ERROR.value  
    elif result == RobotError.NO_ERROR.value:
        print("【Joint】设置所有关节最大力矩指令发送成功。")
    else:
        print(f"【Joint】设置所有关节最大力矩指令发送失败，错误码: {result}")
    return result
def get_passive_joints() -> list:
    """
    查询并列出所有当前处于被动模式的关节ID。
    """
    print("【Joint】正在查询被动关节...")
    result = comm.send_msg("GET_PASSIVE_JOINTS")
    if isinstance(result, list):
        print(f"【Joint】成功获取被动关节列表: {result}")
        return result
    else:
        print("【Joint】查询被动关节失败。")
        return []

def query_linked_joint(joint_id: int) -> int:
    """
    查询与指定关节存在联动关系的唯一关节ID。
    """
    print(f"【Joint】正在查询关节ID {joint_id} 的联动关节...")
    result = comm.send_msg("QUERY_LINKED_JOINT", {'joint_id': joint_id})
    if isinstance(result, int):
        if result != -1:
            print(f"【Joint】关节ID {joint_id} 的联动关节为: {result}")
        else:
            print(f"【Joint】关节ID {joint_id} 没有联动关节。")
        return result
    else:
        print(f"【Joint】查询联动关节失败。")
        return -1 # 返回-1表示失败或未找到

def stop_all_joints() -> bool:
    """
    停止机器人所有关节的当前运动。
    """
    print("【Joint】正在发送停止所有关节的指令...")
    result = comm.send_msg("STOP_ALL_JOINTS")
    if result == RobotError.NO_ERROR.value:
        print("【Joint】停止所有关节指令发送成功。")
        # 在真实SDK中，这里会启动一个定时器或订阅来确认状态
        return True
    else:
        print(f"【Joint】停止所有关节指令发送失败，错误码: {result}")
        return False


    
def get_speed(joint_id: int) -> float:
    """获取指定关节的当前速度"""
    result = comm.send_msg("GET_JOINT_SPEED", {"joint_id": joint_id})
    if isinstance(result, float):
        return result
    else:
        print(f"获取关节速度失败，错误码: {result}")
        return -1.0  

