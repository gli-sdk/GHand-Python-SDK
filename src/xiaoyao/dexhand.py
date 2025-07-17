import enum
from client import Client
from subscription import SubscriptionManager

class HandType(enum.Enum):
    UNKNOWN = "unknown"
    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"

class CommType(enum.Enum):
    UNKNOWN = "unknown"
    ETHERCAT = "ethercat"
    CANFD = "canfd"
    RS485 = "rs485"

class GestureType(enum.Enum):
    HAND_OPEN = "hand_open"

class DexHand(object):
    def __init__(self):
        self._client = Client()
        self._hand_type = HandType.UNKNOWN
        self._firmware_version = ""
        self._sub_manager = SubscriptionManager()

    def __del__(self):
        self._client.disconnect()
        pass

    def open(self, type=CommType.ETHERCAT, id="auto"):
        connected = False
        if id == "auto":
            id_list = self._client.search()
            for id in id_list:
                connected = self._client.connect(id)
                if connected:
                    break
        else:
            connected = self._client.connect(id)
        return connected


    def close(self):
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
        self._client.sdo_write(0x2002, 0x01, b'\x01')
        return True

    def joint_init(self):
        self._client.sdo_write(0x2003, 0x00, b'\x01')
        return True

    def tactile_self_test(self):
        self._client.sdo_write(0x2005, 0x00, b'\x01')
        return True

    def tactile_reset(self):
        self._client.sdo_write(0x2006, 0x00, b'\x01')
        return True

    def motor_self_test(self):
        self._client.sdo_write(0x2007, 0x00, b'\x01')
        return True

    def stop(self):
        self._client.sdo_write(0x2007, 0x00, b'\x00')
        return True

    def do_preset_gesture(self, gesture: GestureType):
        if gesture == GestureType.HAND_OPEN:
            self._client.sdo_write(0x2021, 0x00, b'\x01')
        return True

    def get_hand_type(self):
        if self._hand_type == HandType.UNKNOWN:
            type = int.from_bytes(self._client.sdo_read(0x2011), byteorder='little')
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