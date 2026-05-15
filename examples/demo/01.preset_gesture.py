import time
import logging
from ghand import (
    GHand,
    CommType,
    GestureType,
    execute_gesture,
    configure_logging
)

# Configure SDK logging (shows connection state, warnings, errors)
# configure_logging(level=logging.INFO)


def main():
    """主执行函数，演示如何执行预设手势。"""
    print("***** 枭尧灵巧手 SDK - 预设手势功能演示 *****\n")
    hand = GHand()
    connected = hand.open(CommType.ETHERCAT, "auto")

    try:
        if not connected:
            print("[扫描结束] 未能连接到灵巧手。")
            return

        print("\n--- 设备已就绪，将开始依次演示预设手势 ---\n")

        # 定义要演示的手势列表
        gesture_demo = [
            GestureType.OPEN_HAND,
            GestureType.FIST,
            GestureType.OK,
            GestureType.THUMBS_UP,
            GestureType.SIX_SIGN,
        ]

        # 循环执行手势动作
        gesture_cycle = 0
        max_cycles = 0  # 设置循环次数，可以根据需要调整，0表示无限循环

        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break

            print(f"\n--- 第 {gesture_cycle} 轮手势演示开始 ---")

            # 按顺序演示所有手势
            for i, gesture in enumerate(gesture_demo, 1):
                print(f"演示{i}: [{gesture.value}]")

                if not execute_gesture(hand, gesture, speed=100, torque=100):
                    print(f"{gesture.value} 动作失败，终止演示")
                    hand.close()
                    return
                # time.sleep(1)

            print(f"\n--- 第 {gesture_cycle} 轮手势演示结束 ---\n")

            # 提示信息
            if max_cycles == 0:
                print("按 Ctrl+C 停止演示并退出程序\n")

    except KeyboardInterrupt:
        print("程序被用户中断。")
    except Exception as e:
        print(f"[严重错误] {e}")
    finally:
        hand.close()
        time.sleep(0.5)
        print("演示结束，断开连接")


if __name__ == "__main__":
    main()
