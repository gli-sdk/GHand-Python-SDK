
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
        self._slave = None

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
            try:
                self._master.send_processdata()
                self._actual_wkc = self._master.receive_processdata(15_000)
                if self._actual_wkc < 1:
                    print(f"Warning: Invalid working counter (WKC): {self._actual_wkc}")
            except Exception as e:
                print(f"Error in process data thread: {e}")
            time.sleep(0.015)

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

    def recv_data(self) -> bytes:
        if self._slave is not None:
            return self._slave.input
        else:
            print("No slave connected")
            return bytes()

    def send_data(self, data: bytes):
        if self._slave is not None:
            print(f"Sending {len(data)} bytes: {data}")
            self._slave.output = data
            print(f"【Joint】发送 PDO 数据成功")

    def search(self) -> list[str]:
        ids = netifaces.interfaces()
        for i, v in enumerate(ids):
            ids[i] = "\\Device\\NPF_" + v
        return ids
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
            self._slave.is_lost = False
            return True
        except Exception as e:
            print(e)
            return False
              
    def run(self):
        if not self._connected or self._slave is None:
            print("Not connected or no slave configured")
            return False
        
        print(f"Number of slaves: {len(self._master.slaves)}")
        for i, slave in enumerate(self._master.slaves):
            print(f"Slave {i}:")
            print(f"  Name: {slave.name}")
            print(f"  Input size: {len(slave.input)} bytes")
            print(f"  Output size: {len(slave.output)} bytes")
            print(f"  State: {slave.state}")
        
        # 直接配置映射并等待完成
        try:
            self._master.config_map()
            print("PDO mapping configured successfully")
        except Exception as e:
            print(f"Failed to configure PDO mapping: {e}")
            self._master.close()
            return False
        
        print("PDO mapping information:")
        for i, slave in enumerate(self._master.slaves):
            print(f"Slave {i}:")
            print(f"  Input size after config_map: {len(slave.input)} bytes")
            print(f"  Output size after config_map: {len(slave.output)} bytes")
        
        # 设置并检查是否进入PREOP状态
        self._master.state = pysoem.PREOP_STATE
        self._master.write_state()
        self._master.read_state()  # 刷新状态
        if self._master.state_check(pysoem.PREOP_STATE, timeout=500_000) != pysoem.PREOP_STATE:
            print("Failed to enter PREOP state")
            for slave in self._master.slaves:
                print(f'{slave.name} did not reach PREOP state')
                print(f'al status code {hex(slave.al_status)} ({pysoem.al_status_code_to_string(slave.al_status)})')
            self._master.close()
            return False       
        
        # 设置并检查是否进入SAFEOP状态
        self._master.state = pysoem.SAFEOP_STATE
        self._master.write_state()
        self._master.read_state()  # 刷新状态
        if self._master.state_check(pysoem.SAFEOP_STATE, timeout=1000_000) != pysoem.SAFEOP_STATE:
            print("Failed to enter SAFEOP state")
            for slave in self._master.slaves:
                if slave.state != pysoem.SAFEOP_STATE:
                    print(f'{slave.name} did not reach SAFEOP state')
                    print(f'al status code {hex(slave.al_status)} ({pysoem.al_status_code_to_string(slave.al_status)})')
            self._master.close()
            return False
            

        print('Switching to OP state...')
        # 设置OP状态
        self._master.state = pysoem.OP_STATE
        self._master.write_state()
        
        # 启动处理线程
        self.check_thread = threading.Thread(target=self._check_thread)
        self.check_thread.daemon = True
        self.check_thread.start()
        self.proc_thread = threading.Thread(target=self._processdata_thread)
        self.proc_thread.daemon = True
        self.proc_thread.start()
        
        # 等待进入OP状态
        self._master.read_state()  # 刷新状态
        if self._master.state_check(pysoem.OP_STATE, timeout=500_000) != pysoem.OP_STATE:
            print("Failed to reach OP state")
            # 如果无法进入OP状态，停止线程
            self._pd_thread_stop_event.set()
            self._ch_thread_stop_event.set()
            # 等待线程结束
            if hasattr(self, 'proc_thread') and self.proc_thread.is_alive():
                self.proc_thread.join(timeout=1.0)
            if hasattr(self, 'check_thread') and self.check_thread.is_alive():
                self.check_thread.join(timeout=1.0)
            self._master.close()
            return False
                
        self._master.in_op = True
        print("OP state reached successfully")
            
        # 打印配置后的从站信息
        print(f"After configuration - Slave input size: {len(self._slave.input)} bytes")
        print(f"After configuration - Slave output size: {len(self._slave.output)} bytes")
        
        return True

    def disconnect(self):
        if self._connected:
            self._pd_thread_stop_event.set()
            self._ch_thread_stop_event.set()
            # 只有在线程存在且活跃时才join
            if hasattr(self, 'proc_thread') and self.proc_thread.is_alive():
                self.proc_thread.join(timeout=1.0)
            if hasattr(self, 'check_thread') and self.check_thread.is_alive():
                self.check_thread.join(timeout=1.0)
            self._master.state = pysoem.INIT_STATE
            self._master.write_state()
            self._master.close()
            self._slave = None
            self._connected = False
    def sdo_read(self, index, subindex=0):
        """
        读取SDO对象字典中的值
        
        Args:
            index: 对象字典索引
            subindex: 子索引，默认为0
        
        Returns:
            读取到的数据
        """
        if self._slave is None:
            raise RuntimeError("No slave connected")
        return self._slave.sdo_read(index, subindex)

    def sdo_write(self, index, subindex, value):
        """
        写入SDO对象字典中的值
        
        Args:
            index: 对象字典索引
            subindex: 子索引
            value: 要写入的值
        """
        if self._slave is None:
            raise RuntimeError("No slave connected")
        return self._slave.sdo_write(index, subindex, value)
