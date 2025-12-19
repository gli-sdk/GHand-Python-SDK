import time
import math
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId

# 创建所有关节列表，角度应设为预设值
joints = []

def open_hand(hand, speed = 100, torque = 100):
     
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(0), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(0), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(0), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(0), speed=speed, torque=torque))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(0), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(0), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(0), speed=speed, torque=torque))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(0), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(0), speed=speed, torque=torque))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(0), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(0), speed=speed, torque=torque))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(0), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(0), speed=speed, torque=torque))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("手部张开指令发送成功")
    else:
        print("手部张开指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    return result

def make_fist(hand, speed = 100, torque = 100):
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(2), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(2), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(2), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(2), speed=speed, torque=torque))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(2), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(2), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(2), speed=speed, torque=torque))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(2), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(2), speed=speed, torque=torque))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(2), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(2), speed=speed, torque=torque))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(2), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(2), speed=speed, torque=torque))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("握拳指令发送成功")
    else:
        print("握拳指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    return result

def make_ok(hand, speed = 100, torque = 100):
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(4), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(4), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(4), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(4), speed=speed, torque=torque))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(4), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(4), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(4), speed=speed, torque=torque))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(4), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(4), speed=speed, torque=torque))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(4), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(4), speed=speed, torque=torque))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(4), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(4), speed=speed, torque=torque))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("OK手势指令发送成功")
    else:
        print("OK手势指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
        
    return result

def thumbs_up(hand, speed = 100, torque = 100):
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(6), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(6), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(6), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(6), speed=speed, torque=torque))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(6), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(6), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(6), speed=speed, torque=torque))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(6), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(6), speed=speed, torque=torque))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(6), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(6), speed=speed, torque=torque))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(6), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(6), speed=speed, torque=torque))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("竖大拇指指令发送成功")
    else:
        print("竖大拇指指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    return result

def make_six_sign(hand, speed = 100, torque = 100):
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(8), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(8), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_SWING,angle=math.radians(8), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(8), speed=speed, torque=torque))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(8), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(8), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(8), speed=speed, torque=torque))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(8), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(8), speed=speed, torque=torque))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(8), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(8), speed=speed, torque=torque))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(8), speed=speed, torque=torque))
    joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(8), speed=speed, torque=torque))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("比666指令发送成功")
    else:
        print("比666指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
        
    return result

def main():
    """主执行函数，演示如何执行预设手势。"""
    print("***** 枭尧灵巧手 SDK - 预设手势功能演示 *****\n")
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT,  "auto")
    try:
        if not connected:
            print("\n[扫描结束] 未能连接到灵巧手。")
            return
        
        print("\n--- 设备已就绪，将开始依次演示预设手势 ---\n")

        # 循环执行手势动作
        gesture_cycle = 0
        max_cycles = 0  # 设置循环次数，可以根据需要调整，0表示无限循环
        
        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break
                
            print(f"\n--- 第 {gesture_cycle} 轮手势演示开始 ---")
            
            print("演示1: [张开所有手指]")
            if not open_hand(hand):
                print("打开手部失败，终止演示")
                hand.close()
                return
            time.sleep(3)

            print("演示2: [握拳]")
            if not make_fist(hand):
                print("握拳动作失败，终止演示")
                hand.close()
                return
            time.sleep(3)

            print("演示3: [OK 手势]")
            if not make_ok(hand):
                print("OK手势失败，终止演示")
                hand.close()
                return
            time.sleep(3)

            print("演示4: [竖大拇指]")
            if not thumbs_up(hand):
                print("竖大拇指动作失败，终止演示")
                hand.close()
                return
            time.sleep(3)

            print("演示5: [六抓握]")
            if not make_six_sign(hand):
                print("比666手势失败，终止演示")
                hand.close()
                return
            time.sleep(3)

            print("恢复: [张开所有手指]")
            if not open_hand(hand):
                print("最后打开手部失败")
            time.sleep(5)
            
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
