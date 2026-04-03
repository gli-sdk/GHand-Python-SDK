"""
在线碰撞检测示例

演示如何连接真实硬件并进行碰撞检测。
"""
import time
import math
import logging
from xiaoyao import configure_logging, CollisionCheckError
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId

# 配置日志
configure_logging(level=logging.INFO)

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
        hand.set_safety_margin(0.3)  # 0.3mm
        print("[OK] 安全边距已设置为 0.3mm\n")

        # 测试1：移动到安全姿态
        print("--- 测试1：移动到安全姿态 ---")
        joints1 = [
            Joint(id=JointId.THUMB_PIP, angle=math.radians(66), speed=100, torque=100),
            Joint(id=JointId.THUMB_SWING, angle=math.radians(52), speed=100, torque=100),
            Joint(id=JointId.THUMB_ROTATION,angle=math.radians(0),speed=100,torque=100,),
            Joint(id=JointId.FF_PIP, angle=math.radians(30), speed=100, torque=100),
            Joint(id=JointId.FF_MCP, angle=math.radians(70), speed=100, torque=100),
        ]
        success = hand.move_safe_joints(joints1)
        if success:
            print("[OK] 移动成功")
            time.sleep(2)

        # 显示当前状态
        current_joints = hand.get_joints()
        print(f"当前角度：拇指PIP={math.degrees(current_joints[JointId.THUMB_PIP.value].angle):.1f}°")
        print(
            f"当前角度：拇指SWING={math.degrees(current_joints[JointId.THUMB_SWING.value].angle):.1f}°"
        )
        print(
            f"当前角度：拇指ROTATION={math.degrees(current_joints[JointId.THUMB_ROTATION.value].angle):.1f}°"
        )
        print(
            f"当前角度：食指PIP={math.degrees(current_joints[JointId.FF_PIP.value].angle):.1f}°"
        )
        print(
            f"当前角度：食指MCP={math.degrees(current_joints[JointId.FF_MCP.value].angle):.1f}°"
        )

        print()

        # 测试2：尝试可能导致碰撞的姿态
        print("--- 测试2：测试碰撞规避 ---")
        joints2 = [
            Joint(id=JointId.THUMB_PIP, angle=math.radians(70), speed=100, torque=100),
            Joint(id=JointId.THUMB_SWING, angle=math.radians(52), speed=100, torque=100),
            Joint(id=JointId.THUMB_ROTATION,angle=math.radians(-10),speed=100,torque=100,),
            Joint(id=JointId.FF_PIP, angle=math.radians(70), speed=100, torque=100),
            Joint(id=JointId.FF_MCP, angle=math.radians(70), speed=100, torque=100),
        ]

        print("目标：拇指和食指弯曲90度")
        success = hand.move_safe_joints(joints2)
        if success:
            print(f"当前角度：拇指PIP={math.degrees(current_joints[JointId.THUMB_PIP.value].angle):.1f}°")
            print(
                f"当前角度：拇指SWING={math.degrees(current_joints[JointId.THUMB_SWING.value].angle):.1f}°"
            )
            print(
                f"当前角度：拇指ROTATION={math.degrees(current_joints[JointId.THUMB_ROTATION.value].angle):.1f}°"
            )
            print(
                f"当前角度：食指PIP={math.degrees(current_joints[JointId.FF_PIP.value].angle):.1f}°"
            )
            print(
                f"当前角度：食指MCP={math.degrees(current_joints[JointId.FF_MCP.value].angle):.1f}°"
            )

        print()
        print("===== 演示完成 =====")

    except CollisionCheckError as e:
        print(f"\n[ERROR] 碰撞检测错误: {e.reason}")

    except Exception as e:
        print(f"\n[ERROR] 错误: {type(e).__name__}: {e}")

    finally:
        hand.close()
        print("\n设备已断开连接")


if __name__ == "__main__":
    main()
