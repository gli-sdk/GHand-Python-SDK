# examples/get_joint_speed.py (已按新风格重构)

import sys
import os
import time
import math
from xiaoyao import hand, joint, common
from xiaoyao._internal.ethercat_client import auto_connect_to_hand

def rad_to_deg(rad):
    """一个简单的辅助函数，将弧度转换为度。"""
    return rad * 180.0 / math.pi

def main():
    """主执行函数，实时获取并显示关节速度。"""
    print("***** 枭尧灵巧手 SDK - 实时关节速度监控 *****\n")

    try:
        if not auto_connect_to_hand():
            print("\n[扫描结束] 未能连接到灵巧手。请检查设备电源和网线连接。")
            return

        if not hand.start_pdo_communication():
            print("启动高速运行模式(OP)失败，程序终止。")
            return

        print("\n--- 开始实时获取关节速度 (按 Ctrl+C 退出) ---")
        print("每秒更新一次。将显示所有关节的速度 (单位: °/s)。\n")
        
        while True:
            all_joints = joint.get_all_joints()

            if all_joints:
                # 清晰地格式化输出
                print(f"--- 更新于: {time.strftime('%H:%M:%S')} ---")
                for joint_info in all_joints:
                    # common.JOINT_NAMES 是一个包含关节名称的列表
                    joint_name = common.JOINT_NAMES[joint_info.joint_id]
                    speed_deg = rad_to_deg(joint_info.speed)
                    # 使用 f-string 进行对齐和格式化
                    print(f"  关节 {joint_name:<8s} : {speed_deg:8.2f} °/s")
                print("-" * 40) # 分隔符
            else:
                # 初始几帧可能为空，这很正常
                print("等待数据...")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n程序被用户中断。")
    except Exception as e:
        print(f"\n[严重错误] {e}")
    finally:
        print("\n--- 任务结束，断开连接 ---")
        hand.close_device()

if __name__ == "__main__":
    main()