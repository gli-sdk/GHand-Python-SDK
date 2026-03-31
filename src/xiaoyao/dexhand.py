import enum
import math
import logging
from dataclasses import dataclass
from .ecatclient import EthercatClient
from .subscription import SubscriptionManager
from .data import JointRpdo, Rpdo, Tpdo
from .error import State, ErrorCode
from .exceptions import (
    DeviceDisconnectedError,
    DeviceFaultError,
    JointFaultError,
    DataReceiveError,
    FaultInfo,
    JointFaultInfo,
    get_fault_message
)

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
    state: bool = False  # 传感器连接状态
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

    def get_state(self) -> bool:
        """获取传感器连接状态"""
        return self.state


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
    speed: int = 0
    torque: int = 0
    state: State = State.STOPPED  # 关节状态
    error: ErrorCode = ErrorCode.NORMAL  # 错误码

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

    def _check_speed_limit(self, joint: Joint, mode: CtrlMode):
        """
        检查关节速度是否在有效范围内，根据控制模式应用不同的限制

        Args:
          joint (Joint): 关节对象
          mode (CtrlMode): 控制模式

        """
        if mode == CtrlMode.POSITION:
            # 位置模式：速度范围 0-100，负数取绝对值，绝对值>100取100
            if joint.speed < 0:
                joint.speed = abs(joint.speed)
                logger.warning(f"[Joint] ID: {JointId(joint.id).name} speed is negative in POSITION mode, converted to absolute value {joint.speed}")
            if joint.speed > 100:
                original_speed = joint.speed
                joint.speed = 100
                logger.warning(f"[Joint] ID: {JointId(joint.id).name} speed {original_speed} exceeds limit in POSITION mode, clamped to 100")
        elif mode == CtrlMode.SPEED:
            # 速度模式：速度范围 -100到100
            if joint.speed < -100:
                original_speed = joint.speed
                joint.speed = -100
                logger.warning(f"[Joint] ID: {JointId(joint.id).name} speed {original_speed} below limit in SPEED mode, clamped to -100")
            elif joint.speed > 100:
                original_speed = joint.speed
                joint.speed = 100
                logger.warning(f"[Joint] ID: {JointId(joint.id).name} speed {original_speed} exceeds limit in SPEED mode, clamped to 100")
        # 力矩模式：速度不影响，不进行检查

    def _check_torque_limit(self, joint: Joint, mode: CtrlMode):
        """
        检查关节力矩是否在有效范围内，根据控制模式应用不同的限制

        Args:
          joint (Joint): 关节对象
          mode (CtrlMode): 控制模式

        """
        if mode in [CtrlMode.POSITION, CtrlMode.SPEED]:
            # 位置模式和速度模式：力矩范围 0-100，负数取绝对值，绝对值>100取100
            if joint.torque < 0:
                joint.torque = abs(joint.torque)
                logger.warning(f"[Joint] ID: {JointId(joint.id).name} torque is negative in {mode.name} mode, converted to absolute value {joint.torque}")
            if joint.torque > 100:
                original_torque = joint.torque
                joint.torque = 100
                logger.warning(f"[Joint] ID: {JointId(joint.id).name} torque {original_torque} exceeds limit in {mode.name} mode, clamped to 100")
        elif mode == CtrlMode.TORQUE:
            # 力矩模式：力矩范围 -100到100
            if joint.torque < -100:
                original_torque = joint.torque
                joint.torque = -100
                logger.warning(f"[Joint] ID: {JointId(joint.id).name} torque {original_torque} below limit in TORQUE mode, clamped to -100")
            elif joint.torque > 100:
                original_torque = joint.torque
                joint.torque = 100
                logger.warning(f"[Joint] ID: {JointId(joint.id).name} torque {original_torque} exceeds limit in TORQUE mode, clamped to 100")

    def get_connectable_devices(self) -> list[str]:
        """
        获取可连接的设备列表

        Returns:
            list[str]: 返回可连接设备的网络接口ID列表
        """
        connected_interfaces = []
        id_list = self._client.search()

        for iface_id in id_list:
            connected = self._client.connect(iface_id)
            if connected:
                connected_interfaces.append(iface_id)
                self._client.disconnect()

        if connected_interfaces:
            logger.info("可连接的设备:\n" + "\n".join([f"{id}" for id in connected_interfaces]))
        else:
            logger.warning("未找到可连接的设备")

        return connected_interfaces

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
                            logger.error(f"Failed to open device (ID: {id})")
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

    def is_connected(self) -> bool:
        """
        检查设备是否已连接

        Returns:
            bool: 已连接返回True，否则返回False
        """
        return self._opened

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
            int: 获取成功返回产品序列号，失败返回0
        """
        try:
            serial_number = int.from_bytes(
                self._client.sdo_read(0x1018, 0x04), byteorder='little')
        except Exception:
            return 0
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
        # THUMB_ROTATION 在固件层面有 30 度偏移，发送时需要补偿
        # 固件期望 0-90 度，SDK 逻辑范围是 -30 到 60 度
        if joint.id == JointId.THUMB_ROTATION:
            pdo.angle = joint.angle + math.radians(30)
        else:
            pdo.angle = joint.angle
        pdo.speed = joint.speed
        pdo.torque = joint.torque

    def move_joints(self, joints: list[Joint], mode: CtrlMode = CtrlMode.POSITION):
        """
        发送多个关节控制指令

        Args:
          joints (list[Joint]): 关节控制指令
          mode (CtrlMode, optional): 模式选择。位置模式/力矩模式/速度模式。默认为位置模式

        Returns:
          bool: 连接成功返回True，否则返回False
        """
        try:
            rpdo = Rpdo()
            rpdo.mode = mode.value
            rpdo.stop = 0
            for joint in joints:
                # 应用速度和力矩限制检查
                self._check_speed_limit(joint, mode)
                self._check_torque_limit(joint, mode)
                # 应用关节角度限制检查
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

    def stop(self) -> bool:
        """
        停止所有关节运动

        Returns:
            bool: 指令是否发送成功
        """
        try:
            rpdo = Rpdo()
            rpdo.mode = 0
            rpdo.stop = 1
            self._client.send_data(rpdo.to_bytes())
            logger.info("Stop command sent successfully")
            return True
        except RuntimeError as e:
            logger.error(f"Failed to stop joints: {e}")
            return False

    def get_joints(self) -> list[Joint]:
        """
        获取所有关节状态及运动信息

        Returns:
            list[Joint]: 关节列表

        Raises:
            DataReceiveError: 数据长度不正确（期望708字节）
            DeviceDisconnectedError: 设备断连或通信失败
            JointFaultError: 任何关节故障（error != 0 或 state in [2, 3]）
        """
        try:
            data = self._client.recv_data()

            # 数据长度验证
            if len(data) != 708:
                error_msg = f"Data length insufficient. Expected 708 bytes, got {len(data)} bytes"
                logger.warning(error_msg)
                raise DataReceiveError(
                    error_msg,
                    expected_length=708,
                    actual_length=len(data)
                )

            logger.info("Joint data received successfully")
            tpdo = Tpdo.from_bytes(data)

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
            faulty_joints = []  # 收集所有故障关节

            for joint_id, joint_tpdo in joint_mappings:
                # 检查关节故障
                if joint_tpdo.error != ErrorCode.NORMAL or joint_tpdo.state in [
                    State.ABNORMAL_RUNNING,
                    State.PROTECTIVE_STOPED,
                ]:
                    faulty_joints.append(JointFaultInfo(
                        joint_id=JointId(joint_id).name,
                        state=State(joint_tpdo.state),
                        error_code=ErrorCode(joint_tpdo.error)
                    ))

                # THUMB_ROTATION 角度补偿
                angle = joint_tpdo.angle
                if joint_id == JointId.THUMB_ROTATION:
                    angle = angle - math.radians(30)

                joints.append(
                    Joint(
                        id=joint_id,
                        angle=angle,
                        speed=joint_tpdo.speed,
                        torque=joint_tpdo.torque,
                        state=State(joint_tpdo.state),
                        error=ErrorCode(joint_tpdo.error),
                    )
                )

            # 如果有故障关节，抛出异常
            if faulty_joints:
                error_msg = f"Detected {len(faulty_joints)} faulty joint(s)"
                logger.error(error_msg)
                raise JointFaultError(error_msg, faulty_joints=faulty_joints)

            return joints

        except DataReceiveError:
            # 重新抛出数据接收错误
            raise
        except JointFaultError:
            # 重新抛出关节故障错误
            raise
        except RuntimeError as e:
            # 通信错误，转换为设备断连异常
            # logger.error(f"Communication failed: {e}")
            raise DeviceDisconnectedError(
                f"Failed to communicate with device: {e}"
            ) from e

    def get_hand_info(self) -> HandInfo:
        """
        获取手部状态信息

        Returns:
            HandInfo: 手部状态信息对象，包含 state（状态）、error（错误码）、temp（温度）

        Raises:
            DataReceiveError: 数据长度不正确（期望708字节）
            DeviceDisconnectedError: 设备断连或通信失败
            DeviceFaultError: 设备故障（state=2/3 或 error!=0）
        """
        try:
            data = self._client.recv_data()

            # 数据长度验证
            if len(data) != 708:
                error_msg = f"Data length insufficient. Expected 708 bytes, got {len(data)} bytes"
                logger.warning(error_msg)
                raise DataReceiveError(
                    error_msg,
                    expected_length=708,
                    actual_length=len(data)
                )

            tpdo = Tpdo.from_bytes(data)

            # 检查设备故障状态
            if tpdo.hand.error != 0:
                fault_info = FaultInfo(
                    error_code=ErrorCode(tpdo.hand.error),
                    state=State(tpdo.hand.state),
                    message=get_fault_message(ErrorCode(tpdo.hand.error), State(tpdo.hand.state), temp=tpdo.hand.temp)
                )
                error_msg = f"Device fault detected - {fault_info}"
                logger.error(error_msg)
                raise DeviceFaultError(error_msg, fault_info=fault_info)

            # 检查异常运行状态（虽然你说 state=2/3 时一定 error!=0，但为了保险再检查一次）
            if tpdo.hand.state in [State.ABNORMAL_RUNNING, State.PROTECTIVE_STOPED]:
                # 如果 error == 0 但状态异常，也抛出异常
                if tpdo.hand.error == 0:
                    fault_info = FaultInfo(
                        error_code=ErrorCode.NORMAL,
                        state=State(tpdo.hand.state),
                        message=get_fault_message(ErrorCode.NORMAL, State(tpdo.hand.state))
                    )
                    error_msg = f"Abnormal device state - {fault_info}"
                    logger.error(error_msg)
                    raise DeviceFaultError(error_msg, fault_info=fault_info)

            return HandInfo(
                state=State(tpdo.hand.state),
                error=ErrorCode(tpdo.hand.error),
                temp=tpdo.hand.temp
            )

        except DataReceiveError:
            # 重新抛出数据接收错误
            raise
        except DeviceFaultError:
            # 重新抛出设备故障错误
            raise
        except RuntimeError as e:
            # 通信错误，转换为设备断连异常
            logger.error(f"Communication failed: {e}")
            raise DeviceDisconnectedError(
                f"Failed to communicate with device: {e}",
                reason=str(e)
            ) from e

    def get_tactile_data(self):
        """
        获取触觉传感器数据

        Returns:
            dict: 包含各手指触觉传感器数据的字典，键为TactileSensorId枚举，值为TactileInfo对象

        Raises:
            DeviceDisconnectedError: 设备断开或通信失败
            DataReceiveError: 数据接收异常（长度不匹配）
        """
        try:
            data = self._client.recv_data()

            # 数据长度验证
            if len(data) != 708:
                error_msg = f"Data length insufficient. Expected 708 bytes, got {len(data)} bytes"
                logger.warning(error_msg)
                raise DataReceiveError(
                    error_msg,
                    expected_length=708,
                    actual_length=len(data)
                )

            logger.info("Tactile data received successfully")
            tactile_data = data[148:708]
            logger.debug(f"Tactile data (560 bytes):\n{' '.join(f'{b:02x}' for b in tactile_data)}")

            tpdo = Tpdo.from_bytes(data)
            logger.debug(
                "Parsed TPDO tactile data:\n"
                + "\n".join(
                    [
                        f"tactile_state: {tpdo.tactile_state}",
                        f"thumb_tactile: {tpdo.thumb_tactile}",
                        f"ff_tactile: {tpdo.ff_tactile}",
                        f"mf_tactile: {tpdo.mf_tactile}",
                        f"rf_tactile: {tpdo.rf_tactile}",
                        f"lf_tactile: {tpdo.lf_tactile}",
                    ]
                )
            )

            # 返回一个结构化的字典，使用枚举作为键
            tactile_data = {
                TactileSensorId.THUMB: TactileInfo(
                    state=bool(tpdo.tactile_state.state & (1 << 0)),
                    resultant_force=tpdo.thumb_tactile.resultant_force,
                    distributed_force=tpdo.thumb_tactile.sample_force,
                ),
                TactileSensorId.FOREFINGER: TactileInfo(
                    state=bool(tpdo.tactile_state.state & (1 << 1)),
                    resultant_force=tpdo.ff_tactile.resultant_force,
                    distributed_force=tpdo.ff_tactile.sample_force,
                ),
                TactileSensorId.MIDDLE_FINGER: TactileInfo(
                    state=bool(tpdo.tactile_state.state & (1 << 2)),
                    resultant_force=tpdo.mf_tactile.resultant_force,
                    distributed_force=tpdo.mf_tactile.sample_force,
                ),
                TactileSensorId.RING_FINGER: TactileInfo(
                    state=bool(tpdo.tactile_state.state & (1 << 3)),
                    resultant_force=tpdo.rf_tactile.resultant_force,
                    distributed_force=tpdo.rf_tactile.sample_force,
                ),
                TactileSensorId.LITTLE_FINGER: TactileInfo(
                    state=bool(tpdo.tactile_state.state & (1 << 4)),
                    resultant_force=tpdo.lf_tactile.resultant_force,
                    distributed_force=tpdo.lf_tactile.sample_force,
                ),
            }

            return tactile_data

        except DataReceiveError:
            # 重新抛出数据接收错误
            raise
        except RuntimeError as e:
            # 通信错误，转换为设备断连异常
            raise DeviceDisconnectedError(
                f"Failed to communicate with device: {e}",
                reason=str(e)
            ) from e
