# examples/do_preset_gesture.py。

import sys
import os
import time
from xiaoyao import hand, common
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId

def open_hand():
    
    # 创建所有关节列表，角度都设为0
    joints = []
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_DIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_PIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=0))
    joints.append(Joint(id=JointId.THUMB_SWING, angle=0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_DIP, angle=0))
    joints.append(Joint(id=JointId.FF_PIP, angle=0))
    joints.append(Joint(id=JointId.FF_MCP, angle=0))
    joints.append(Joint(id=JointId.FF_SWING, angle=0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_DIP, angle=0))
    joints.append(Joint(id=JointId.MF_PIP, angle=0))
    joints.append(Joint(id=JointId.MF_MCP, angle=0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_DIP, angle=0))
    joints.append(Joint(id=JointId.RF_PIP, angle=0))
    joints.append(Joint(id=JointId.RF_MCP, angle=0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_DIP, angle=0))
    joints.append(Joint(id=JointId.LF_PIP, angle=0))
    joints.append(Joint(id=JointId.LF_MCP, angle=0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("手部张开指令发送成功")
    else:
        print("手部张开指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    # 关闭连接
    hand.close()
    
    return result

def make_fist():
    
    # 创建所有关节列表，角度都设为0
    joints = []
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_DIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_PIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=0))
    joints.append(Joint(id=JointId.THUMB_SWING, angle=0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_DIP, angle=0))
    joints.append(Joint(id=JointId.FF_PIP, angle=0))
    joints.append(Joint(id=JointId.FF_MCP, angle=0))
    joints.append(Joint(id=JointId.FF_SWING, angle=0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_DIP, angle=0))
    joints.append(Joint(id=JointId.MF_PIP, angle=0))
    joints.append(Joint(id=JointId.MF_MCP, angle=0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_DIP, angle=0))
    joints.append(Joint(id=JointId.RF_PIP, angle=0))
    joints.append(Joint(id=JointId.RF_MCP, angle=0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_DIP, angle=0))
    joints.append(Joint(id=JointId.LF_PIP, angle=0))
    joints.append(Joint(id=JointId.LF_MCP, angle=0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("手部张开指令发送成功")
    else:
        print("手部张开指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    # 关闭连接
    hand.close()
    
    return result

def make_ok():
    
    # 创建所有关节列表，角度都设为0
    joints = []
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_DIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_PIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=0))
    joints.append(Joint(id=JointId.THUMB_SWING, angle=0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_DIP, angle=0))
    joints.append(Joint(id=JointId.FF_PIP, angle=0))
    joints.append(Joint(id=JointId.FF_MCP, angle=0))
    joints.append(Joint(id=JointId.FF_SWING, angle=0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_DIP, angle=0))
    joints.append(Joint(id=JointId.MF_PIP, angle=0))
    joints.append(Joint(id=JointId.MF_MCP, angle=0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_DIP, angle=0))
    joints.append(Joint(id=JointId.RF_PIP, angle=0))
    joints.append(Joint(id=JointId.RF_MCP, angle=0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_DIP, angle=0))
    joints.append(Joint(id=JointId.LF_PIP, angle=0))
    joints.append(Joint(id=JointId.LF_MCP, angle=0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("OK手势指令发送成功")
    else:
        print("OK手势指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    # 关闭连接
    hand.close()
    
    return result

def thumbs_up():
    
    # 创建所有关节列表，角度都设为0
    joints = []
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_DIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_PIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=0))
    joints.append(Joint(id=JointId.THUMB_SWING, angle=0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_DIP, angle=0))
    joints.append(Joint(id=JointId.FF_PIP, angle=0))
    joints.append(Joint(id=JointId.FF_MCP, angle=0))
    joints.append(Joint(id=JointId.FF_SWING, angle=0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_DIP, angle=0))
    joints.append(Joint(id=JointId.MF_PIP, angle=0))
    joints.append(Joint(id=JointId.MF_MCP, angle=0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_DIP, angle=0))
    joints.append(Joint(id=JointId.RF_PIP, angle=0))
    joints.append(Joint(id=JointId.RF_MCP, angle=0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_DIP, angle=0))
    joints.append(Joint(id=JointId.LF_PIP, angle=0))
    joints.append(Joint(id=JointId.LF_MCP, angle=0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("竖大拇指指令发送成功")
    else:
        print("竖大拇指指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    # 关闭连接
    hand.close()
    
    return result

def make_six_sign():
    
    # 创建所有关节列表，角度都设为0
    joints = []
    
    # 拇指关节
    joints.append(Joint(id=JointId.THUMB_DIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_PIP, angle=0))
    joints.append(Joint(id=JointId.THUMB_MCP, angle=0))
    joints.append(Joint(id=JointId.THUMB_SWING, angle=0))
    joints.append(Joint(id=JointId.THUMB_ROTATION, angle=0))
    
    # 食指关节
    joints.append(Joint(id=JointId.FF_DIP, angle=0))
    joints.append(Joint(id=JointId.FF_PIP, angle=0))
    joints.append(Joint(id=JointId.FF_MCP, angle=0))
    joints.append(Joint(id=JointId.FF_SWING, angle=0))
    
    # 中指关节
    joints.append(Joint(id=JointId.MF_DIP, angle=0))
    joints.append(Joint(id=JointId.MF_PIP, angle=0))
    joints.append(Joint(id=JointId.MF_MCP, angle=0))
    
    # 无名指关节
    joints.append(Joint(id=JointId.RF_DIP, angle=0))
    joints.append(Joint(id=JointId.RF_PIP, angle=0))
    joints.append(Joint(id=JointId.RF_MCP, angle=0))
    
    # 小指关节
    joints.append(Joint(id=JointId.LF_DIP, angle=0))
    joints.append(Joint(id=JointId.LF_PIP, angle=0))
    joints.append(Joint(id=JointId.LF_MCP, angle=0))
    
    # 发送关节控制指令
    result = hand.move_joints(joints)
    
    if result:
        print("比666指令发送成功")
    else:
        print("比666指令发送失败")
    
    # 等待一段时间确保动作完成
    time.sleep(2)
    
    # 关闭连接
    hand.close()
    
    return result

def main():
    """主执行函数，演示如何执行预设手势。"""
    print("***** 枭尧灵巧手 SDK - 预设手势功能演示 *****\n")
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT, r"\Device\NPF_{22F450DC-244F-47FA-A538-CBD0142495BE}")
    try:
        if not connected:
            print("\n[扫描结束] 未能连接到灵巧手。请检查设备电源和网线连接。")
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
