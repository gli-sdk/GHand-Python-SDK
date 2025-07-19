import enum
from typing import Optional
from client import Client
from subscription import SubscriptionManager
from data import JointRpdo, Rpdo
from dataclasses import dataclass

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

@dataclass
class Joint:
    id: str = ""
    angle: float = 0.0
    speed: float = 0.0
    torque: float = 0.0

class GestureType(enum.Enum):
    HAND_OPEN = "hand_open"

class DexHand(object):
    def __init__(self):
        self._client = Client()
        self._hand_type = HandType.UNKNOWN
        self._firmware_version = ""
        self._sub_manager = SubscriptionManager()
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

    def open(self, type=CommType.ETHERCAT, id="auto"):
        connected = False
        if type == CommType.ETHERCAT:
            if id == "auto":
                id_list = self._client.search()
                for id in id_list:
                    connected = self._client.connect(id)
                    if connected:
                        break
            else:
                connected = self._client.connect(id)
        elif type == CommType.CANFD:
            connected = self._client.connect(id)
        elif type == CommType.RS485:
            connected = self._client.connect(id)
        return connected


    def close(self):
        self._client.disconnect()
        return True

    def get_firmware_version(self):
        if self._firmware_version == "":
            self._firmware_version = self._client.sdo_read(0x100A, 0x00).decode('utf-8')
        return self._firmware_version


    # 解除保护
    def release_protection(self):
        self._client.sdo_write(0x2001, 0x00, b'\x01')
        return True

    def reboot(self):
        try:
            self._client.sdo_write(0x2002, 0x01, b'\x01')
        except Exception:
            return False
        return True

    def joint_init(self):
        try:
            self._client.sdo_write(0x2003, 0x00, b'\x01')
        except Exception:
            return False
        return True

    def tactile_self_test(self):
        try:
            self._client.sdo_write(0x2005, 0x00, b'\x01')
        except Exception:
            return False
        return True

    def tactile_reset(self):
        try:
            self._client.sdo_write(0x2006, 0x00, b'\x01')
        except Exception:
            return False
        return True

    def motor_self_test(self):
        try:
            self._client.sdo_write(0x2007, 0x00, b'\x01')
        except Exception:
            return False
        return True

    def stop(self):
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

    def get_hand_type(self):
        if self._hand_type == HandType.UNKNOWN:
            try:
                type = int.from_bytes(self._client.sdo_read(0x2011), byteorder='little')
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

    def move_joints(self, th_pip: Optional[Joint]=None, th_mcp: Optional[Joint]=None, th_swing: Optional[Joint]=None, th_rot: Optional[Joint]=None, ff_pip: Optional[Joint]=None,ff_mcp: Optional[Joint]=None,ff_swing: Optional[Joint]=None, mf_pip: Optional[Joint]=None,mf_mcp: Optional[Joint]=None, rf_pip: Optional[Joint]=None, rf_mcp: Optional[Joint]=None, lf_pip: Optional[Joint]=None, lf_mcp: Optional[Joint]=None, ctrl_mode=CtrlMode.POSITION):
        if not self._client._connected:
            return False
        rpdo = Rpdo(mode=ctrl_mode.value)
        # Check joint limit
        if th_pip is not None:
            self._joint_to_pdo(th_pip, rpdo.th_pip)
        if th_mcp is not None:
            self._joint_to_pdo(th_mcp, rpdo.th_mcp)
        if th_swing is not None:
            self._joint_to_pdo(th_swing, rpdo.th_swing)
        if th_rot is not None:
            self._joint_to_pdo(th_rot, rpdo.th_rot)
        if ff_pip is not None:
            self._joint_to_pdo(ff_pip, rpdo.ff_pip)
        if ff_mcp is not None:
            self._joint_to_pdo(ff_mcp, rpdo.ff_mcp)
        if ff_swing is not None:
            self._joint_to_pdo(ff_swing, rpdo.ff_swing)
        if mf_pip is not None:
            self._joint_to_pdo(mf_pip, rpdo.mf_pip)
        if mf_mcp is not None:
            self._joint_to_pdo(mf_mcp, rpdo.mf_mcp)
        if rf_pip is not None:
            self._joint_to_pdo(rf_pip, rpdo.rf_pip)
        if rf_mcp is not None:
            self._joint_to_pdo(rf_mcp, rpdo.rf_mcp)
        if lf_pip is not None:
            self._joint_to_pdo(lf_pip, rpdo.lf_pip)
        if lf_mcp is not None:
            self._joint_to_pdo(lf_mcp, rpdo.lf_mcp)
        self._client._slave.output = rpdo.to_bytes()
        return True
