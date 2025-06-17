# set_joint_angle.py
import sys
import time
import math # 用于弧度转换
from xiaoyao_sdk_mock import XiaoyaoClient, RobotError # 导入模拟SDK客户端和枚举

print("--- 示例 4: 设置单个关节角度 ---")

# 实例化SDK客户端
client = XiaoyaoClient()

# 尝试连接设备
if not client.connect():
    print("无法连接到设备，退出示例。")
    sys.exit(1)

try:
    joint_id_to_set = 0
    target_angle_degrees = 90.0 # 目标角度，度
    target_angle_radians = math.radians(target_angle_degrees) # 转换为弧度
    set_speed = 0.5 # 设定运动速度

    print(f"尝试设置关节ID {joint_id_to_set} 的角度为 {target_angle_degrees} 度 (即 {target_angle_radians:.2f} 弧度)，速度为 {set_speed} 弧度/秒...")
    
    # 构建单个关节的目标字典列表
    joint_targets = [
        {'joint_id': joint_id_to_set, 'target_angle': target_angle_radians, 'speed': set_speed}
    ]
    
    result_code = client.joint.set_angle(joint_targets)
    
    if result_code == RobotError.NO_ERROR.value:
        print("关节角度设置指令发送成功。")
        # 在实际SDK中，这里可以等待运动完成或检查状态
    elif result_code == RobotError.INVALID_PARAMETER.value:
        print(f"关节角度设置失败: 参数无效。错误码: {result_code}")
    else:
        print(f"关节角度设置失败，错误码: {result_code}")
except Exception as e:
    print(f"设置关节角度时发生错误: {e}")
finally:
    # 断开设备连接
    client.disconnect()
    print("\n示例 4 运行完毕。")