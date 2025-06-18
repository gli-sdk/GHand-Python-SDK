# tip.py
from . import comm
from .common import RobotError

# --- 外部可调用的函数 ---

def set_posture(tip_id: int, x: float, y: float, z: float, tx: float, ty: float, tz: float) -> int:
    """
    设置指定指尖在机器人坐标系中的精确姿态。
    姿态由三维位置 (x, y, z) 和三维方向 (tx, ty, tz) 共同定义。
    """
    print(f"【Tip】正在为指尖ID {tip_id} 设置姿态...")
    posture_data = {'tip_id': tip_id, 'x': x, 'y': y, 'z': z, 'tx': tx, 'ty': ty, 'tz': tz}
    result = comm.send_msg("SET_TIP_POSTURE", posture_data)

    if result == RobotError.NO_ERROR.value:
        print(f"【Tip】指尖ID {tip_id} 姿态设置指令发送成功。")
    else:
        print(f"【Tip】指尖ID {tip_id} 姿态设置指令发送失败，错误码: {result}")
    return result

def set_all_tips_posture(tip_targets: list) -> int:
    """
    为多个指尖设置其在机器人坐标系中的精确姿态。
    """
    print(f"【Tip】正在为 {len(tip_targets)} 个指尖设置姿态...")
    result = comm.send_msg("SET_ALL_TIPS_POSTURE", tip_targets)
    
    if result == RobotError.NO_ERROR.value:
        print("【Tip】所有指尖姿态设置指令发送成功。")
    else:
        print(f"【Tip】所有指尖姿态设置指令发送失败，错误码: {result}")
    return result

def sub_tip_position(callback) -> int:
    """
    订阅所有指尖位置数据的实时更新。当有新位置数据可用时，系统将定期调用提供的回调函数。
    """
    print("【Tip】正在订阅指尖位置数据...")
    subscription_id = comm.subscribe("tip_position_stream", callback)

    if subscription_id > 0:
        print(f"【Tip】指尖位置数据订阅成功，订阅ID: {subscription_id}")
    else:
        print("【Tip】指尖位置数据订阅失败。")
    return subscription_id

def unsub_tip_position(subscription_id: int) -> bool:
    """
    取消指定ID的指尖位置数据订阅。
    """
    print(f"【Tip】正在取消订阅ID为 {subscription_id} 的指尖位置数据...")
    success = comm.unsubscribe(subscription_id)

    if success:
        print(f"【Tip】订阅ID {subscription_id} 已成功取消。")
    else:
        print(f"【Tip】取消订阅ID {subscription_id} 失败。")
    return success