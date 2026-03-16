import time
import math
import logging
from xiaoyao.dexhand import DexHand, CommType, Joint, JointId

from xiaoyao import configure_logging

# Configure SDK logging (shows connection state, errors, etc.)
configure_logging(level=logging.INFO)
class TrajectoryPlanning:
    # 初始化
    def __init__(self,current_position=0.0,current_velocity=0.0,target_position=0.0,target_velocity=0.0,last_time=0.0,angle_tolerance=0.01):
        self.coeffs = [0.0,0.0,0.0,0.0] #位置曲线三次项系数[a0,a1,a2,a3]
        self.x0 = current_position #初始位置
        self.x1 = target_position #目标位置
        self.v0 = current_velocity #初始速度
        self.v1 = target_velocity #目标速度
        self.T = 0.8 #轨迹的时间间隔
        self.T = max(self.T, 0.8)  # 钳制最小值为0.8，防止烧毁电机
        self.t0=last_time #发送控制目标的上一时刻的时间
        self.planning_position=0.0 #规划的下一时刻的位置
        self.planning_velocity=0.0 #规划的下一时刻的速度
        self.angle_tolerance = angle_tolerance
        self.calculate_path_planning_coeffs()
        
    # 辅助函数向量点乘 
    def dot_product(self,vec_a,vec_b,n):
        res =0.0
        for i in range(n):
            res += vec_a[i]*vec_b[i]
        return res
    # 根据初始状态和目标状态计算轨迹曲线的系数
    def calculate_path_planning_coeffs(self):
        h = self.x1-self.x0
        self.coeffs[0]=self.x0
        self.coeffs[1]=self.v0
        self.coeffs[2]=1.0/(self.T**2)*(3.0*h-2.0*(2.0*self.v0+self.v1)*self.T)
        self.coeffs[3]=1.0/(self.T**3)*(-2.0*h+(self.v0+self.v1)*self.T)
    # 根据当前时间计算下一时刻要发送的轨迹
    def generate_planning_trajectory(self,current_time):
        # 如果时间超过规划时间，直接返回目标位置和目标速度
        if current_time - self.t0 >= self.T:
            self.planning_position = self.x1
            self.planning_velocity = self.v1
        else:
            vec_time=[1,current_time-self.t0,(current_time-self.t0)**2,(current_time-self.t0)**3]
            vec_vel_coeffs=[self.coeffs[1],2*self.coeffs[2],3*self.coeffs[3]]
            self.planning_position = self.dot_product(vec_time,self.coeffs,4)
            self.planning_velocity = self.dot_product(vec_time,vec_vel_coeffs,3)
    #判断是否抵达目标角度，容差为默认为0.01度
    def stop_judge(self):
        # 只根据位置是否到达目标容差内判断是否停止
        position_ok = abs(self.planning_position - self.x1) < self.angle_tolerance
        return position_ok

def logger_send_result(result,hand,joint_id):
    if result:
        print("指令发送成功")
        time.sleep(0.8)
        current_joints = hand.get_joints()
        print(f"当前角度: {math.degrees(current_joints[joint_id].angle):.2f} 度")
    else:
        print("指令发送失败")

# -------------------------
# 不同手指关节信息的调用方式
# THUMB_DIP = current_joints[0]
# THUMB_PIP = current_joints[1]
# THUMB_MCP = current_joints[2]
# THUMB_SWING = current_joints[3]
# THUMB_ROTATION = current_joints[4]
# FF_DIP = current_joints[5]
# FF_PIP = current_joints[6]
# FF_MCP = current_joints[7]
# FF_SWING = current_joints[8]
# MF_DIP = current_joints[9]
# MF_PIP = current_joints[10]
# MF_MCP = current_joints[11]
# RF_DIP = current_joints[12]
# RF_PIP = current_joints[13]
# RF_MCP = current_joints[14]
# LF_DIP = current_joints[15]
# LF_PIP = current_joints[16]
# LF_MCP = current_joints[17]
# -------------------------

def main():
    hand = DexHand()
    connected = hand.open(CommType.ETHERCAT,  "auto")      
    connected = True
    try:
        if not connected:
            print("connect failed")
            return
        print("connect successful!")

        # 初始化配置
        joint_id = JointId.RF_MCP #希望规划的手指关节
        desired_joint_angle=0 #deg  # 配置期望的目标角度
        send_interval = 0.001  # 发送间隔（秒），间隔越大，顿挫感越明显
        while desired_joint_angle<40:
            desired_joint_angle+=5
            # 获取所有手指的关节信息
            current_joints  = hand.get_joints() #接受到的角度数据,单位是rad
            current_positIon = math.degrees(current_joints[joint_id].angle) #获取规划的关节的角度
            # 对食指FF的MCP关节进行轨迹规划
            angle_planning = TrajectoryPlanning(current_position=current_positIon,target_position=desired_joint_angle)

            # 等采样间隔，持续发送轨迹，直至抵达目标角度
            last_send_time = 0
            current_time = 0.0
            max_timeout = angle_planning.T*3
            begin_time = time.perf_counter()
            while not angle_planning.stop_judge():
                current_time = time.perf_counter() - begin_time
                # 只在间隔时间足够时才发送新指令
                if current_time > max_timeout:
                    print("轨迹规划超时，强制退出")
                    break
                if current_time - last_send_time >= send_interval:
                    angle_planning.generate_planning_trajectory(current_time)
                    print(f" 角度:{angle_planning.planning_position:.2f}度已发送")
                    # 清空旧指令，只发送最新的
                    joints = [Joint(id=joint_id, 
                                    angle=math.radians(angle_planning.planning_position), 
                                    speed=100, 
                                    torque=100)]

                    result = hand.move_joints(joints)
                    last_send_time = current_time

        # 复位
        time.sleep(3)
        joints = []
        joints.append(Joint(id=joint_id, angle=math.radians(0), speed=100, torque=100))
        result = hand.move_joints(joints)
        logger_send_result(result,hand,joint_id)

    except KeyboardInterrupt:
        # hand.close()
        print("程序被用户中断。")
    except Exception as e:
        print(f"[严重错误] {e}")
    finally:
        # hand.close()
        time.sleep(0.5)
        print("\n--- 演示结束，断开连接 ---")

    # hand.close()

if __name__ == "__main__":
    main()
