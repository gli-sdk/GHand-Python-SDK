import time
import math
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId


def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT,  "auto")      

    try:
        if not connected:
            print("connect failed")
            return
        
        print("connect successful!")
        joints = []

        # 循环执行手指动作
        gesture_cycle = 0
        max_cycles = 0  # 设置循环次数，可以根据需要调整，0表示无限循环
        
        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break
                
            print(f"\n--- 第 {gesture_cycle} 轮手指运动开始 ---")
            joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(30), speed=10, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(30), speed=10, torque=90))   #角度范围为:0~55(度)
            joints.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~90(度)
            joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~90(度)
            joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(5), speed=10, torque=90))   #角度范围为:-15~15(度)
            joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(5), speed=10, torque=90))   #角度范围为:0~70(度)

            result = hand.move_joints(joints)
            if result:
                print("指令1发送成功")
                current_joints  = hand.get_joints()
                if current_joints:
                    for joint in current_joints:
                        if joint.id == JointId.FF_MCP:
                            print(f"当前关节状态 - 角度: {math.degrees(joint.angle):.2f} 度, 速度: {joint.speed}, 扭矩: {joint.torque}")
            else:
                print("指令1发送失败")
            time.sleep(0.5)

            joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(0), speed=1000, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(0), speed=1000, torque=90))   #角度范围为:0~55(度)
            joints.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~90(度)
            joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~90(度)
            joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(0), speed=50, torque=90))   #角度范围为:-15~15(度)
            joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(0), speed=50, torque=90))   #角度范围为:0~70(度)

            result = hand.move_joints(joints)
            if result:
                print("指令2发送成功")
                current_joints  = hand.get_joints()
                if current_joints:
                    for joint in current_joints:
                        if joint.id == JointId.FF_MCP:
                            print(f"当前关节状态 - 角度: {math.degrees(joint.angle):.2f} 度, 速度: {joint.speed}, 扭矩: {joint.torque}")
            else:
                print("指令2发送失败")
            time.sleep(0.5)

            print(f"--- 第 {gesture_cycle} 轮手指运动结束 ---\n")
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

 

    hand.close()

if __name__ == "__main__":
    main()
