# get_basic_info.py
import sys
import time
from xiaoyao_sdk_mock import XiaoyaoClient # 导入模拟SDK客户端

print("--- 示例 1: 获取手部所有基本信息 ---")

# 实例化SDK客户端
client = XiaoyaoClient()

# 尝试连接设备
if not client.connect():
    print("无法连接到设备，退出示例。")
    sys.exit(1)

try:
    hand_info = client.hand.get_all_basic_info()
    if hand_info:
        print("\n手部基本信息:")
        for key, value in hand_info.items():
            print(f"  {key}: {value}")
    else:
        print("获取手部基本信息失败。")
except Exception as e:
    print(f"获取信息时发生错误: {e}")
finally:
    # 断开设备连接
    client.disconnect()
    print("\n示例 1 运行完毕!!!")