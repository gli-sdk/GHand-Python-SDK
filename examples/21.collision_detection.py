"""
在线碰撞检测示例

演示如何将碰撞检测与关节运动解耦使用：
1. 调用 check_collision() 检测目标姿态
2. 检查结果并打印角度对比
3. 调用 move_joints() 执行运动（或在碰撞时自主选择是否运动）
"""
import time
import math
import logging
from xiaoyao import configure_logging
from xiaoyao.converter import joints_to_nparray, nparray_to_joints
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId

# 配置日志
configure_logging(level=logging.INFO)

# 默认速度和力矩
DEFAULT_SPEED = 100
DEFAULT_TORQUE = 100


def main():
    print("===== 枭尧灵巧手 SDK - 在线碰撞检测演示 =====\n")

    hand = DexHand()

    try:
        print("正在连接设备...")
        connected = hand.open(CommType.ETHERCAT, "auto")

        if not connected:
            print("[ERROR] 设备连接失败")
            return

        print("[OK] 设备连接成功\n")

        # 设置安全边距
        hand.set_safety_margin(1)
        print("[OK] 安全边距已设置为 0.2mm\n")

        # 测试：尝试可能导致碰撞的姿态
        print("--- 测试：检测碰撞并规避 ---")
        target_joints = [
            Joint(id=JointId.THUMB_PIP,angle=math.radians(66),speed=DEFAULT_SPEED, torque=DEFAULT_TORQUE ),
            Joint(id=JointId.THUMB_SWING, angle=math.radians(52),speed=DEFAULT_SPEED, torque=DEFAULT_TORQUE),
            Joint(id=JointId.THUMB_ROTATION,angle=math.radians(-10),speed=DEFAULT_SPEED,torque=DEFAULT_TORQUE),
            Joint(id=JointId.FF_PIP,angle=math.radians(70),speed=DEFAULT_SPEED,torque=DEFAULT_TORQUE),
            Joint(id=JointId.FF_MCP, angle=math.radians(70), speed=DEFAULT_SPEED, torque=DEFAULT_TORQUE),
        ]

        # 第一步：进行碰撞检测（不执行运动）
        result = hand.check_collision(target_joints)

        if result.has_collision:
            print("检测到碰撞！")
            collision_info = " <-> ".join(result.collision_pairs or ["unknown"])
            print(f"碰撞对: {collision_info}\n")

            # 打印目标角度和安全角度的对比
            target_angles = joints_to_nparray(target_joints,hand.get_joints())
            print("=== 碰撞检测 - 角度对比 (单位: 度) ===")
            print("-" * 70)
            print(f"{'关节名称':<18} {'目标角度':<12} {'安全角度':<12}")
            print("-" * 70)
            for i in range(18):
                if JointId(i) in (JointId.THUMB_DIP, JointId.FF_DIP, JointId.MF_DIP, JointId.RF_DIP, JointId.LF_DIP):
                    continue
                joint_name = JointId(i).name
                target_deg = math.degrees(target_angles[i])
                safe_deg = math.degrees(result.safe_angles[i])
                print(f"{joint_name:<25} {target_deg:<12.2f} {safe_deg:<12.2f}")
            print("-" * 70)
            print()

            # 第二步：使用安全角度运动
            safe_joints = nparray_to_joints(
                result.safe_angles,
                speed=DEFAULT_SPEED,
                torque=DEFAULT_TORQUE,
            )
            print("使用安全角度执行运动...")
            success = hand.move_joints(safe_joints)
        else:
            print("未检测到碰撞，直接使用目标角度运动。")
            success = hand.move_joints(target_joints)

        if success:
            time.sleep(2)

        # 获取当前关节状态并打印
        current_joints = hand.get_joints()
        print(f"当前角度：拇指PIP={math.degrees(current_joints[JointId.THUMB_PIP.value].angle):.1f}°")
        print(f"当前角度：拇指SWING={math.degrees(current_joints[JointId.THUMB_SWING.value].angle):.1f}°")
        print(f"当前角度：拇指ROTATION={math.degrees(current_joints[JointId.THUMB_ROTATION.value].angle):.1f}°")
        print(f"当前角度：食指PIP={math.degrees(current_joints[JointId.FF_PIP.value].angle):.1f}°")
        print(f"当前角度：食指MCP={math.degrees(current_joints[JointId.FF_MCP.value].angle):.1f}°")

        print("\n===== 演示完成 =====")

    except Exception as e:
        print(f"\n[ERROR] 错误: {type(e).__name__}: {e}")

    finally:
        hand.close()
        print("\n设备已断开连接")


if __name__ == "__main__":
    main()
