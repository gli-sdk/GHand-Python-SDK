import time
import math
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId

joint_positions_1 = {
    JointId.THUMB_PIP: math.radians(20),
    JointId.THUMB_MCP: math.radians(55),
    JointId.THUMB_SWING: math.radians(60),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.LF_PIP: math.radians(56),
    JointId.LF_MCP: math.radians(28),
    # 其他关节保持零位
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
}

joint_positions_2 = {
    JointId.THUMB_PIP: math.radians(19),
    JointId.THUMB_MCP: math.radians(41.25),
    JointId.THUMB_SWING: math.radians(45),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.RF_PIP: math.radians(67),
    JointId.RF_MCP: math.radians(39),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
}

joint_positions_3 = {
    JointId.THUMB_PIP: math.radians(17),
    JointId.THUMB_MCP: math.radians(27.5),
    JointId.THUMB_SWING: math.radians(30),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.MF_PIP: math.radians(40),
    JointId.MF_MCP: math.radians(57),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

joint_positions_4 = {
    JointId.THUMB_PIP: math.radians(13),
    JointId.THUMB_MCP: math.radians(13.5),
    JointId.THUMB_SWING: math.radians(15),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(51),
    JointId.FF_MCP: math.radians(46),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
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

fist = {
    JointId.THUMB_PIP: math.radians(70),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(75),
    JointId.FF_MCP: math.radians(70),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

open_ff = {
    JointId.THUMB_PIP: math.radians(70),
    JointId.THUMB_MCP: math.radians(55),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    # 张开食指
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    # 其他关节保持零位
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

open_mf = {
    JointId.THUMB_PIP: math.radians(70),
    JointId.THUMB_MCP: math.radians(55),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    # 张开食指
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

open_rf = {
    JointId.THUMB_PIP: math.radians(70),
    JointId.THUMB_MCP: math.radians(55),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    # 张开无名指
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    # 其他关节保持零位
    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

open_lf = {
    JointId.THUMB_PIP: math.radians(70),
    JointId.THUMB_MCP: math.radians(55),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    # 张开小拇指
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

ff_swing_neg = {
    JointId.THUMB_PIP: math.radians(70),
    JointId.THUMB_MCP: math.radians(55),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    # 侧摆-15度
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(-15),
    
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

ff_swing_pos = {
    JointId.THUMB_PIP: math.radians(70),
    JointId.THUMB_MCP: math.radians(55),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    # 侧摆15度
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(15),

    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

joint_positions_5 = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),

    JointId.FF_PIP: math.radians(75),
    JointId.FF_MCP: math.radians(70),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),

    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

joint_positions_6 = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),

    JointId.FF_PIP: math.radians(75),
    JointId.FF_MCP: math.radians(70),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),

    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

joint_positions_7 = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),

    JointId.FF_PIP: math.radians(75),
    JointId.FF_MCP: math.radians(70),
    JointId.FF_SWING: math.radians(0),

    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),
    JointId.RF_PIP: math.radians(0),
    JointId.RF_MCP: math.radians(0),
    JointId.LF_PIP: math.radians(0),
    JointId.LF_MCP: math.radians(0),
}

joint_positions_8 = {
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

    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

joint_positions_9 = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(0),
    JointId.MF_MCP: math.radians(0),

    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

joint_positions_10 = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    JointId.FF_PIP: math.radians(0),
    JointId.FF_MCP: math.radians(0),
    JointId.FF_SWING: math.radians(0),

    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

joint_positions_11 = {
    JointId.THUMB_PIP: math.radians(0),
    JointId.THUMB_MCP: math.radians(0),
    JointId.THUMB_SWING: math.radians(0),
    JointId.THUMB_ROTATION: math.radians(0),
    
    JointId.FF_PIP: math.radians(75),
    JointId.FF_MCP: math.radians(70),
    JointId.FF_SWING: math.radians(0),
    JointId.MF_PIP: math.radians(75),
    JointId.MF_MCP: math.radians(70),
    JointId.RF_PIP: math.radians(75),
    JointId.RF_MCP: math.radians(70),
    JointId.LF_PIP: math.radians(75),
    JointId.LF_MCP: math.radians(70),
}

def thumb_touch_tp(hand):
    # 1: 拇指和小指指尖触碰，其他手指保持在零位
    
    joints = Joint.create_joint_positions(joint_positions_1)
    hand.move_joints(joints)
    time.sleep(1)

    # 2: 拇指和无名指指尖触碰，其他手指保持在零位
    joints = Joint.create_joint_positions(joint_positions_2)
    hand.move_joints(joints)
    time.sleep(1)

    # 3: 拇指和中指指尖触碰，其他手指保持在零位
    joints = Joint.create_joint_positions(joint_positions_3)
    hand.move_joints(joints)
    time.sleep(1)

    # 4: 拇指和食指指尖触碰，其他手指保持在零位
    joints = Joint.create_joint_positions(joint_positions_4)
    hand.move_joints(joints)
    time.sleep(1)

    # 5: 全部手指保持在零位
    joints = Joint.create_joint_positions(open_hand)
    hand.move_joints(joints)
    time.sleep(1)

def fist_then_open(hand):
    # 1: 握拳动作 
    joints = Joint.create_joint_positions(fist)
    hand.move_joints(joints)
    time.sleep(1)

    # 2: 张开手掌动作
    joints = Joint.create_joint_positions(open_hand)
    hand.move_joints(joints)
    time.sleep(1)


def seq_open_finger(hand):

    # 1: 握拳动作
    joints = Joint.create_joint_positions(fist)
    hand.move_joints(joints)
    time.sleep(1)

    # 2: 张开食指动作
    joints = Joint.create_joint_positions(open_ff)
    hand.move_joints(joints)
    time.sleep(1)

    # 3: 张开中指动作
    joints = Joint.create_joint_positions(open_mf)
    hand.move_joints(joints)
    time.sleep(1)

    # 4: 张开无名指动作
    joints = Joint.create_joint_positions(open_rf)
    hand.move_joints(joints)
    time.sleep(1)

    # 5: 张开小拇指动作
    joints = Joint.create_joint_positions(open_lf)
    hand.move_joints(joints)
    time.sleep(1)

    # 5: 张开大拇指动作
    joints = Joint.create_joint_positions(open_hand)
    hand.move_joints(joints)
    time.sleep(1)

def swing_ff(hand):
    joints = Joint.create_joint_positions(open_ff)
    hand.move_joints(joints)
    time.sleep(1)

    for i in range(2):
        joints = Joint.create_joint_positions(ff_swing_neg)
        hand.move_joints(joints)
        time.sleep(1)

        joints = Joint.create_joint_positions(ff_swing_pos)
        hand.move_joints(joints)
        time.sleep(1)

    joints = Joint.create_joint_positions(open_ff)
    hand.move_joints(joints)
    time.sleep(1)

def flex_finger_movement(hand):

    joints = Joint.create_joint_positions(joint_positions_8)
    hand.move_joints(joints)
    time.sleep(1)

    joints = Joint.create_joint_positions(joint_positions_9)
    hand.move_joints(joints)
    time.sleep(1)

    joints = Joint.create_joint_positions(joint_positions_10)
    hand.move_joints(joints)
    time.sleep(1)

    joints = Joint.create_joint_positions(joint_positions_11)
    hand.move_joints(joints)
    time.sleep(1) 

    joints = Joint.create_joint_positions(joint_positions_5)
    hand.move_joints(joints)
    time.sleep(1)

    joints = Joint.create_joint_positions(joint_positions_6)
    hand.move_joints(joints)
    time.sleep(1)

    joints = Joint.create_joint_positions(joint_positions_7)
    hand.move_joints(joints)
    time.sleep(1)

    joints = Joint.create_joint_positions(open_hand)
    hand.move_joints(joints)
    time.sleep(1)

def make_ok(hand):
    joints = Joint.create_joint_positions(joint_positions_4)
    hand.move_joints(joints)
    time.sleep(1)



def first_action(hand):
    thumb_touch_tp(hand)
    
    for i in range(2):
        fist_then_open(hand)

def second_action(hand):
    seq_open_finger(hand)
    swing_ff(hand)

    for i in range(4):
        flex_finger_movement(hand)

    make_ok(hand)



def main():
    print("***** 枭尧灵巧手 SDK - 手势舞功能演示 *****\n")
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, "auto")
    try:
        if not connected:
            print("\n[扫描结束] 未能连接到灵巧手。")
            return        
        print("\n--- 设备已就绪，将开始手势舞功能演示 ---\n")

        # 循环执行手势动作
        gesture_cycle = 0
        max_cycles = 0  # 设置循环次数，可以根据需要调整，0表示无限循环
        
        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break
                
            print(f"\n--- 第 {gesture_cycle} 轮手势演示开始 ---")
            
            first_action(hand)

            second_action(hand)
            
            print(f"--- 第 {gesture_cycle} 轮手势演示结束 ---\n")
            
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