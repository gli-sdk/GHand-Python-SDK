import math
import logging
from .comm.ethercat_comm import EtherCATComm
from .comm.canfd_comm import CANFDComm
from .comm.rs485_comm import RS485Comm
from .comm.icomm import IComm
from .types import (
    ProductType, ProductConfig, JointId, State, ErrorCode,
    HandType, CommType, CtrlMode, TactileSensorId,
    Joint, HandInfo, TactileInfo,
    GHandError, DeviceDisconnectedError, DeviceFaultError,
    JointFaultError, DataReceiveError, FaultInfo, JointFaultInfo,
    get_fault_message,
)
from ._config import load_product_config
from ._subscription import SubscriptionManager
from .comm.ethercat_protocol import JointRpdo, Rpdo, Tpdo

from collision_sdk import CollisionSDK, CollisionCheckResult

from ._converter import joints_to_nparray, nparray_to_joints

logger = logging.getLogger("ghand.ghand")

class GHand(object):
    def __init__(self,
                 product_type: ProductType = ProductType.G5,
                 comm_type: CommType = CommType.ETHERCAT):
        """
        初始化灵巧手对象

        Args:
            product_type: 产品型号，默认 ProductType.G5
            comm_type: 通信类型，默认 CommType.ETHERCAT
        """
        self._product_type = product_type
        self._comm_type = comm_type
        self._product_config = load_product_config(product_type)
        self._joint_limits = {
            jid: (math.radians(mn), math.radians(mx))
            for jid, (mn, mx) in self._product_config.joint_limits.items()
        }
        self._comm = self._create_comm(comm_type)
        self._hand_type = HandType.UNKNOWN
        self._firmware_version = ""
        self._sub_manager = SubscriptionManager(self._comm)
        self._opened = False
        self._safety_margin = 0.0
        self._collision_checker = None

    def __del__(self):
        """
        析构函数，关闭灵巧手设备连接
        """
        self.close()

    def _create_comm(self, comm_type: CommType) -> IComm:
        """根据通信类型创建对应的 IComm 实例"""
        if comm_type == CommType.ETHERCAT:
            return EtherCATComm(self._product_config)
        elif comm_type == CommType.CANFD:
            return CANFDComm(self._product_config)
        elif comm_type == CommType.RS485:
            return RS485Comm(self._product_config)
        else:
            raise ValueError(f"Unknown communication type: {comm_type}")

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
        id_list = self._comm.search_adapters()

        for iface_id in id_list:
            try:
                connected = self._comm.connect(iface_id)
                if connected:
                    connected_interfaces.append(iface_id)
                    self._comm.disconnect()
            except NotImplementedError:
                break
            except Exception:
                pass

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

        if type != self._comm_type:
            self._comm = self._create_comm(type)
            self._comm_type = type
            self._sub_manager = SubscriptionManager(self._comm)

        if id == "auto":
            id_list = self._comm.search_adapters()
            logger.info("Found IDs:\n" + "\n".join([f"\t{id}" for id in id_list]))
            for adapter_id in id_list:
                if self._comm.connect(adapter_id):
                    self._opened = True
                    logger.info(f"Device opened successfully (ID: {adapter_id})")
                    break
                else:
                    logger.error(f"Failed to open device (ID: {adapter_id})")
        else:
            self._opened = self._comm.connect(id)
            if self._opened:
                logger.info(f"Device opened successfully (ID: {id})")
            else:
                logger.error(f"Failed to open device (ID: {id})")

        return self._opened

    def close(self) -> bool:
        """
        关闭灵巧手设备连接

        Returns:
          bool: 关闭成功返回True，失败返回False
        """
        self._sub_manager.stop()
        if self._opened:
            self._comm.disconnect()
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
            self._firmware_version = self._comm.sdo_read(
                0x100A, 0x00).decode('utf-8')
        return self._firmware_version

    def get_device_name(self):
        """
        获取设备名

        Returns:
            str: 获取成功返回设备ID，失败返回空字符串""
        """
        try:
            device_name = self._comm.sdo_read(0x1008, 0x00).decode('utf-8')
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
            hardware_version = self._comm.sdo_read(0x1009, 0x00).decode('utf-8')
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
                self._comm.sdo_read(0x1018, 0x04), byteorder='little')
        except Exception:
            return 0
        return serial_number

    def get_motor_driver_version(self):
        """
        获取电机驱动版本号

        Returns:
            tuple: (主版本号, 子版本号1, 子版本号2)，获取失败返回 (0, 0, 0)
        """
        try:
            main_ver = int.from_bytes(
                self._comm.sdo_read(0x2007, 0x01), byteorder="little"
            )
            sub1_ver = int.from_bytes(
                self._comm.sdo_read(0x2007, 0x02), byteorder="little"
            )
            sub2_ver = int.from_bytes(
                self._comm.sdo_read(0x2007, 0x03), byteorder="little"
            )
        except Exception:
            return (0, 0, 0)
        return (main_ver, sub1_ver, sub2_ver)

    def fault_clearance(self) -> bool:
        """
        故障清除

        Returns:
            bool: 清除成功返回True，失败返回False
        """
        try:
            self._comm.sdo_write(0x2002, 0x01, b'\x01')
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
            self._comm.sdo_write(0x2003, 0x01, b'\x01')
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
        if not self._product_config.has_tactile:
            logger.warning("This product does not support tactile sensors")
            return False
        try:
            self._comm.sdo_write(0x2004, 0x01, b'\x01')
            # 读取结果区（子索引3）
            result_data = self._comm.sdo_read(0x2004, 0x03)
            # 检查结果区数据，如果为0则成功，为1则失败
            if result_data == b'\x00':
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"tactile_open error: {e}", exc_info=True)
            return False

    def tactile_close(self) -> bool:
        """
        关闭触觉传感器

        Returns:
            bool: 关闭成功返回True，失败返回False
        """
        if not self._product_config.has_tactile:
            logger.warning("This product does not support tactile sensors")
            return False
        try:
            self._comm.sdo_write(0x2004, 0x01, b'\x02')
            # 读取结果区（子索引3）
            result_data = self._comm.sdo_read(0x2004, 0x03)
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
        if not self._product_config.has_tactile:
            logger.warning("This product does not support tactile sensors")
            return False
        try:
            self._comm.sdo_write(0x2004, 0x01, b'\x04')
            # 读取结果区（子索引3）
            result_data = self._comm.sdo_read(0x2004, 0x03)
            # 检查结果区数据，如果为0则成功，为1则失败
            if result_data == b'\x00':
                logger.debug("Tactile zero calibration successful")
                return True
            else:
                logger.error(f"tactile_zero failed with result data: {result_data}")
                return False

        except Exception as e:
            logger.error(f"tactile_zero error: {e}", exc_info=True)
            return False

    def get_hand_type(self) -> HandType:
        """
        获取手的类型

        Returns:
            HandType: 成功返回手的类型HandType.LEFT_HAND/HandType.RIGHT_HAND，失败返回HandType.UNKNOWN
        """
        if self._hand_type == HandType.UNKNOWN:
            try:
                htype = self._comm.get_hand_type()
            except Exception:
                return HandType.UNKNOWN
            if htype == 1:
                self._hand_type = HandType.LEFT_HAND
            elif htype == 2:
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
            joint_pdo_map = {
                JointId.THUMB_PIP: rpdo.th_pip,
                JointId.THUMB_MCP: rpdo.th_mcp,
                JointId.THUMB_SWING: rpdo.th_swing,
                JointId.THUMB_ROTATION: rpdo.th_rot,
                JointId.FF_PIP: rpdo.ff_pip,
                JointId.FF_MCP: rpdo.ff_mcp,
                JointId.FF_SWING: rpdo.ff_swing,
                JointId.MF_PIP: rpdo.mf_pip,
                JointId.MF_MCP: rpdo.mf_mcp,
                JointId.RF_PIP: rpdo.rf_pip,
                JointId.RF_MCP: rpdo.rf_mcp,
                JointId.LF_PIP: rpdo.lf_pip,
                JointId.LF_MCP: rpdo.lf_mcp,
            }
            passive_joints = {
                JointId.THUMB_DIP, JointId.FF_DIP, JointId.MF_DIP,
                JointId.RF_DIP, JointId.LF_DIP,
            }

            for joint in joints:
                self._check_speed_limit(joint, mode)
                self._check_torque_limit(joint, mode)

                if mode == CtrlMode.POSITION and joint.id in self._joint_limits:
                    self._check_joint_limit(joint, self._joint_limits[joint.id])

                if joint.id in joint_pdo_map:
                    self._joint_to_pdo(joint, joint_pdo_map[joint.id])
                elif joint.id in passive_joints:
                    logger.debug(f"Skipping passive joint: {JointId(joint.id).name}")
                    continue
                else:
                    logger.warning(f"[Joint] Invalid joint ID: {joint.id}")
                    return False
            self._comm.send_data(rpdo.to_bytes())
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
            self._comm.send_data(rpdo.to_bytes())
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
            data = self._comm.recv_data()

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

                # 规范化角度：避免 -0.0
                angle = joint_tpdo.angle
                if abs(angle) < 1e-10:
                    angle = 0.0

                joints.append(
                    Joint(
                        id=joint_id,
                        angle=joint_tpdo.angle,
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
            data = self._comm.recv_data()

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
        if not self._product_config.has_tactile:
            logger.warning("This product does not support tactile sensors")
            return {}
        try:
            data = self._comm.recv_data()

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

    # ==================== 碰撞检测相关方法 ====================

    def set_safety_margin(self, margin: float) -> None:
        """
        设置碰撞检测的安全边距

        Args:
            margin: 安全边距，范围 [0.0, 1.0]
                    0.0 = 无边距（精确接触）
                    1.0 = 最大边距（2mm）

        Raises:
            ValueError: 如果 margin 超出 [0.0, 1.0] 范围

        Example:
            >>> hand = GHand()
            >>> hand.open(CommType.ETHERCAT, "auto")
            >>> hand.set_safety_margin(0.5)  # 设置1mm安全边距
        """
        # 限制在有效范围内
        if margin < 0.0 or margin > 1.0:
            logger.warning(
                f"Safety margin {margin} out of range [0.0, 1.0], clamping to valid range"
            )
            margin = max(0.0, min(1.0, margin))

        self._safety_margin = margin
        logger.info(f"Collision safety margin set to {margin} ({margin * 2:.1f} mm)")

    def _ensure_collision_checker(self):
        """确保碰撞检测器已初始化（延迟加载）"""
        if self._collision_checker is None:
            self._collision_checker = CollisionSDK()
        return self._collision_checker

    def check_collision(self, joints: list[Joint]) -> CollisionCheckResult:
        """
        检查目标关节姿态是否会发生碰撞。

        此方法仅进行碰撞检测并返回结果，不会执行任何关节运动。
        如果检测到碰撞，返回的结果中会包含安全角度。

        Args:
            joints: 关节列表。未指定的关节将使用当前关节角度（设备已连接）
                    或 0°（设备未连接）填充。

        Returns:
            CollisionCheckResult: 碰撞检测结果，包含 has_collision、safe_angles 和
                                   collision_pairs。

        Example:
            >>> hand = GHand()
            >>> result = hand.check_collision(joints)
            >>> if result.has_collision:
            ...     print("检测到碰撞，使用安全角度")
            ...     joints = hand._angles_to_joints(result.safe_angles)
        """
        collision_checker = self._ensure_collision_checker()

        # 获取当前关节状态（用于填充未指定的关节）
        current_joints = None
        if self._opened:
            try:
                current_joints = self.get_joints()
            except Exception:
                logger.debug("无法获取当前关节状态，使用默认值（0度）")

        # 转换 Joint 列表为 numpy 数组
        target_angles = joints_to_nparray(joints, current_joints)

        # 调用 CollisionSDK 进行碰撞检测
        result = collision_checker.collision_check(
            target_angles=target_angles,
            safety_margin=self._safety_margin
        )

        # 若未碰撞，将 safe_angles 设为 target_angles 便于调用方统一处理
        if not result.has_collision:
            result = CollisionCheckResult(
                has_collision=False,
                safe_angles=target_angles.copy(),
                collision_pairs=None,
            )
        return result

    def _joints_to_angles(self, joints: list[Joint], current_joints: list[Joint] | None = None):
        """
        将Joint列表转换为numpy数组（私有方法）

        Args:
            joints: 关节列表
            current_joints: 当前关节状态（用于填充未指定的关节）

        Returns:
            np.ndarray: 18个关节角度的数组
        """
        return joints_to_nparray(joints, current_joints)

    def _angles_to_joints(self, angles, speed: int = 100, torque: int = 100) -> list[Joint]:
        """
        将numpy数组转换为Joint列表（私有方法）

        Args:
            angles: 18个关节角度的numpy数组
            speed: 所有关节的速度参数
            torque: 所有关节的力矩参数

        Returns:
            list[Joint]: 18个Joint对象的列表
        """
        return nparray_to_joints(angles, speed, torque)
