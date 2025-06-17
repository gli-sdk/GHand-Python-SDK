# get_tactile_data.py
import sys
import time
import numpy as np # 用于更好地显示数组
from xiaoyao_sdk_mock import XiaoyaoClient # 导入模拟SDK客户端

print("--- 示例 3: 获取指尖触觉传感器数据 ---")

# 实例化SDK客户端
client = XiaoyaoClient()

# 尝试连接设备
if not client.connect():
    print("无法连接到设备，退出示例。")
    sys.exit(1)

try:
    # 假设查询传感器ID为 0 的触觉数据
    sensor_id_to_query = 0
    print(f"尝试获取指尖传感器 {sensor_id_to_query} 的触觉数据...")
    tactile_data = client.tactile.get_data(sensor_id=sensor_id_to_query)
    
    if tactile_data:
        print(f"指尖传感器 {sensor_id_to_query} 的触觉数据 (3x3矩阵):")
        # 使用numpy更好地格式化输出二维数组
        print(np.array(tactile_data))
    else:
        print(f"获取指尖传感器 {sensor_id_to_query} 触觉数据失败或无数据。")
except Exception as e:
    print(f"获取触觉数据时发生错误: {e}")
finally:
    # 断开设备连接
    client.disconnect()
    print("\n示例 3 运行完毕。")