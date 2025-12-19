import time
import math
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId

grab_tightly = {
    JointId.THUMB_PIP: math.radians(50),
    JointId.THUMB_MCP: math.radians(40),
    JointId.THUMB_SWING: math.radians(30),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(59),
    JointId.FF_MCP: math.radians(69),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(60),
    JointId.MF_MCP: math.radians(56),
    JointId.RF_PIP: math.radians(60),
    JointId.RF_MCP: math.radians(54),
    JointId.LF_PIP: math.radians(62),
    JointId.LF_MCP: math.radians(64),
}

grab_loosely = {
    JointId.THUMB_PIP: math.radians(22),
    JointId.THUMB_MCP: math.radians(32),
    JointId.THUMB_SWING: math.radians(30),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(19),
    JointId.FF_MCP: math.radians(32),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(27),
    JointId.MF_MCP: math.radians(29),
    JointId.RF_PIP: math.radians(37),
    JointId.RF_MCP: math.radians(13),
    JointId.LF_PIP: math.radians(30),
    JointId.LF_MCP: math.radians(22),
}

open_hand = {
    # 全部手指都在零位
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

def grab(hand):
    joints = Joint.create_joint_positions(grab_tightly)
    result =  hand.move_joints(joints)
    return result

def hand_zero(hand):
    joints = Joint.create_joint_positions(open_hand)
    result =  hand.move_joints(joints)
    return result

def main():
    print("***** 枭尧灵巧手 SDK - 抓取功能演示 *****\n")
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT,  "auto")
    try:
        if not connected:
            print("\n[扫描结束] 未能连接到灵巧手。")
            return        
        print("\n--- 设备已就绪，将开始抓取功能演示 ---\n")

        # 循环执行手势动作
        gesture_cycle = 0
        max_cycles = 0  # 设置循环次数，可以根据需要调整，0表示无限循环
        
        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break
                
            print(f"\n--- 第 {gesture_cycle} 轮功能演示开始 ---")

            if not grab(hand):
                print(f"第 {gesture_cycle} 轮演示中的抓取动作执行失败")
                break
            time.sleep(5)

            if not hand_zero(hand):
                print(f"第 {gesture_cycle} 轮演示中的复位动作执行失败")
                break
            time.sleep(5)
            
            print(f"--- 第 {gesture_cycle} 轮功能演示结束 ---\n")
            
            # 提示信息
            if max_cycles == 0:
                print("按 Ctrl+C 停止演示并退出程序\n")
    except KeyboardInterrupt:
        print("\n\n程序被用户中断。")
    except Exception as e:
        print(f"\n[严重错误] {e}")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n--- 演示结束，断开连接 ---")

if __name__ == "__main__":
    main()