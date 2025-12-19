import threading
import time
import pysoem
import netifaces
import struct
from .data import Rpdo, Tpdo


class Client(object):
    _instance_lock = threading.Lock()

    def __init__(self):
        self._connected = False
        self._master = pysoem.Master()
        self._slave = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            with cls._instance_lock:
                if not hasattr(cls, '_instance'):
                    cls._instance = super().__new__(cls)
        return cls._instance

    def search(self):
        ids = netifaces.interfaces()
        for i, v in enumerate(ids):
            ids[i] = "\\Device\\NPF_" + v
        return ids

    def connect(self, id):
        if self._connected:
            return True
        try:
            self._master.open(id)
            self._master.sdo_read_timeout = 1000
        except:
            return False
        if self._master.config_init() <= 0:
            self._master.close()
            return False
        else:
            self._connected = True
            print("Connected to device with id: ", id)
            self._slave = self._master.slaves[0]
            return True

    def disconnect(self):
        if self._connected:
            self._master.close()
            self._connected = False

    def pdo_init(self):
        self._master.config_map()
        self._slave.state = pysoem.SAFEOP_STATE
        self._master.write_state()
        time.sleep(0.01)
        if self._master.read_state() != pysoem.SAFEOP_STATE:
            print("Failed to change state to SAFEOP")
            return False
        self._slave.state = pysoem.OP_STATE
        self._master.write_state()
        time.sleep(0.01)
        if self._master.read_state() != pysoem.OP_STATE:
            print("Failed to change state to OP")
            return False
        return True

    def sdo_read(self, index, subindex=0):
        return self._slave.sdo_read(index, subindex)

    def sdo_write(self, index, subindex, value):
        return self._slave.sdo_write(index, subindex, value)

    def recv_data(self):
        if not self._connected:
            return {}
        with self._instance_lock:
            self._master.send_processdata()
            self._master.receive_processdata()
            data = self._slave.input
            tpdo = Tpdo().from_bytes(data)
            return tpdo

    def send_thread(self):
        pass

    def recv_thread(self):
        pass
