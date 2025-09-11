import time
import math
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId
from do_gesture_dance import create_joint_positions

clap_hand = {
    JointId.THUMB_PIP: math.radians(15),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(30),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(15),
    JointId.FF_MCP: math.radians(19),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(20),
    JointId.RF_PIP: math.radians(19),
    JointId.RF_MCP: math.radians(0),
    JointId.LF_PIP: math.radians(14),
    JointId.LF_MCP: math.radians(6),    
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

def hand_clap(hand):
    joints = create_joint_positions(clap_hand)
    hand.move_joints(joints)
    time.sleep(5)

def hand_zero(hand):
    joints = create_joint_positions(open_hand)
    hand.move_joints(joints)
    time.sleep(5)

def main():
    print("***** 枭尧灵巧手 SDK - 拍功能演示 *****\n")
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, r"\Device\NPF_{22F450DC-244F-47FA-A538-CBD0142495BE}")
    try:
        if not connected:
            print("\n[扫描结束] 未能连接到灵巧手。")
            return        
        print("\n--- 设备已就绪，将开始拍功能演示 ---\n")

        # 循环执行手势动作
        gesture_cycle = 0
        max_cycles = 0  # 设置循环次数，可以根据需要调整，0表示无限循环
        
        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break
                
            print(f"\n--- 第 {gesture_cycle} 轮功能演示开始 ---")

            hand_clap(hand)

            hand_zero(hand)
            
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