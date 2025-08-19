import enum
from typing import Optional
from dataclasses import dataclass
from .ecatclient import EthercatClient
from .subscription import SubscriptionManager
from .data import JointRpdo, Rpdo, Tpdo


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


class GestureType(enum.Enum):
    HAND_OPEN = "hand_open"


class DexHand(object):
    def __init__(self):
        self._client = EthercatClient()
        self._hand_type = HandType.UNKNOWN
        self._firmware_version = ""
        self._sub_manager = SubscriptionManager()
        self._opened = False
        self._set_joint_limit()

    def __del__(self):
        self.close()

    def _set_joint_limit(self):
        self._th_pip_limit = (0, 0)
        self._th_mcp_limit = (0, 0)
        self._th_swing_limit = (0, 0)
        self._th_rot_limit = (0, 0)
        self._ff_pip_limit = (0, 0)
        self._ff_mcp_limit = (0, 0)
        self._ff_swing_limit = (0, 0)
        self._mf_pip_limit = (0, 0)
        self._mf_mcp_limit = (0, 0)
        self._rf_pip_limit = (0, 0)
        self._rf_mcp_limit = (0, 0)
        self._lf_pip_limit = (0, 0)
        self._lf_mcp_limit = (0, 0)

    def _check_joint_limit(self, joint: Joint, limit):
        if joint.angle < limit[0] or joint.angle > limit[1]:
            return False
        return True

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
                for id in id_list:
                    self._opened = self._client.connect(id)
                    if self._opened:
                        self._client.run()
                        break
            else:
                self._opened = self._client.connect(id)
                if self._opened:
                    self._client.run()
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
            str: 获取成功返回版本号（如："v1.0.0"），失败返回空字符串""
        """
        if self._firmware_version == "":
            self._firmware_version = self._client.sdo_read(
                0x100A, 0x00).decode('utf-8')
        return self._firmware_version

    def release_protection(self) -> bool:
        """
        解除保护

        Returns:
            bool: 解除成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2001, 0x00, b'\x01')
        except Exception:
            return False
        return True

    def reboot(self) -> bool:
        """
        重启设备

        Returns:
            bool: 重启成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2002, 0x01, b'\x01')
        except Exception:
            return False
        return True

    def joint_init(self) -> bool:
        try:
            self._client.sdo_write(0x2003, 0x00, b'\x01')
        except Exception:
            return False
        return True

    def tactile_self_test(self) -> bool:
        try:
            self._client.sdo_write(0x2005, 0x00, b'\x01')
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
            self._client.sdo_write(0x2006, 0x00, b'\x01')
        except Exception:
            return False
        return True

    def motor_self_test(self) -> bool:
        try:
            self._client.sdo_write(0x2007, 0x00, b'\x01')
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
                    self._client.sdo_read(0x2011), byteorder='little')
            except Exception:
                return HandType.UNKNOWN
            if type == 0x01:
                self._hand_type = HandType.LEFT_HAND
            elif type == 0x02:
                self._hand_type = HandType.RIGHT_HAND
        return self._hand_type

    def sub_hand_data(self, callback=None, *args, **kw):
        sub_id = self._sub_manager.subscribe(callback, *args, **kw)
        return sub_id

    def unsub_hand_data(self, sub_id):
        return self._sub_manager.unsubscribe(sub_id)

    def _joint_to_pdo(self, joint: Joint, pdo: JointRpdo):
        print(joint.angle)
        pdo.angle = joint.angle
        pdo.speed = joint.speed
        pdo.torque = joint.torque

    def move_joints(self, joints: list[Joint]):
        """
        发送多个关节控制指令

        Args:
          joints (list[Joint]): 关节控制指令

        Returns:
          bool: 连接成功返回True，否则返回False
        """
        rpdo = Rpdo()
        for joint in joints:
            if joint.id == JointId.THUMB_PIP:
                self._joint_to_pdo(joint, rpdo.th_pip)
            elif joint.id == JointId.THUMB_MCP:
                self._joint_to_pdo(joint, rpdo.th_mcp)
            elif joint.id == JointId.THUMB_SWING:
                self._joint_to_pdo(joint, rpdo.th_swing)
            elif joint.id == JointId.THUMB_ROTATION:
                self._joint_to_pdo(joint, rpdo.th_rot)
            elif joint.id == JointId.FF_PIP:
                self._joint_to_pdo(joint, rpdo.ff_pip)
            elif joint.id == JointId.FF_MCP:
                self._joint_to_pdo(joint, rpdo.ff_mcp)
            elif joint.id == JointId.FF_SWING:
                self._joint_to_pdo(joint, rpdo.ff_swing)
            elif joint.id == JointId.MF_PIP:
                self._joint_to_pdo(joint, rpdo.mf_pip)
            elif joint.id == JointId.MF_MCP:
                self._joint_to_pdo(joint, rpdo.mf_mcp)
            elif joint.id == JointId.RF_PIP:
                self._joint_to_pdo(joint, rpdo.rf_pip)
            elif joint.id == JointId.RF_MCP:
                self._joint_to_pdo(joint, rpdo.rf_mcp)
            elif joint.id == JointId.LF_PIP:
                self._joint_to_pdo(joint, rpdo.lf_pip)
            elif joint.id == JointId.LF_MCP:
                self._joint_to_pdo(joint, rpdo.lf_mcp)
            else:
                print(f"【Joint】无效的关节ID: {joint.id}")
                return False
        self._client.send_data(rpdo.to_bytes())
        print(f"【Joint】发送 PDO 数据成功")
        return True

    def get_joints(self) -> list[Joint]:
        """
        获取所有关节状态及运动信息

        Returns:
        list[Joint]: 连接成功返回True，否则返回False
        """
        data = self._client.recv_data()
        print(f"Received data length: {len(data)} bytes")  # 调试信息：打印接收到的数据长度
        
        if len(data) < 235:
            print(f"Data length insufficient. Expected at least 235 bytes, got {len(data)} bytes")  # 调试信息：数据长度不足时的提示
            return []
        
        tpdo = Tpdo.from_bytes(data)
        print(f"Parsed TPDO: {tpdo}")  # 调试信息：打印解析后的TPDO对象
        
        joints = []
        for i in range(18):
            joint = Joint(id=i, angle=i)
            joints.append(joint)
        
        print(f"Returning {len(joints)} joints")  # 调试信息：打印返回的关节数量
        return joints

    # def move_joints(self, th_pip: Optional[Joint] = None, th_mcp: Optional[Joint] = None, th_swing: Optional[Joint] = None, th_rot: Optional[Joint] = None, ff_pip: Optional[Joint] = None, ff_mcp: Optional[Joint] = None, ff_swing: Optional[Joint] = None, mf_pip: Optional[Joint] = None, mf_mcp: Optional[Joint] = None, rf_pip: Optional[Joint] = None, rf_mcp: Optional[Joint] = None, lf_pip: Optional[Joint] = None, lf_mcp: Optional[Joint] = None, ctrl_mode=CtrlMode.POSITION):
    #     if not self._client._connected:
    #         return False
    #     rpdo = Rpdo(mode=ctrl_mode.value)
    #     # Check joint limit
    #     if th_pip is not None:
    #         self._joint_to_pdo(th_pip, rpdo.th_pip)
    #     if th_mcp is not None:
    #         self._joint_to_pdo(th_mcp, rpdo.th_mcp)
    #     if th_swing is not None:
    #         self._joint_to_pdo(th_swing, rpdo.th_swing)
    #     if th_rot is not None:
    #         self._joint_to_pdo(th_rot, rpdo.th_rot)
    #     if ff_pip is not None:
    #         self._joint_to_pdo(ff_pip, rpdo.ff_pip)
    #     if ff_mcp is not None:
    #         self._joint_to_pdo(ff_mcp, rpdo.ff_mcp)
    #     if ff_swing is not None:
    #         self._joint_to_pdo(ff_swing, rpdo.ff_swing)
    #     if mf_pip is not None:
    #         self._joint_to_pdo(mf_pip, rpdo.mf_pip)
    #     if mf_mcp is not None:
    #         self._joint_to_pdo(mf_mcp, rpdo.mf_mcp)
    #     if rf_pip is not None:
    #         self._joint_to_pdo(rf_pip, rpdo.rf_pip)
    #     if rf_mcp is not None:
    #         self._joint_to_pdo(rf_mcp, rpdo.rf_mcp)
    #     if lf_pip is not None:
    #         self._joint_to_pdo(lf_pip, rpdo.lf_pip)
    #     if lf_mcp is not None:
    #         self._joint_to_pdo(lf_mcp, rpdo.lf_mcp)
    #     self._client._slave.output = rpdo.to_bytes()
    #     return True
