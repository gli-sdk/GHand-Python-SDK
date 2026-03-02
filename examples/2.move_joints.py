import time
import math
import logging
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId
from xiaoyao.error import State, ErrorCode

logger = logging.getLogger("xiaoyao")

def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT,  "auto")      

    try:
        if not connected:
            logger.error("connect failed")
            return

        logger.info("connect successful!")
        joints = []

        # 循环执行手指动作
        gesture_cycle = 0
        max_cycles = 0  # 设置循环次数，可以根据需要调整，0表示无限循环
        
        while True:
            gesture_cycle += 1
            if max_cycles > 0 and gesture_cycle > max_cycles:
                break

            logger.info(f"\n--- 第 {gesture_cycle} 轮手指运动开始 ---")

            # 获取手部状态信息
            hand_info = hand.get_hand_info()
            logger.info(f"手部状态: {hand_info.state.name}, 温度: {hand_info.temp}°C")

            # 检查手部是否有错误
            if hand_info.state in [State.ABNORMAL_RUNNING, State.PROTECTIVE_STOP] or hand_info.error != ErrorCode.NO_ERROR:
                logger.error("检测到手部错误，进一步检查关节...")

                # 检查具体是哪个关节有问题
                joints_status = hand.get_joints()
                error_joints = [j for j in joints_status if j.state in [State.ABNORMAL_RUNNING, State.PROTECTIVE_STOP] or j.error != ErrorCode.NO_ERROR]
                if error_joints:
                    logger.error(f"发现 {len(error_joints)} 个关节有错误：")
                    for joint in error_joints:
                        logger.error(f"  {JointId(joint.id).name}: state={joint.state.name}, error={joint.error}")
                logger.error("请清除故障后重试")
                break

            joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(30), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(30), speed=100, torque=100))   #角度范围为:0~55(度)
            joints.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(15), speed=100, torque=100))   #角度范围为:0~90(度)
            joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(15), speed=100, torque=100))   #角度范围为:0~90(度)
            joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(50), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(50), speed=100, torque=100))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(0), speed=100, torque=100))   #角度范围为:-15~15(度)
            joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(40), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(40), speed=100, torque=100))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(50), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(50), speed=100, torque=100))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(50), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(50), speed=100, torque=100))   #角度范围为:0~70(度)

            result = hand.move_joints(joints)
            if result:
                logger.info("指令1发送成功")
                time.sleep(0.7)
                current_joints  = hand.get_joints()
                if current_joints:
                    for joint in current_joints:
                        logger.info(
                            f"  {JointId(joint.id).name:<15}- state:{joint.state},\terror:{joint.error},\t角度: {math.degrees(joint.angle):.2f} 度,\t速度: {joint.speed},\t扭矩: {joint.torque}"
                        )
            else:
                logger.error("指令1发送失败")
                break
            joints.append(Joint(id=JointId.THUMB_PIP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.THUMB_MCP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~55(度)
            joints.append(Joint(id=JointId.THUMB_SWING, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~90(度)
            joints.append(Joint(id=JointId.THUMB_ROTATION, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~90(度)
            joints.append(Joint(id=JointId.FF_PIP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.FF_MCP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.FF_SWING, angle=math.radians(0), speed=100, torque=100))   #角度范围为:-15~15(度)
            joints.append(Joint(id=JointId.MF_PIP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.MF_MCP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.RF_PIP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.RF_MCP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~70(度)
            joints.append(Joint(id=JointId.LF_PIP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~75(度)
            joints.append(Joint(id=JointId.LF_MCP, angle=math.radians(0), speed=100, torque=100))   #角度范围为:0~70(度)

            # 检查关节是否有错误
            joints_status = hand.get_joints()
            error_joints = [j for j in joints_status if j.state in [State.ABNORMAL_RUNNING, State.PROTECTIVE_STOP] or j.error != ErrorCode.NO_ERROR]
            if error_joints:
                logger.error("检测到关节错误，停止运动！")
                for joint in error_joints:
                    logger.error(f"  {JointId(joint.id).name}: state={joint.state.name}, error={joint.error}")
                logger.error("请清除故障后重试")
                break

            result = hand.move_joints(joints)
            if result:
                logger.info("指令2发送成功")
                time.sleep(1)
                current_joints  = hand.get_joints()
                for joint in current_joints:
                    logger.info(f"  {JointId(joint.id).name:<15}- 角度: {math.degrees(joint.angle):.2f} 度,\t速度: {joint.speed},\t扭矩: {joint.torque}")
            else:
                logger.error("指令2发送失败")
                break

            print(f"--- 第 {gesture_cycle} 轮手指运动结束 ---\n")
            # 提示信息
            if max_cycles == 0:
                print("按 Ctrl+C 停止演示并退出程序\n")          

    except KeyboardInterrupt:
        hand.close()
        logger.info("程序被用户中断。")
    except Exception as e:
        logger.error(f"[严重错误] {e}")
    finally:
        hand.close()
        time.sleep(0.5)
        print("\n--- 演示结束，断开连接 ---")

if __name__ == "__main__":
    main()
