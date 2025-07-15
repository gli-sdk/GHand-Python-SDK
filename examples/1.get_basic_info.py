# examples/get_basic_info.py。

import sys
import os
import time
from xiaoyao.hand import hand
from xiaoyao._internal.ethercat_client import auto_connect_to_hand, start_pdo_communication

def main():
    try:
        if not auto_connect_to_hand():
            return
        static_info = hand.get_all_basic_info()
        print(f"  序列号: {static_info.get('serial_number', 'N/A')}")
        print(f"  软件版本: {static_info.get('software_version', 'N/A')}")
        print(f"  手部类型: {static_info.get('hand_type', 'N/A')}")

        if not start_pdo_communication():
            print("启动运行模式失败。")
            hand.close_device()
            return

        for i in range(5):
            current_state = hand.get_operation_state()
            current_temp = hand.get_temperature()
            print(f"  第 {i+1}/5 次更新 -> 实时状态: {current_state.name}, 当前温度: {current_temp}°C")
            time.sleep(0.5)
            
    except Exception as e:
        print(f"\n[程序执行期间发生严重错误] {e}")
    finally:
        print("\n--- 任务结束，正在断开与设备的连接 ---")
        hand.close_device()

if __name__ == "__main__":
    main()