# examples/do_gesture_sequence.py。

import sys
import os
import time
from xiaoyao import hand, common
from xiaoyao._internal.ethercat_client import auto_connect_to_hand

def main():
    """主执行函数，演示一个“握拳再张开”的自定义手势序列。"""
    print("***** 枭尧灵巧手 SDK - 自定义手势序列演示 *****\n")

    try:
        if not auto_connect_to_hand():
            print("\n[扫描结束] 未能连接到灵巧手。请检查设备电源和网线连接。")
            return

        if not hand.start_pdo_communication():
            print("启动高速运行模式(OP)失败，程序终止。")
            return

        print("\n--- 设备已就绪，开始执行“握拳-保持-张开”序列 ---\n")
        
        
        print("动作1: 正在执行 [握拳]...")
        hand.do_preset_gesture(common.GestureType.FIST)
        
        print("      -> 保持握拳状态 2 秒...")
        time.sleep(2)

        print("动作2: 正在执行 [张开所有手指]...")
        hand.do_preset_gesture(common.GestureType.OPEN_ALL_FINGERS)
        
        time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n程序被用户中断。")
    except Exception as e:
        print(f"\n[严重错误] {e}")
    finally:
        print("\n--- 序列演示结束，断开连接 ---")
        hand.close_device()


if __name__ == "__main__":
    main()
