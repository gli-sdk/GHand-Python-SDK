import time
import math
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId


def get_temprature(data):
    return data["temp"]


def process_data(data):
    temp = get_temprature(data)
    print(temp)
    for key in ["thumb1", "thumb2"]:
        print(f"{key}: {data[key]}")


def main():
    hand = DexHand()

    test_angle = 0
    test_speed = 1000
    test_torque = 30


    connected = hand.open(CommType.ETHERCAT, r"\Device\NPF_{22F450DC-244F-47FA-A538-CBD0142495BE}")
    if not connected:
        print("connect failed")
        return
    ver = hand.get_firmware_version()
    hand_name = hand.get_device_name()
    hand_hw_ver = hand.get_hardware_version()
    mfr_mark = hand.get_manufacturer_mark()
    prod_code = hand.get_product_code()
    rev_num = hand.get_revision_number()
    serial_num = hand.get_serial_number()
    hand_type = hand.get_hand_type()
    print(f"hand name:{hand_name};H/W ver:{hand_hw_ver};ver: {ver};hand_type: {hand_type.value};")
    print(f"Mfr Mark:{mfr_mark};Prod code:{prod_code};Rev num:{rev_num};Serial num:{int.from_bytes(serial_num, 'little')};")

    try:
        while True:

            joints = []
            
            
            # 拇指关节
            joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))        #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))        #角度范围为:0~55(度)
            joints.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))      #角度范围为:0~90(度)
            joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))   #角度范围为:0~90(度)
            
            # 食指关节
            joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(test_angle), speed=test_speed, torque=test_torque)) #角度范围为:-15~15(度)
            
            # 中指关节
            joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))   #角度范围为:0~70(度)
            
            # 无名指关节
            joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))   #角度范围为:0~70(度)
            
            # 小指关节
            joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(test_angle), speed=test_speed, torque=test_torque))   #角度范围为:0~70(度)

            hand.move_joints(joints)
            time.sleep(3)

            # 增加角度值，每次增加10度，当达到70度后重新从0度开始
            test_angle += 1
            if test_angle > 15:
                test_angle = 0

            test_speed += 500
            if test_speed > 5000:
                test_speed = 1000

            test_torque += 10  
            if test_torque > 90:
                test_torque = 30      
            
            current_joints  = hand.get_joints()
            if current_joints:
                for joint in current_joints:
                    if joint.id == JointId.FF_MCP:
                        print(f"当前FF_MCP关节状态 - 角度: {math.degrees(joint.angle):.2f} 度, 速度: {joint.speed}, 扭矩: {joint.torque}")
                        
    except KeyboardInterrupt:
        print("\n用户中断程序,正在关闭手部连接...")
    finally:
        hand.close()
        time.sleep(0.5)
        print("hand is closed")


if __name__ == "__main__":
    main()
