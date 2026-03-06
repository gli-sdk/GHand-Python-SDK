import time
import math
import logging
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId
from xiaoyao import configure_logging

# Configure SDK logging (shows connection state, warnings, errors)
configure_logging(level=logging.INFO)


def main():
    hand = DexHand()

    # 为每个关节创建独立的参数字典
    joint_params = {
        JointId.THUMB_PIP: {"angle": 0, "speed": 0, "torque": 0},
        JointId.THUMB_MCP: {"angle": 0, "speed": 0, "torque": 0},
        JointId.THUMB_SWING: {"angle": 0, "speed": 0, "torque": 0},
        JointId.THUMB_ROTATION: {"angle": 0, "speed": 0, "torque": 0},
        JointId.FF_PIP: {"angle": 0, "speed": 0, "torque": 0},
        JointId.FF_MCP: {"angle": 0, "speed": 0, "torque": 0},
        JointId.FF_SWING: {"angle": 0, "speed": 0, "torque": 0},
        JointId.MF_PIP: {"angle": 0, "speed": 0, "torque": 0},
        JointId.MF_MCP: {"angle": 0, "speed": 0, "torque": 0},
        JointId.RF_PIP: {"angle": 0, "speed": 0, "torque": 0},
        JointId.RF_MCP: {"angle": 0, "speed": 0, "torque": 0},
        JointId.LF_PIP: {"angle": 0, "speed": 0, "torque": 0},
        JointId.LF_MCP: {"angle": 0, "speed": 0, "torque": 0},
    }


    connected = hand.open(CommType.ETHERCAT, "auto")
    if not connected:
        print("connect failed")
        return
    ver = hand.get_firmware_version()
    hand_name = hand.get_device_name()
    hand_hw_ver = hand.get_hardware_version()
    serial_num = hand.get_serial_number()
    hand_type = hand.get_hand_type()
    print(f"hand name:{hand_name};H/W ver:{hand_hw_ver};ver: {ver};hand_type: {hand_type.value};")
    print(f"Serial num:{int.from_bytes(serial_num, 'little')};")

    try:
        while True:
            # 在每次循环开始时，重置所有关节参数为默认值
            for joint_id in joint_params:
                joint_params[joint_id]["angle"] = 0
                joint_params[joint_id]["speed"] = 0
                joint_params[joint_id]["torque"] = 0
            
            # 记录已设置的关节
            set_joints = set()
            
            # 获取用户输入
            print("\n请为关节设置参数 (输入空行结束输入):")
            print("关节ID列表:")
            print("1:THUMB_PIP, 2:THUMB_MCP, 3:THUMB_SWING, 4:THUMB_ROTATION")
            print("6:FF_PIP, 7:FF_MCP, 8:FF_SWING")
            print("10:MF_PIP, 11:MF_MCP")
            print("13:RF_PIP, 14:RF_MCP")
            print("16:LF_PIP, 17:LF_MCP")
            
            try:
                while True:
                    # 显示已设置的关节及其参数
                    if set_joints:
                        print("已设置的关节:")
                        for joint_id in set_joints:
                            params = joint_params[joint_id]
                            print(f"  {JointId(joint_id).name}: 角度={params['angle']}, 速度={params['speed']}, 扭矩={params['torque']}")

                    joint_input = input("请输入关节ID (或直接按回车结束输入): ").strip()
                    if not joint_input:
                        break
                    
                    if joint_input.isdigit():
                        joint_id = int(joint_input)
                        if joint_id in joint_params:
                            set_joints.add(joint_id)
                            current_params = joint_params[joint_id]
                            print(f"为关节 {JointId(joint_id).name} 设置参数:")
                            angle_input = input(f"角度值 [{current_params['angle']}]: ").strip()
                            speed_input = input(f"速度值 [{current_params['speed']}]: ").strip()
                            torque_input = input(f"扭矩值 [{current_params['torque']}]: ").strip()
                            
                            # 更新选定关节的参数
                            if angle_input:
                                joint_params[joint_id]["angle"] = float(angle_input)
                            if speed_input:
                                joint_params[joint_id]["speed"] = int(speed_input)
                            if torque_input:
                                joint_params[joint_id]["torque"] = int(torque_input)
                        else:
                            print("无效的关节ID")
                    else:
                        print("请输入有效的关节ID数字")
            except ValueError:
                print("输入格式错误，跳过本次设置")

            joints = []
            
            # 为每个关节创建Joint对象
            for joint_id, params in joint_params.items():
                joints.append(Joint(
                    id=joint_id,
                    angle=math.radians(params["angle"]),
                    speed=params["speed"],
                    torque=params["torque"]
                ))

            result = hand.move_joints(joints)
            if result:
                hand.get_joints()
            else:
                break
    except KeyboardInterrupt:
        print("\n用户中断程序,正在关闭手部连接...")
    finally:
        hand.close()
        time.sleep(0.5)
        print("hand is closed")


if __name__ == "__main__":
    main()
