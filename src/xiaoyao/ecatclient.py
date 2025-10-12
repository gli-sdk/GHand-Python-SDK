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
        # 线程安全锁
        self._data_lock = threading.RLock()
        
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
                with self._data_lock:
                    self._master.send_processdata()
                    self._actual_wkc = self._master.receive_processdata(15_000)
                if self._actual_wkc < 1:
                    print(f"Warning: Invalid working counter (WKC): {self._actual_wkc}")
            except Exception as e:
                print(f"Error in process data thread: {e}")
            time.sleep(0.01)

    def _check_thread(self):
        while not self._ch_thread_stop_event.is_set():
            try:
                need_check = False
                with self._data_lock:
                    if self._master.in_op and (self._actual_wkc < 1 or self._master.do_check_state):
                        self._master.do_check_state = False
                        self._master.read_state()
                        need_check = True
                
                if need_check:
                    with self._data_lock:
                        for i, slave in enumerate(self._master.slaves):
                            if slave.state != pysoem.OP_STATE:
                                self._master.do_check_state = True
                                self._check_slave(slave)
            except Exception as e:
                print(f"Error in check thread: {e}")
            time.sleep(0.01)

    def recv_data(self) -> bytes:
        with self._data_lock:
            if self._slave is not None:
                return self._slave.input
            else:
                print("No slave connected")
                return bytes()

    def send_data(self, data: bytes):
        with self._data_lock:
            if self._slave is not None:
                print(f"Sending {len(data)} bytes: {' '.join(f'{b:02x}' for b in data)}")
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
            self._master.read_state()  # 刷新状态
            return True
        except Exception as e:
            print(e)
            return False
              
    def run(self):
        if not self._connected or self._slave is None:
            print("Not connected or no slave configured")
            return False
        
        expected_input_size = 208
        expected_output_size = 80
        
        # 进入初始状态
        if self._master.state != pysoem.INIT_STATE:
            self._master.state = pysoem.INIT_STATE
        
        # 配置映射并等待完成
        try:
            # 确保从站在INIT状态才能进行映射
            if len(self._master.slaves) > 0:
                slave = self._master.slaves[0]

                if slave.state != pysoem.INIT_STATE:
                    slave.state = pysoem.INIT_STATE
                    slave.write_state()
                    # 等待状态转换完成
                    if slave.state_check(pysoem.INIT_STATE, timeout=100_000) != pysoem.INIT_STATE:
                        print(f"Failed to enter INIT state. Current state: {slave.state}")
                        self._master.close()
                        return False
                
                # 进行配置初始化
                config_result = self._master.config_init()
                if config_result <= 0:
                    print(f"Config init failed with result: {config_result}")
                    self._master.close()
                    return False
                
                self._master.config_map()
                print("master state: ", self._master.state)
                
                if len(slave.input) != expected_input_size or len(slave.output) != expected_output_size:
                    print("Expected size errror!")
                    print(f"Expected input size: {expected_input_size}, actual input size: {len(slave.input)}") 
                    print(f"Expected output size: {expected_output_size}, actual output size: {len(slave.output)}")
            else:
                    print("No slaves found")
                    self._master.close()
                    return False
        except Exception as e:
            print(f"Failed to configure PDO mapping: {e}")
            self._master.close()
            return False
        
        
        if self._master.state_check(pysoem.SAFEOP_STATE, timeout=500_000) != pysoem.SAFEOP_STATE:
            print("Failed to enter SAFEOP state")
            for i, slave in enumerate(self._master.slaves):
                print(f'Slave {i}: {slave.name}')
                print(f'  Current state: {slave.state}')
                print(f'  Expected state: {pysoem.SAFEOP_STATE}')
                print(f'  AL status code: {hex(slave.al_status)} ({pysoem.al_status_code_to_string(slave.al_status)})')
                print(f'  Input size: {len(slave.input)} bytes')
                print(f'  Output size: {len(slave.output)} bytes')
            self._master.close()
            return False

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
        
        # 等待进入OP状态，增加超时时间
        self._master.read_state()  # 刷新状态
        if self._master.state_check(pysoem.OP_STATE, timeout=500_000) != pysoem.OP_STATE:
            print("Failed to reach OP state")
            # 如果无法进入OP状态，停止线程
            self._pd_thread_stop_event.set()
            self._ch_thread_stop_event.set()
            # 等待线程结束
            thread_join_timeout = 5.0  # 增加超时时间
            if hasattr(self, 'proc_thread') and self.proc_thread.is_alive():
                self.proc_thread.join(timeout=thread_join_timeout)
            if hasattr(self, 'check_thread') and self.check_thread.is_alive():
                self.check_thread.join(timeout=thread_join_timeout)
            self._master.close()
            return False
                
        self._master.in_op = True
        
        return True

    def disconnect(self):
        if self._connected:
            self._pd_thread_stop_event.set()
            self._ch_thread_stop_event.set()
            # 只有在线程存在且活跃时才join
            thread_join_timeout = 5.0  # 增加超时时间
            if hasattr(self, 'proc_thread') and self.proc_thread.is_alive():
                self.proc_thread.join(timeout=thread_join_timeout)
            if hasattr(self, 'check_thread') and self.check_thread.is_alive():
                self.check_thread.join(timeout=thread_join_timeout)
            with self._data_lock:
                # 直接关闭主站
                if self._master:
                    self._master.close()
                    print("Master closed")
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
        with self._data_lock:
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
        with self._data_lock:
            if self._slave is None:
                raise RuntimeError("No slave connected")
            return self._slave.sdo_write(index, subindex, value)
        