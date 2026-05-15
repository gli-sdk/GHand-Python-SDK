"""
示例：连接两只灵巧手

现在 EthercatClient 已经移除了单例模式，可以直接创建多个 DexHand 实例
来连接多个设备。
"""
import time
import math
import logging
from ghand.dexhand import DexHand, CommType, Joint, JointId
from ghand import configure_logging

# Configure SDK logging
configure_logging(level=logging.INFO)


def main():
    """连接并控制两只灵巧手"""

    # 创建并连接第一只手
    print("正在连接第一只灵巧手...")
    hand1 = DexHand()
    connected1 = hand1.open(
        CommType.ETHERCAT, "\\Device\\NPF_{B1A930DF-53B0-483A-ABB8-6C3146F1FC2D}"
    )
    if not connected1:
        print("第一只手连接失败")
        return

        # 创建并连接第二只手
    print("正在连接第二只灵巧手...")
    hand2 = DexHand()
    connected2 = hand2.open(
        CommType.ETHERCAT, "\\Device\\NPF_{5539C758-F9F9-482D-B319-1760CE5958A6}"
    )
    if not connected2:
        print("第二只手连接失败")
        hand1.close()
        return

    # logger.info("两只灵巧手连接成功！")

    # 获取第一只手的信息
    try:
        ver1 = hand1.get_firmware_version()
        name1 = hand1.get_device_name()
        hw_ver1 = hand1.get_hardware_version()
        serial1 = hand1.get_serial_number()
        type1 = hand1.get_hand_type()
        print(
            f"第一只手 - 名称: {name1}, 硬件版本: {hw_ver1}, "
            f"固件版本: {ver1}, 类型: {type1.value}, "
            f"序列号: {serial1}"
        )
    except Exception as e:
        print(f"获取第一只手信息失败: {e}")

    # 获取第二只手的信息
    try:
        ver2 = hand2.get_firmware_version()
        name2 = hand2.get_device_name()
        hw_ver2 = hand2.get_hardware_version()
        serial2 = hand2.get_serial_number()
        type2 = hand2.get_hand_type()
        print(
            f"第二只手 - 名称: {name2}, 硬件版本: {hw_ver2}, "
            f"固件版本: {ver2}, 类型: {type2.value}, "
            f"序列号: {serial2}"
        )
    except Exception as e:
        print(f"获取第二只手信息失败: {e}")

    print("灵巧手已就绪，可以进行控制操作")

    # 在这里添加你的控制逻辑...
    # 例如：
    # hand1.move_joints([...])
    # hand2.move_joints([...])
    joints1 = []

    joints1.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~75(度)
    joints1.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(50), speed=100, torque=100))   #角度范围为:0~55(度)
    joints1.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(20), speed=100, torque=100))   #角度范围为:0~90(度)
    joints1.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~90(度)
    joints1.append(Joint(id=JointId.FF_PIP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~75(度)
    joints1.append(Joint(id=JointId.FF_MCP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~70(度)

    result = hand1.move_joints(joints1)
    if result:
        print("指令1发送成功")
        time.sleep(0.7)
        current_joints  = hand1.get_joints()
        if current_joints:
            joint =current_joints[2]
            print(
                f"  {JointId(joint.id).name:<15}- 角度: {math.degrees(joint.angle):.2f} 度,\t速度: {joint.speed},\t扭矩: {joint.torque}"
            )

    joints1.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~75(度)
    joints1.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~55(度)
    joints1.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(20), speed=100, torque=100))   #角度范围为:0~90(度)
    joints1.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~90(度)
    joints1.append(Joint(id=JointId.FF_PIP, angle=math.radians(50), speed=100, torque=100))   #角度范围为:0~75(度)
    joints1.append(Joint(id=JointId.FF_MCP, angle=math.radians(50), speed=100, torque=100))   #角度范围为:0~70(度)

    result = hand2.move_joints(joints1)
    if result:
        print("指令1发送成功")
        time.sleep(0.7)
        current_joints2  = hand2.get_joints()
        if current_joints2:
            joint =current_joints2[7]
            print(
                f"  {JointId(joint.id).name:<15}- 角度: {math.degrees(joint.angle):.2f} 度,\t速度: {joint.speed},\t扭矩: {joint.torque}"
            )

    # 程序结束时关闭连接
    # 注意：也可以使用上下文管理器来自动关闭
    print("关闭所有连接...")
    hand1.close()
    hand2.close()
    print("完成")


if __name__ == "__main__":
    main()
