"""
安全边距设置示例

演示如何设置和使用安全边距来提高碰撞检测的灵敏度。
"""
import math
import logging
from xiaoyao import configure_logging
from xiaoyao.dexhand import DexHand, Joint, JointId

configure_logging(level=logging.INFO)

def main():
    print("===== 安全边距设置示例 =====\n")

    hand = DexHand()

    # 示例1：无边距（精确接触）
    print("--- 示例1：无边距检测 ---")
    hand.set_safety_margin(0.0)
    print("安全边距：0mm（仅在接触时检测碰撞）")

    joints = [
        Joint(id=JointId.THUMB_PIP, angle=math.radians(45), speed=100, torque=100),
        Joint(id=JointId.FF_PIP, angle=math.radians(45), speed=100, torque=100),
    ]
    print(f"目标角度：拇指={math.degrees(joints[0].angle):.0f}°, 食指={math.degrees(joints[1].angle):.0f}°")

    # 注意：实际移动需要连接硬件
    # hand.move_safe_joints(joints)

    print()

    # 示例2：中等边距（推荐）
    print("--- 示例2：中等安全边距 ---")
    hand.set_safety_margin(0.5)
    print("安全边距：1.0mm（在距离1mm时触发碰撞）")
    print("适用场景：一般操作，平衡安全性和灵活性")

    print()

    # 示例3：最大边距（保守）
    print("--- 示例3：最大安全边距 ---")
    hand.set_safety_margin(1.0)
    print("安全边距：2.0mm（在距离2mm时触发碰撞）")
    print("适用场景：精密操作，需要额外的安全余量")

    print()

    # 示例4：动态调整边距
    print("--- 示例4：动态调整安全边距 ---")
    print("可以根据操作类型动态调整安全边距：")

    # 粗略操作
    hand.set_safety_margin(0.3)
    print("粗略操作：0.6mm")

    # 精密操作
    hand.set_safety_margin(0.8)
    print("精密操作：1.6mm")

    print()
    print("===== 演示完成 =====")
    print("\n提示：")
    print("- 安全边距值范围：0.0-1.0")
    print("- 实际安全距离 = 边距值 × 2mm")
    print("- 边距越大，碰撞检测越保守")
    print("- 建议从0.5开始，根据实际需求调整")


if __name__ == "__main__":
    main()
