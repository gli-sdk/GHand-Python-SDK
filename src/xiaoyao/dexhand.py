import enum
import math
import logging
from typing import Optional
from dataclasses import dataclass
from .ecatclient import EthercatClient
from .data import JointRpdo, Rpdo, Tpdo

logger = logging.getLogger("xiaoyao")

class HandType(enum.Enum):
    UNKNOWN = "unknown"
    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"


class CommType(enum.Enum):
    UNKNOWN = "unknown"
    ETHERCAT = "ethercat"
    CANFD = "canfd"
    RS485 = "rs485"


class CtrlMode(enum.Enum):
    POSITION = 0
    TORQUE = 1


class JointId(enum.IntEnum):
    THUMB_DIP = 0
    THUMB_PIP = 1
    THUMB_MCP = 2
    THUMB_SWING = 3
    THUMB_ROTATION = 4
    FF_DIP = 5
    FF_PIP = 6
    FF_MCP = 7
    FF_SWING = 8
    MF_DIP = 9
    MF_PIP = 10
    MF_MCP = 11
    RF_DIP = 12
    RF_PIP = 13
    RF_MCP = 14
    LF_DIP = 15
    LF_PIP = 16
    LF_MCP = 17

@dataclass
class Joint:
    id: int = JointId.THUMB_DIP
    angle: float = 0.0
    speed: float = 0.0
    torque: float = 0.0

    def create_joint_positions(joint_angles_dict):
        """
        根据关节角度字典创建关节列表
        
        Args:
            joint_angles_dict: 字典,键为JointId,值为角度值(弧度)
        
        Returns:
            list: Joint对象列表
        """
        joints = []
        default_speed = 100
        default_torque = 100
        
        for joint_id, angle in joint_angles_dict.items():
            joints.append(Joint(
                id=joint_id, 
                angle=angle, 
                speed=default_speed, 
                torque=default_torque
            ))
        
        return joints

class GestureType(enum.Enum):
    HAND_OPEN = "hand_open"


class DexHand(object):
    def __init__(self):
        """
        初始化灵巧手对象
        """
        self._client = EthercatClient()
        self._hand_type = HandType.UNKNOWN
        self._firmware_version = ""
        self._opened = False
        self._set_joint_limit()

    def __del__(self):
        """
        析构函数，关闭灵巧手设备连接
        """
        self.close()

    def _set_joint_limit(self):
        """
        设置关节限制参数
        """
        self._th_pip_limit = (0, math.radians(75))
        self._th_mcp_limit = (0, math.radians(75))
        self._th_swing_limit = (0, math.radians(90))
        self._th_rot_limit = (0, math.radians(90))
        self._ff_pip_limit = (0, math.radians(75))
        self._ff_mcp_limit = (0, math.radians(70))
        self._ff_swing_limit = (math.radians(-15), math.radians(15))
        self._mf_pip_limit = (0, math.radians(75))
        self._mf_mcp_limit = (0, math.radians(70))
        self._rf_pip_limit = (0, math.radians(75))
        self._rf_mcp_limit = (0, math.radians(70))
        self._lf_pip_limit = (0, math.radians(75))
        self._lf_mcp_limit = (0, math.radians(70))

    def _check_joint_limit(self, joint: Joint, limit):
        """
        检查关节角度是否超出限制范围，如果超出则设为边界值

        Args:
          joint (Joint): 关节对象
          limit: 关节限制范围

        """
        if joint.angle < limit[0]:
            joint.angle = limit[0]
        elif joint.angle > limit[1]:
            joint.angle = limit[1]
            logger.warning(f"【Joint】关节ID: {joint.id} 角度超出限制范围，已设为最大值 {math.degrees(limit[1]):.2f} 度")

    def open(self, type: CommType = CommType.ETHERCAT, id: str = "auto"):
        """
        打开灵巧手设备连接

        Args:
          type (CommType): 通信类型，默认为ETHERCAT
          id (str): 设备ID，当设置为"auto"时自动搜索设备，默认为"auto"

        Returns:
          bool: 连接成功返回True，否则返回False
        """
        if self._opened:
            return True
        if type == CommType.ETHERCAT:
            if id == "auto":
                id_list = self._client.search()
                logger.info("搜索到的ID:\n" + "\n".join([f"{id}" for id in id_list]))
                for id in id_list:
                    connected = self._client.connect(id)
                    if connected:
                        run_success = self._client.run()
                        if run_success:
                            self._opened = True
                            break
                        else:
                            # 如果run失败，断开连接并尝试下一个设备
                            self._client.disconnect()
            else:
                connected = self._client.connect(id)
                if connected:
                    run_success = self._client.run()
                    self._opened = run_success
        elif type == CommType.CANFD:
            pass
        elif type == CommType.RS485:
            pass
        return self._opened

    def close(self) -> bool:
        """
        关闭灵巧手设备连接

        Returns:
          bool: 关闭成功返回True，失败返回False
        """
        if self._opened:
            self._client.disconnect()
        return True
    
    def get_firmware_version(self):
        """
        获取灵巧手固件版本号

        Returns:
            str: 返回版本号（如："v1.0.0"）
        """
        if self._firmware_version == "":
            self._firmware_version = self._client.sdo_read(
                0x100A, 0x00).decode('utf-8')
        return self._firmware_version
    
    def get_device_name(self):
        """
        获取设备名

        Returns:
            str: 获取成功返回设备ID，失败返回空字符串""
        """
        try:
            device_name = self._client.sdo_read(0x1008, 0x00).decode('utf-8')
        except Exception:
            return ""
        return device_name
    
    def get_hardware_version(self):
        """
        获取硬件版本号

        Returns:
            str: 获取成功返回版本号（如："v1.0.0"），失败返回空字符串""
        """
        try:
            hardware_version = self._client.sdo_read(0x1009, 0x00).decode('utf-8')
        except Exception:
            return ""
        return hardware_version

    def get_serial_number(self):
        """
        获取产品序列号

        Returns:
            str: 获取成功返回产品序列号，失败返回空字符串""
        """        
        try:
            serial_number = self._client.sdo_read(0x1018, 0x04)
        except Exception:
            return ""
        return serial_number

    def fault_clearance(self) -> bool:
        """
        故障清除

        Returns:
            bool: 清除成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2002, 0x01, b'\x01')
        except Exception:
            return False
        return True

    def joint_init(self) -> bool:
        """
        关节初始化

        Returns:
            bool: 初始化成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2003, 0x01, b'\x01')
        except Exception:
            return False
        return True

    def tactile_reset(self) -> bool:
        """
        重置（清零）触觉传感器数据

        Returns:
            bool: 重置成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x01')
        except Exception:
            return False
        return True

    def stop(self) -> bool:
        """
        急停-立即停止所有关节运动

        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2007, 0x00, b'\x00')
        except Exception:
            return False
        return True

    def do_preset_gesture(self, gesture: GestureType):
        """
        执行预设手势动作

        Args:
            gesture (GestureType): 手势类型

        Returns:
            bool: 执行成功返回True，失败返回False
        """
        if gesture == GestureType.HAND_OPEN:
            try:
                self._client.sdo_write(0x2021, 0x00, b'\x01')
            except Exception:
                return False
        return True

    def get_hand_type(self) -> HandType:
        """
        获取手的类型

        Returns:
            HandType: 成功返回手的类型HandType.LEFT_HAND/HandType.RIGHT_HAND，失败返回HandType.UNKNOWN
        """
        if self._hand_type == HandType.UNKNOWN:
            try:
                type = int.from_bytes(
                    self._client.sdo_read(0x2001, 0x00), byteorder='little')
            except Exception:
                return HandType.UNKNOWN
            if type == 0x01:
                self._hand_type = HandType.LEFT_HAND
            elif type == 0x02:
                self._hand_type = HandType.RIGHT_HAND
        return self._hand_type
    def _joint_to_pdo(self, joint: Joint, pdo: JointRpdo):
        """
        将Joint对象转换为PDO对象
        
        Args:
          joint (Joint): 关节对象
          pdo (JointRpdo): PDO对象
        """
        pdo.angle = joint.angle
        pdo.speed = joint.speed
        pdo.torque = joint.torque

    def move_joints(self, joints: list[Joint], mode: int = 0, stop: int = 0):
        """
        发送多个关节控制指令

        Args:
          joints (list[Joint]): 关节控制指令
          mode (int, optional): 模式选择。0:位置模式;1:力矩模式。默认为0
          stop (int, optional): 停止选择。0:运动;1:停止所有关节。默认为0

        Returns:
          bool: 连接成功返回True，否则返回False
        """
        try:
            rpdo = Rpdo()
            rpdo.mode = mode
            rpdo.stop = stop
            for joint in joints:
                # 应用关节限制检查
                if joint.id == JointId.THUMB_PIP:
                    self._check_joint_limit(joint, self._th_pip_limit)
                    self._joint_to_pdo(joint, rpdo.th_pip)
                elif joint.id == JointId.THUMB_MCP:
                    self._check_joint_limit(joint, self._th_mcp_limit)
                    self._joint_to_pdo(joint, rpdo.th_mcp)
                elif joint.id == JointId.THUMB_SWING:
                    self._check_joint_limit(joint, self._th_swing_limit)
                    self._joint_to_pdo(joint, rpdo.th_swing)
                elif joint.id == JointId.THUMB_ROTATION:
                    self._check_joint_limit(joint, self._th_rot_limit)
                    self._joint_to_pdo(joint, rpdo.th_rot)
                elif joint.id == JointId.FF_PIP:
                    self._check_joint_limit(joint, self._ff_pip_limit)
                    self._joint_to_pdo(joint, rpdo.ff_pip)
                elif joint.id == JointId.FF_MCP:
                    self._check_joint_limit(joint, self._ff_mcp_limit)
                    self._joint_to_pdo(joint, rpdo.ff_mcp)
                elif joint.id == JointId.FF_SWING:
                    self._check_joint_limit(joint, self._ff_swing_limit)
                    self._joint_to_pdo(joint, rpdo.ff_swing)
                elif joint.id == JointId.MF_PIP:
                    self._check_joint_limit(joint, self._mf_pip_limit)
                    self._joint_to_pdo(joint, rpdo.mf_pip)
                elif joint.id == JointId.MF_MCP:
                    self._check_joint_limit(joint, self._mf_mcp_limit)
                    self._joint_to_pdo(joint, rpdo.mf_mcp)
                elif joint.id == JointId.RF_PIP:
                    self._check_joint_limit(joint, self._rf_pip_limit)
                    self._joint_to_pdo(joint, rpdo.rf_pip)
                elif joint.id == JointId.RF_MCP:
                    self._check_joint_limit(joint, self._rf_mcp_limit)
                    self._joint_to_pdo(joint, rpdo.rf_mcp)
                elif joint.id == JointId.LF_PIP:
                    self._check_joint_limit(joint, self._lf_pip_limit)
                    self._joint_to_pdo(joint, rpdo.lf_pip)
                elif joint.id == JointId.LF_MCP:
                    self._check_joint_limit(joint, self._lf_mcp_limit)
                    self._joint_to_pdo(joint, rpdo.lf_mcp)
                else:
                    logger.warning(f"【Joint】无效的关节ID: {joint.id}")
                    return False
            self._client.send_data(rpdo.to_bytes())
            return True
        except RuntimeError as e:
            logger.error(f"Failed to move joints: {e}")
            return False

    def get_joints(self) -> list[Joint]:
        """
        获取所有关节状态及运动信息

        Returns:
        list[Joint]: 连接成功返回True,否则返回False
        """
        try:
            data = self._client.recv_data()
            logger.debug(f"Received data: \n{' '.join(f'{b:02x}' for b in data)}")
            logger.debug(f"Received data length: {len(data)} bytes")  # 调试信息：打印接收到的数据长度

            if len(data) != 208:
                logger.warning(f"Data length insufficient. Expected 208 bytes, got {len(data)} bytes")  # 数据长度不足时的提示
                return []
            
            tpdo = Tpdo.from_bytes(data)
            logger.debug(f"Parsed TPDO:\n" + "\n".join([f"hand: {tpdo.hand}",
                           f"th_dip: {tpdo.th_dip}", f"th_pip: {tpdo.th_pip}", f"th_mcp: {tpdo.th_mcp}",
                           f"th_swing: {tpdo.th_swing}",f"th_rot: {tpdo.th_rot}",
                           f"ff_dip: {tpdo.ff_dip}",f"ff_pip: {tpdo.ff_pip}",f"ff_mcp: {tpdo.ff_mcp}",f"ff_swing: {tpdo.ff_swing}",
                           f"mf_dip: {tpdo.mf_dip}",f"mf_pip: {tpdo.mf_pip}",f"mf_mcp: {tpdo.mf_mcp}",
                           f"rf_dip: {tpdo.rf_dip}",f"rf_pip: {tpdo.rf_pip}",f"rf_mcp: {tpdo.rf_mcp}",
                           f"lf_dip: {tpdo.lf_dip}",f"lf_pip: {tpdo.lf_pip}",f"lf_mcp: {tpdo.lf_mcp}",
                           f"tac_th: {tpdo.tac_th}",f"tac_ff: {tpdo.tac_ff}",f"tac_mf: {tpdo.tac_mf}",
                           f"tac_rf: {tpdo.tac_rf}",f"tac_lf: {tpdo.tac_lf}",f"tac_palm: {tpdo.tac_palm}"]))
            
            # 定义关节信息映射
            joint_mappings = [
                # thumb
                (JointId.THUMB_DIP, tpdo.th_dip),
                (JointId.THUMB_PIP, tpdo.th_pip),
                (JointId.THUMB_MCP, tpdo.th_mcp),
                (JointId.THUMB_SWING, tpdo.th_swing),
                (JointId.THUMB_ROTATION, tpdo.th_rot),
                # ff
                (JointId.FF_DIP, tpdo.ff_dip),
                (JointId.FF_PIP, tpdo.ff_pip),
                (JointId.FF_MCP, tpdo.ff_mcp),
                (JointId.FF_SWING, tpdo.ff_swing),
                # mf
                (JointId.MF_DIP, tpdo.mf_dip),
                (JointId.MF_PIP, tpdo.mf_pip),
                (JointId.MF_MCP, tpdo.mf_mcp),
                # rf
                (JointId.RF_DIP, tpdo.rf_dip),
                (JointId.RF_PIP, tpdo.rf_pip),
                (JointId.RF_MCP, tpdo.rf_mcp),
                # lf
                (JointId.LF_DIP, tpdo.lf_dip),
                (JointId.LF_PIP, tpdo.lf_pip),
                (JointId.LF_MCP, tpdo.lf_mcp),
            ]
            
            joints = []
            for joint_id, joint_tpdo in joint_mappings:
                joints.append(Joint(
                    id=joint_id,
                    angle=joint_tpdo.angle,
                    speed=joint_tpdo.speed,
                    torque=joint_tpdo.torque
                ))

            return joints
        
        except RuntimeError as e:
            logger.error(f"Failed to get joints: {e}")
            return []

