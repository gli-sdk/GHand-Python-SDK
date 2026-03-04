import enum
import math
import logging
from typing import Optional
from dataclasses import dataclass
from .ecatclient import EthercatClient
from .subscription import SubscriptionManager
from .data import JointRpdo, Rpdo, Tpdo
from .error import State, ErrorCode

logger = logging.getLogger("xiaoyao.dexhand")

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
    SPEED = 2


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

# 触觉传感器枚举
class TactileSensorId(enum.Enum):
    THUMB = 'thumb'
    FOREFINGER = 'forefinger'
    MIDDLE_FINGER = 'middle_finger'
    RING_FINGER = 'ring_finger'
    LITTLE_FINGER = 'little_finger'

@dataclass
class TactileInfo:
    """触觉传感器信息数据类"""
    status: bool = False  # 传感器连接状态
    resultant_force: list[int] = None  # xyz合力数据
    distributed_force: list[int] = None  # 分布力数据

    def __post_init__(self):
        """初始化后设置默认值"""
        if self.resultant_force is None:
            self.resultant_force = [0, 0, 0]
        if self.distributed_force is None:
            self.distributed_force = []

    def get_force_x(self) -> float:
        """获取X轴合力"""
        return self.resultant_force[0] if len(self.resultant_force) > 0 else 0

    def get_force_y(self) -> float:
        """获取Y轴合力"""
        return self.resultant_force[1] if len(self.resultant_force) > 1 else 0

    def get_force_z(self) -> float:
        """获取Z轴合力"""
        return self.resultant_force[2] if len(self.resultant_force) > 2 else 0

    def get_distributed_force(self) -> list[int]:
        """获取分布力数据"""
        return self.distributed_force

    def get_distributed_force_at(self, index: int) -> int:
        """获取指定索引处的分布力值"""
        if 0 <= index < len(self.distributed_force):
            return self.distributed_force[index]
        else:
            return 0  # 返回默认值，避免索引错误


@dataclass
class HandInfo:
    """手部状态信息"""
    state: State = State.STOPPED  # 手部状态
    error: ErrorCode = ErrorCode.NORMAL  # 错误码
    temp: int = 0  # 温度

@dataclass
class Joint:
    id: int = JointId.THUMB_DIP
    angle: float = 0.0
    speed: float = 0.0
    torque: float = 0.0
    state: State = State.STOPPED  # 关节状态
    error: ErrorCode = ErrorCode.NORMAL  # 错误码

    @staticmethod
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


class DexHand(object):
    def __init__(self):
        """
        初始化灵巧手对象
        """
        self._client = EthercatClient()
        self._hand_type = HandType.UNKNOWN
        self._firmware_version = ""
        # 传递客户端实例给SubscriptionManager
        self._sub_manager = SubscriptionManager(self._client)
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
        self._th_pip_limit = (0, math.radians(66))
        self._th_mcp_limit = (0, math.radians(50))
        self._th_swing_limit = (0, math.radians(90))
        self._th_rot_limit = (math.radians(-30), math.radians(60))
        self._ff_pip_limit = (0, math.radians(80))
        self._ff_mcp_limit = (0, math.radians(90))
        self._ff_swing_limit = (math.radians(-10), math.radians(10))
        self._mf_pip_limit = (0, math.radians(90))
        self._mf_mcp_limit = (0, math.radians(90))
        self._rf_pip_limit = (0, math.radians(90))
        self._rf_mcp_limit = (0, math.radians(90))
        self._lf_pip_limit = (0, math.radians(74))
        self._lf_mcp_limit = (0, math.radians(90))

    def _check_joint_limit(self, joint: Joint, limit):
        """
        检查关节角度是否超出限制范围，如果超出则设为边界值

        Args:
          joint (Joint): 关节对象
          limit: 关节限制范围

        """
        if joint.angle < limit[0]:
            joint.angle = limit[0]
            logger.warning(f"[Joint] ID: {JointId(joint.id).name} angle below limit, clamped to min value {math.degrees(limit[0]):.2f} degrees")
        elif joint.angle > limit[1]:
            joint.angle = limit[1]
            logger.warning(f"[Joint] ID: {JointId(joint.id).name} angle above limit, clamped to max value {math.degrees(limit[1]):.2f} degrees")

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
                logger.info("Found IDs:\n" + "\n".join([f"\t{id}" for id in id_list]))
                for id in id_list:
                    connected = self._client.connect(id)
                    if connected:
                        run_success = self._client.run()
                        if run_success:
                            self._opened = True
                            logger.info(f"Device opened successfully (ID: {id})")
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
        self._sub_manager.stop()
        if self._opened:
            self._client.disconnect()
            logger.info("Disconnected from device")
            self._opened = False
        return True

    def subscribe(self, callback):
        """
        订阅灵巧手数据更新

        Args:
            callback: 回调函数，当有新数据时会被调用
                     回调函数应接受一个参数：TPDO数据对象

        Returns:
            int: 订阅ID，可用于取消订阅
        """

        def wrapper(data_bytes, *args, **kwargs):
            # 将字节数据转换为TPDO对象
            tpdo = Tpdo.from_bytes(data_bytes)
            # 调用用户提供的回调函数
            callback(tpdo)

        return self._sub_manager.subscribe(wrapper)

    def unsubscribe(self, sub_id):
        """
        取消订阅

        Args:
            sub_id (int): 订阅ID

        Returns:
            bool: 取消成功返回True，否则返回False
        """
        return self._sub_manager.unsubscribe(sub_id)

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
            logger.info("Fault cleared successfully")
        except Exception as e:
            logger.error(f"Failed to clear fault: {e}")
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
            logger.info("Joint initialization completed successfully")
        except Exception as e:
            logger.error(f"Failed to initialize joints: {e}")
            return False
        return True

    def tactile_restart(self) -> bool:
        """
        重启触觉传感器数据

        Returns:
            bool: 重置成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x03')
            # 读取结果区（子索引3）
            result_data = self._client.sdo_read(0x2004, 0x03)
            # 检查结果区数据，如果为0则成功，为1则失败
            if result_data == b'\x00':
                return True
            else:
                return False
        except Exception:
            return False

    def tactile_open(self) -> bool:
        """
        打开触觉传感器

        Returns:
            bool: 打开成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x01')
            # 读取结果区（子索引3）
            result_data = self._client.sdo_read(0x2004, 0x03)
            # 检查结果区数据，如果为0则成功，为1则失败
            if result_data == b'\x00':
                return True
            else:
                return False
        except Exception:
            return False

    def tactile_close(self) -> bool:
        """
        关闭触觉传感器

        Returns:
            bool: 关闭成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x02')
            # 读取结果区（子索引3）
            result_data = self._client.sdo_read(0x2004, 0x03)
            # 检查结果区数据，如果为0则成功，为1则失败
            if result_data == b'\x00':
                return True
            else:
                return False
        except Exception:
            return False

    def tactile_zero(self) -> bool:
        """
        调零触觉传感器

        Returns:
            bool: 调零成功返回True，失败返回False
        """
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x04')
            # 读取结果区（子索引3）
            result_data = self._client.sdo_read(0x2004, 0x03)
            # 检查结果区数据，如果为0则成功，为1则失败
            if result_data == b'\x00':
                return True
            else:
                return False
        except Exception:
            return False

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
          mode (int, optional): 模式选择。0:位置模式;1:力矩模式;2:速度模式。默认为0
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
                    logger.warning(f"[Joint] Invalid joint ID: {joint.id}")
                    return False
            self._client.send_data(rpdo.to_bytes())
            logger.info("Command sent successfully")
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
            if len(data) != 708:
                logger.warning(f"Data length insufficient. Expected 708 bytes, got {len(data)} bytes")
                return []
            logger.info("Joint data received successfully")
            # Display first 4 bytes of joint data
            joint_data = data[4:148]
            logger.debug(f"Joint data (144 bytes): {' '.join(f'{b:02x}' for b in joint_data)}")

            tpdo = Tpdo.from_bytes(data)
            # logger.debug(f"Parsed TPDO:\n" + "\n".join([
            #                f"th_dip: {tpdo.th_dip}", f"th_pip: {tpdo.th_pip}", f"th_mcp: {tpdo.th_mcp}",
            #                f"th_swing: {tpdo.th_swing}",f"th_rot: {tpdo.th_rot}",
            #                f"ff_dip: {tpdo.ff_dip}",f"ff_pip: {tpdo.ff_pip}",f"ff_mcp: {tpdo.ff_mcp}",f"ff_swing: {tpdo.ff_swing}",
            #                f"mf_dip: {tpdo.mf_dip}",f"mf_pip: {tpdo.mf_pip}",f"mf_mcp: {tpdo.mf_mcp}",
            #                f"rf_dip: {tpdo.rf_dip}",f"rf_pip: {tpdo.rf_pip}",f"rf_mcp: {tpdo.rf_mcp}",
            #                f"lf_dip: {tpdo.lf_dip}",f"lf_pip: {tpdo.lf_pip}",f"lf_mcp: {tpdo.lf_mcp}"
            #             ]))

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
                # 检查状态并记录异常（state == 2 或 3 为错误状态，或 error != 0）
                if joint_tpdo.error != 0 or joint_tpdo.state in [2, 3]:
                    logger.warning(
                        f"Joint error - ID: {JointId(joint_id).name}, State: {joint_tpdo.state}, Error: {joint_tpdo.error}"
                    )

                joints.append(
                    Joint(
                        id=joint_id,
                        angle=joint_tpdo.angle,
                        speed=joint_tpdo.speed,
                        torque=joint_tpdo.torque,
                        state=joint_tpdo.state,
                        error=joint_tpdo.error,
                    )
                )

            return joints

        except RuntimeError as e:
            logger.error(f"Failed to get joints: {e}")
            return []

    def get_hand_info(self) -> HandInfo:
        """
        获取手部状态信息

        Returns:
            HandInfo: 手部状态信息对象，包含 state（状态）、error（错误码）、temp（温度）
        """
        try:
            data = self._client.recv_data()

            if len(data) != 708:
                logger.warning(f"Data length insufficient. Expected 708 bytes, got {len(data)} bytes")
                return HandInfo()

            # logger.info("Hand data received successfully")
            # hand_data = data[0:4]
            # logger.debug(
            #     f"Hand data (4 bytes): {' '.join(f'{b:02x}' for b in hand_data)}"
            # )
            tpdo = Tpdo.from_bytes(data)

            # 检查手部状态并记录异常
            if tpdo.hand.error != 0 or tpdo.hand.state in [2, 3]:
                logger.warning(
                    f"Hand error - State: {tpdo.hand.state}, Error: {tpdo.hand.error}, Temp: {tpdo.hand.temp}"
                )

            return HandInfo(
                state=tpdo.hand.state,
                error=tpdo.hand.error,
                temp=tpdo.hand.temp
            )

        except RuntimeError as e:
            logger.error(f"Failed to get hand info: {e}")
            return HandInfo()

    def get_tactile_data(self):
        """
        获取触觉传感器数据

        Returns:
            dict: 包含各手指触觉传感器数据的字典，键为TactileSensorId枚举，值为TactileInfo对象
        """
        try:
            data = self._client.recv_data()

            if len(data) != 708:
                logger.warning(f"Data length insufficient. Expected 708 bytes, got {len(data)} bytes")
                return {}

            logger.info("Tactile data received successfully")
            tactile_data = data[148:708]
            logger.debug(f"Tactile data (560 bytes):\n{' '.join(f'{b:02x}' for b in tactile_data)}")

            tpdo = Tpdo.from_bytes(data)
            logger.debug(f"Parsed TPDO tactile data:\n" + "\n".join([
                           f"tactile_status: {tpdo.tactile_status}",
                           f"thumb_tactile: {tpdo.thumb_tactile}",
                           f"ff_tactile: {tpdo.ff_tactile}",
                           f"mf_tactile: {tpdo.mf_tactile}",
                           f"rf_tactile: {tpdo.rf_tactile}",
                           f"lf_tactile: {tpdo.lf_tactile}"]))

            # 返回一个结构化的字典，使用枚举作为键
            tactile_data = {
                TactileSensorId.THUMB: TactileInfo(
                    status=bool(tpdo.tactile_status.state & (1 << 0)),
                    resultant_force=tpdo.thumb_tactile.resultant_force,
                    distributed_force=tpdo.thumb_tactile.sample_force
                ),
                TactileSensorId.FOREFINGER: TactileInfo(
                    status=bool(tpdo.tactile_status.state & (1 << 1)),
                    resultant_force=tpdo.ff_tactile.resultant_force,
                    distributed_force=tpdo.ff_tactile.sample_force
                ),
                TactileSensorId.MIDDLE_FINGER: TactileInfo(
                    status=bool(tpdo.tactile_status.state & (1 << 2)),
                    resultant_force=tpdo.mf_tactile.resultant_force,
                    distributed_force=tpdo.mf_tactile.sample_force
                ),
                TactileSensorId.RING_FINGER: TactileInfo(
                    status=bool(tpdo.tactile_status.state & (1 << 3)),
                    resultant_force=tpdo.rf_tactile.resultant_force,
                    distributed_force=tpdo.rf_tactile.sample_force
                ),
                TactileSensorId.LITTLE_FINGER: TactileInfo(
                    status=bool(tpdo.tactile_status.state & (1 << 4)),
                    resultant_force=tpdo.lf_tactile.resultant_force,
                    distributed_force=tpdo.lf_tactile.sample_force
                )
            }

            return tactile_data

        except RuntimeError as e:
            logger.error(f"Failed to get tactile data: {e}")
            return []
