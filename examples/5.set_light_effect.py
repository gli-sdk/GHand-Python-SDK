# examples/set_light_effect.py。

import time
from xiaoyao.dexhand import DexHand, CommType


def main():
    print("***** 枭尧灵巧手 SDK - 灯光控制演示 *****\n")

    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, "auto")
    if not connected:
        print("connect failed")
        hand.close()
        return

    print("效果1: 蓝色常亮 (持续3秒)...")
    hand.set_light(color=(0, 0, 255), effect='on', T=3000)
    time.sleep(3)

    print("效果2: 绿色闪烁 (持续5秒)...")
    hand.set_light(color=(0, 255, 0), effect='flash', T=500)
    time.sleep(5)

    print("效果3: 红色呼吸 (持续5秒)...")
    hand.set_light(color=(255, 0, 0), effect='breath', T=2000)
    time.sleep(5)
    hand.close()


if __name__ == "__main__":
    main()
