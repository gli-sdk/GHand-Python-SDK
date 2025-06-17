# set_ok_gesture.py
import sys
import time
from xiaoyao_sdk_mock import XiaoyaoClient, GestureType, RobotError  # 导入模拟SDK客户端和枚举

print("--- 示例 2: 设置手部预设手势 (比OK) ---")

# 实例化SDK客户端
client = XiaoyaoClient()

# 尝试连接设备
if not client.connect():
    print("无法连接到设备，退出示例。")
    sys.exit(1)

try:
    print("尝试设置手势为 'OK'...")
    result_code = client.hand.set_preset_gesture(GestureType.OK_SIGN)

    if result_code == GestureType.OK_SIGN.value:
        print(f"成功设置手势为 'OK' ({result_code})。")
    elif result_code == RobotError.INVALID_PARAMETER.value:
        print(f"设置手势失败: 参数无效。错误码: {result_code}")
    elif result_code == RobotError.ACTION_FAILED.value:
        print(f"设置手势失败: 动作执行失败或被终止。错误码: {result_code}")
    else:
        print(f"设置手势失败，错误码: {result_code}")
except Exception as e:
    print(f"设置手势时发生错误: {e}")
finally:
    # 断开设备连接
    client.disconnect()
    print("\n示例 2 运行完毕!")
