# get_joint_speed.py
import sys
import time
import math # 用于判断NaN
from xiaoyao_sdk_mock import XiaoyaoClient # 导入模拟SDK客户端

print("--- 示例 5: 获取关节当前运行速度 ---")

# 实例化SDK客户端
client = XiaoyaoClient()

# 尝试连接设备
if not client.connect():
    print("无法连接到设备，退出示例。")
    sys.exit(1)

try:
    joint_id_to_query = 0 # 假设查询关节ID 0 的速度
    print(f"尝试获取关节ID {joint_id_to_query} 的当前运行速度...")
    joint_speed = client.joint.get_speed(joint_id=joint_id_to_query)
    
    if not math.isnan(joint_speed): # 检查是否返回了有效的浮点数
        print(f"关节ID {joint_id_to_query} 的当前运行速度: {joint_speed:.2f} 弧度/秒")
    else:
        print("获取关节速度失败或返回无效值。")
except Exception as e:
    print(f"获取关节速度时发生错误: {e}")
finally:
    # 断开设备连接
    client.disconnect()
    print("\n示例 5 运行完毕。")