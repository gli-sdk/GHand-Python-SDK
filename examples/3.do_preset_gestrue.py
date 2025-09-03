import time
import math
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId

# 创建所有关节列表，角度应设为预设值
joints = []

def open_hand(hand):
     
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(0), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(0), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(0), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(0), speed=5000.0, torque=90.0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(0), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(0), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(0), speed=5000.0, torque=90.0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(0), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(0), speed=5000.0, torque=90.0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(0), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(0), speed=5000.0, torque=90.0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(0), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(0), speed=5000.0, torque=90.0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("手部张开指令发送成功")
    else:
        print("手部张开指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    return result

def make_fist(hand):
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(2), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(2), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(2), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(2), speed=5000.0, torque=90.0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(2), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(2), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(2), speed=5000.0, torque=90.0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(2), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(2), speed=5000.0, torque=90.0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(2), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(2), speed=5000.0, torque=90.0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(2), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(2), speed=5000.0, torque=90.0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("握拳指令发送成功")
    else:
        print("握拳指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    return result

def make_ok(hand):
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(4), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(4), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(4), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(4), speed=5000.0, torque=90.0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(4), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(4), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(4), speed=5000.0, torque=90.0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(4), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(4), speed=5000.0, torque=90.0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(4), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(4), speed=5000.0, torque=90.0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(4), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(4), speed=5000.0, torque=90.0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("OK手势指令发送成功")
    else:
        print("OK手势指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
        
    return result

def thumbs_up(hand):
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(6), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(6), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(6), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(6), speed=5000.0, torque=90.0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(6), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(6), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(6), speed=5000.0, torque=90.0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(6), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(6), speed=5000.0, torque=90.0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(6), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(6), speed=5000.0, torque=90.0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(6), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(6), speed=5000.0, torque=90.0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("竖大拇指指令发送成功")
    else:
        print("竖大拇指指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    return result

def make_six_sign(hand):
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(8), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(8), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(8), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(8), speed=5000.0, torque=90.0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(8), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(8), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(8), speed=5000.0, torque=90.0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(8), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(8), speed=5000.0, torque=90.0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(8), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(8), speed=5000.0, torque=90.0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(8), speed=5000.0, torque=90.0))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(8), speed=5000.0, torque=90.0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("比666指令发送成功")
    else:
        print("比666指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
        
    return result

def test_finger(hand):
    """食指摇摆动作"""
    joints = []
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(75), speed=5000, torque=90))        #角度范围为:0~75(度)

    result = hand.move_joints(joints)
    if result:
        print("指令1发送成功")
    else:
        print("指令1发送失败")
    time.sleep(5)

    current_joints  = hand.get_joints()
    if current_joints:
        for joint in current_joints:
            if joint.id == JointId.FF_MCP:
                print(f"当前关节状态 - 角度: {math.degrees(joint.angle):.2f} 度, 速度: {joint.speed}, 扭矩: {joint.torque}")

    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(0), speed=5000, torque=90))        #角度范围为:0~75(度)
    result = hand.move_joints(joints)
    if result:
        print("指令2发送成功")
    else:
        print("指令2发送失败")
    time.sleep(5)

    current_joints  = hand.get_joints()
    if current_joints:
        for joint in current_joints:
            if joint.id == JointId.FF_MCP:
                print(f"当前关节状态 - 角度: {math.degrees(joint.angle):.2f} 度, 速度: {joint.speed}, 扭矩: {joint.torque}")
    

    return result

def main():
    """主执行函数，演示如何执行预设手势。"""
    print("***** 枭尧灵巧手 SDK - 预设手势功能演示 *****\n")
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, r"\Device\NPF_{22F450DC-244F-47FA-A538-CBD0142495BE}")
    try:
        if not connected:
            print("\n[扫描结束] 未能连接到灵巧手。")
            return
        
        print("\n--- 设备已就绪，将开始依次演示预设手势 ---\n")
        time.sleep(3)

        # 循环执行手势动作
        gesture_cycle = 0
        max_cycles = 0  # 设置循环次数，可以根据需要调整，0表示无限循环
        
        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break
                
            print(f"\n--- 第 {gesture_cycle} 轮手势演示开始 ---")
            
            # print("演示1: [张开所有手指]")
            # open_hand(hand)
            # time.sleep(3)

            # print("演示2: [握拳]")
            # make_fist(hand)
            # time.sleep(3)

            # print("演示3: [OK 手势]")
            # make_ok(hand)
            # time.sleep(3)

            # print("演示4: [竖大拇指]")
            # thumbs_up(hand)
            # time.sleep(3)

            # print("演示5: [六抓握]")
            # make_six_sign(hand)
            # time.sleep(3)

            print("演示6: [测试]")
            test_finger(hand)

            # print("恢复: [张开所有手指]")
            # open_hand(hand)
            # time.sleep(5)
            
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
