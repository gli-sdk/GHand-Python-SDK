# examples/do_preset_gesture.py。

import sys
import os
import time
from xiaoyao import hand, common
from xiaoyao._internal.ethercat_client import auto_connect_to_hand

def main():
    """主执行函数，演示如何执行预设手势。"""
    print("***** 枭尧灵巧手 SDK - 预设手势功能演示 *****\n")

    try:
        if not auto_connect_to_hand():
            print("\n[扫描结束] 未能连接到灵巧手。请检查设备电源和网线连接。")
            return

        if not hand.start_pdo_communication():
            print("启动高速运行模式(OP)失败，程序终止。")
            return

        print("\n--- 设备已就绪，将开始依次演示预设手势 ---\n")
        time.sleep(1) 
        
        print("演示1: [张开所有手指]")
        hand.do_preset_gesture(common.GestureType.OPEN_ALL_FINGERS)
        time.sleep(3) 

        print("演示2: [握拳]")
        hand.do_preset_gesture(common.GestureType.FIST)
        time.sleep(3)

        print("演示3: [OK 手势]")
        hand.do_preset_gesture(common.GestureType.OK)
        time.sleep(3)

        print("演示4: [竖大拇指]")
        hand.do_preset_gesture(common.GestureType.THUMBS_UP)
        time.sleep(3)

        print("演示5: [六抓握]")
        hand.do_preset_gesture(common.GestureType.GRIP_SIX)
        time.sleep(3)

        print("恢复: [张开所有手指]")
        hand.do_preset_gesture(common.GestureType.OPEN_ALL_FINGERS)
        time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n程序被用户中断。")
    except Exception as e:
        print(f"\n[严重错误] {e}")
    finally:
        print("\n--- 演示结束，断开连接 ---")
        hand.close_device()


if __name__ == "__main__":
    main()