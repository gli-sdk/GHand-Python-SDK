# examples/get_basic_info.py。

import sys
import os
import time
from xiaoyao._internal.ethercat_client import auto_connect_to_hand
from xiaoyao.hand import hand

def main():
    try:
        # --- 第1步: 自动连接 ---
        if not auto_connect_to_hand():
            print("\n[扫描结束] 未能通过任何适配器连接到灵巧手。请检查：")
            print("1. 灵巧手是否已通电？")
            print("2. 网线是否已正确连接到电脑和灵巧手？")
            return

        static_info = hand.get_all_basic_info()
        print(f"  设备ID: {static_info.get('device_id', 'N/A')}")
        print(f"  软件版本: {static_info.get('software_version', 'N/A')}")
        print(f"  手部类型: {static_info.get('hand_type', 'N/A')}")

        if not hand.start_pdo_communication():
            print("启动运行模式失败。")
            return

        for i in range(10): # 循环获取10次
            realtime_data = hand.get_realtime_data()
            if realtime_data:
                # 假设 get_realtime_data 返回的字典中包含这些键
                state_code = realtime_data.get('operation_state_code')
                temp = realtime_data.get('current_temperature')
                print(f"  实时状态码: {state_code}, 温度: {temp}°C")
            time.sleep(0.2)
            
    except Exception as e:
        print(f"\n[严重错误] {e}")
    finally:
        print("\n--- 任务结束，断开连接 ---")
        hand.close_device()

if __name__ == "__main__":
    main()