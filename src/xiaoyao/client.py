import threading
import pysoem
import netifaces
import struct
from message import Message
class Client(object):
    _connected = False
    _instance_lock = threading.Lock()
    _master = pysoem.Master()
    _slave = None

    def __init__(self):
        pass

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
        return  ids


    def connect(self, id):
        if self._connected:
            return True
        try:
            self._master.open(id)
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

    def send(self, message: Message):
        pass

    def recv(self, message: Message):
        pass

    def sdo_read(self, index, subindex=0):
        return self._slave.sdo_read(index, subindex)
    
    def sdo_write(self, index, subindex, value):
        return self._slave.sdo_write(index, subindex, value)

    def recv_data(self):
        if not self._connected:
            return {}
        with self._instance_lock:
            self._master.receive_processdata()
            data = self._slave.input
            data_struct = struct.unpack('<H', data)

            return {
            "temp": 25, 
            "thumb1": {"state": 0, "error": 0, "angle": 0, "speed": 0,"torque": 0}, 
            "thumb2": {"state": 0, "error": 0, "angle": 0, "speed": 0,"torque": 0}}

    def send_thread(self):
        pass
    def recv_thread(self):
        pass