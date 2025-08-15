
import pysoem
import threading
import time
import netifaces


class EthercatClient(object):
    _instance_lock = threading.Lock()

    def __init__(self):
        self._master = pysoem.Master()
        self._master.in_op = False
        self._master.do_check_state = False
        self._actual_wkc = 0
        self._pd_thread_stop_event = threading.Event()
        self._ch_thread_stop_event = threading.Event()
        self._connected = False

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            with cls._instance_lock:
                if not hasattr(cls, '_instance'):
                    cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _check_slave(slave):
        if slave.state == (pysoem.SAFEOP_STATE + pysoem.STATE_ERROR):
            slave.state = pysoem.SAFEOP_STATE + pysoem.STATE_ACK
            slave.write_state()
        elif slave.state == pysoem.SAFEOP_STATE:
            slave.state = pysoem.OP_STATE
            slave.write_state()
        elif slave.state > pysoem.NONE_STATE:
            if slave.reconfig():
                slave.is_lost = False
        elif not slave.is_lost:
            slave.state_check(pysoem.OP_STATE)
            if slave.state == pysoem.NONE_STATE:
                slave.is_lost = True
        else:
            pass
        if slave.is_lost:
            if slave.state == pysoem.NONE_STATE:
                if slave.recover():
                    slave.is_lost = False
            else:
                slave.is_lost = False

    def _processdata_thread(self):
        while not self._pd_thread_stop_event.is_set():
            self._master.send_processdata()
            self._actual_wkc = self._master.receive_processdata(10_000)
            if self._actual_wkc < 1:
                print("no wkc")
            time.sleep(0.01)

    def _check_thread(self):
        while not self._ch_thread_stop_event.is_set():
            if self._master.in_op and (self._actual_wkc < 1 or self._master.do_check_state):
                self._master.do_check_state = False
                self._master.read_state()
                for i, slave in enumerate(self._master.slaves):
                    if slave.state != pysoem.OP_STATE:
                        self._master.do_check_state = True
                        self._check_slave(slave)
            time.sleep(0.01)

    def recv_data(self):
        if self._slave is not None:
            return self._slave.input
        else:
            return None

    def send_data(self, data):
        if self._slave is not None:
            self._slave.output = data

    def connect(self, id):
        if self._connected:
            return True
        try:
            self._master.open(id)
            if not self._master.config_init() > 0:
                self._master.close()
                return False
            self._connected = True
            print("Connected to device with id: ", id)
            self._slave = self._master.slaves[0]
            return True
        except Exception as e:
            print(e)
            return False

    def search(self) -> list[str]:
        ids = netifaces.interfaces()
        for i, v in enumerate(ids):
            ids[i] = "\\Device\\NPF_" + v
        return ids

    def run(self):
        self._master.config_map()
        if self._master.state_check(pysoem.SAFEOP_STATE, timeout=50_000) != pysoem.SAFEOP_STATE:
            self._master.close()
        self._master.state = pysoem.OP_STATE
        self._master.write_state()
        self.check_thread = threading.Thread(target=self._check_thread)
        self.check_thread.start()
        self.proc_thread = threading.Thread(target=self._processdata_thread)
        self.proc_thread.start()
        for i in range(40):
            self._master.state_check(pysoem.OP_STATE, timeout=50_000)
            if self._master.state == pysoem.OP_STATE:
                self._master.in_op = True
            break

    def disconnect(self):
        if self._connected:
            self._pd_thread_stop_event.set()
            self._ch_thread_stop_event.set()
            self.proc_thread.join()
            self.check_thread.join()
            self._master.state = pysoem.INIT_STATE
            self._master.write_state()
            self._master.close()
            self._slave = None

    def sdo_read(self, index, subindex=0):
        return self._slave.sdo_read(self._slave, index, subindex)

    def sdo_write(self, index, subindex, value):
        return self._master.sdo_write(self._slave, index, subindex, value)
