# examples/do_custom_sequence.py

import sys
import os
import time
import math

# 导入 hand, joint, 和 common 模块
from xiaoyao import hand, joint, common

# 导入连接和启动函数
from xiaoyao._internal.ethercat_client import auto_connect_to_hand, start_pdo_communication

def create_joint_targets(target_angles_rad: dict, target_speed_rad_s: float = 1.0) -> list:
    """
    一个辅助函数，用于根据目标角度字典创建 JointInfo 列表。
    """
    targets = []
    for joint_id, angle_rad in target_angles_rad.items():
        info = common.JointInfo()
        info.joint_id = joint_id
        info.angle = angle_rad  # 角度
        info.speed = target_speed_rad_s  # 速度
        info.torque = 0.0  # 在位置模式下，力矩通常设为0，表示不限制
        targets.append(info)
    return targets

def main():
    """主执行函数，演示如何通过控制关节来自定义一个“握拳再张开”的序列。"""
    print("***** 枭尧灵巧手 SDK - 自定义关节序列演示 *****\n")

    # --- 步骤 1: 定义自定义姿态 ---
    # 定义13个主动关节的目标角度 (单位: 弧度)。
    # 注意: 这些角度值是示例，实际最佳值需要根据物理手进行调试。
    # math.pi / 2 约等于 90 度。

    # “握拳”姿态: 所有手指弯曲
    # 我们只定义需要移动的关节，未定义的关节将保持原位或由固件默认处理。
    fist_angles_rad = {
        # 拇指 (假设ID 0-3)
        0: math.radians(45),  # 拇指旋转
        1: math.radians(90),  # 拇指弯曲
        2: math.radians(90),  # 拇指弯曲
        # 食指 (假设ID 4-6)
        4: math.radians(90),
        5: math.radians(90),
        # 中指 (假设ID 7-9)
        7: math.radians(90),
        8: math.radians(90),
        # 无名指 (假设ID 10-12)
        10: math.radians(90),
        11: math.radians(90),
        # 小拇指 (假设ID 13-15, 但主动关节只有13个)
        # 这里需要根据实际的主动关节ID进行调整。假设主动关节ID为0-12。
        # 以下是一个更符合13个主动关节的假设：
    }
    # 假设13个主动关节ID为 0 到 12
    fist_angles_rad_13 = {i: math.radians(90) for i in range(13)}
    fist_angles_rad_13[0] = math.radians(10) # 拇指旋转角度小一些

    # “张开”姿态: 所有关节回到零点位置
    open_angles_rad_13 = {i: 0.0 for i in range(13)}


    try:
        # --- 步骤 2: 连接和初始化 ---
        if not auto_connect_to_hand():
            return

        if not start_pdo_communication():
            return

        print("\n--- 设备已就绪，开始执行自定义的“握拳-保持-张开”序列 ---\n")
        
        # --- 步骤 3: 执行序列 ---

        # 动作1: 执行自定义“握拳”
        print("动作1: 正在发送 [自定义握拳] 的关节目标...")
        fist_targets = create_joint_targets(fist_angles_rad_13, target_speed_rad_s=2.0)
        error = joint.set_joint(fist_targets)
        if error != common.HandError.NO_ERROR:
            print(f"  -> 发送指令失败，错误码: {error.name}")
            return
        
        print("      -> 等待动作完成 (保持2秒)...")
        time.sleep(2)

        # 动作2: 执行自定义“张开”
        print("动作2: 正在发送 [自定义张开] 的关节目标...")
        open_targets = create_joint_targets(open_angles_rad_13, target_speed_rad_s=2.5)
        error = joint.set_joint(open_targets)
        if error != common.HandError.NO_ERROR:
            print(f"  -> 发送指令失败，错误码: {error.name}")
            return

        print("      -> 等待动作完成...")
        time.sleep(2)

        print("\n[成功] 自定义序列执行完毕！")

    except KeyboardInterrupt:
        print("\n\n程序被用户中断。")
        # 紧急停止所有关节
        print("正在发送急停指令...")
        joint.stop_all_joints()
    except Exception as e:
        print(f"\n[严重错误] {e}")
    finally:
        print("\n--- 任务结束，断开连接 ---")
        hand.close_device()


if __name__ == "__main__":
    main()