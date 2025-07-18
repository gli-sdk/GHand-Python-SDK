# examples/set_light_effect.py。

import sys
import os
import time
from xiaoyao._internal.ethercat_client import auto_connect_to_hand
from xiaoyao.hand import hand

def main():
    print("***** 枭尧灵巧手 SDK - 灯光控制演示 *****\n")
    
    if not auto_connect_to_hand():
        print("\n[扫描结束] 未能连接到灵巧手。请检查设备电源和网线连接。")
        return
    
    try:
        print("效果1: 蓝色常亮 (持续3秒)...")
        hand.set_light(mode=0, color=(0, 0, 255))
        time.sleep(3)

        print("效果2: 绿色闪烁 (持续5秒)...")
        hand.set_light(mode=1, color=(0, 255, 0), frequency_ms=500)
        time.sleep(5)

        print("效果3: 红色呼吸 (持续5秒)...")
        hand.set_light(mode=2, color=(255, 0, 0), frequency_ms=2000)
        time.sleep(5)

    except Exception as e:
        print(f"\n测试过程中发生未知错误: {e}")
    finally:
        print("\n演示结束，断开连接。")
        hand.close_device()


if __name__ == "__main__":
    main()