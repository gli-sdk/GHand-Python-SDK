import pysoem
import threading
import time
import logging
import netifaces
import os
import tempfile
import hashlib
import platform

logger = logging.getLogger("xiaoyao.ecatclient")


class EthercatClient(object):
    def __init__(self):
        """
        初始化EtherCAT客户端对象

        注意：已移除单例模式，每个 DexHand 实例都有自己独立的 EthercatClient
        这样可以支持多个网络接口同时连接不同的设备
        """
        self._master = pysoem.Master()
        self._master.in_op = False
        self._master.do_check_state = False
        self._actual_wkc = 0
        self._pd_thread_stop_event = threading.Event()
        self._ch_thread_stop_event = threading.Event()
        self._connected = False
        self._slave = None
        # 添加连接状态标志
        self._connection_lost = False
        # 线程安全锁
        self._data_lock = threading.RLock()
        # 设备独占锁相关
        self._lock_file = None
        self._lock_file_path = None

    def _get_lock_file_path(self, device_id: str) -> str:
        """
        生成设备锁文件路径

        Args:
            device_id (str): 设备ID

        Returns:
            str: 锁文件路径
        """
        # 使用设备ID的哈希值作为锁文件名，避免特殊字符问题
        device_hash = hashlib.md5(device_id.encode()).hexdigest()
        system = platform.system()
        if system == "Windows":
            lock_dir = tempfile.gettempdir()
        else:
            lock_dir = "/tmp"
        return os.path.join(lock_dir, f"xiaoyao_ethernet_{device_hash}.lock")

    def _acquire_lock(self, device_id: str) -> bool:
        """
        尝试获取设备独占锁

        Args:
            device_id (str): 设备ID

        Returns:
            bool: 成功获取锁返回True，否则返回False
        """
        lock_path = self._get_lock_file_path(device_id)
        try:
            # 尝试以独占模式创建/打开锁文件
            if platform.system() == "Windows":
                # Windows: 尝试以独占写入模式打开文件
                try:
                    import msvcrt
                    self._lock_file = open(lock_path, 'w')
                    # 尝试锁定文件
                    msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    # 写入当前进程信息
                    self._lock_file.write(f"{os.getpid()}\n{device_id}\n")
                    self._lock_file.flush()
                    self._lock_file_path = lock_path
                    return True
                except (IOError, OSError):
                    # 文件已被锁定
                    if self._lock_file:
                        self._lock_file.close()
                    self._lock_file = None
                    logger.warning(f"Device {device_id} is already locked by another process")
                    return False
            else:
                # Linux/Unix: 使用flock进行文件锁定
                import fcntl
                self._lock_file = open(lock_path, 'w')
                try:
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # 写入当前进程信息
                    self._lock_file.write(f"{os.getpid()}\n{device_id}\n")
                    self._lock_file.flush()
                    self._lock_file_path = lock_path
                    return True
                except (IOError, OSError):
                    # 文件已被锁定
                    if self._lock_file:
                        self._lock_file.close()
                    self._lock_file = None
                    logger.warning(f"Device {device_id} is already locked by another process")
                    return False
        except Exception as e:
            logger.error(f"Error acquiring lock for device {device_id}: {e}")
            if self._lock_file:
                self._lock_file.close()
            self._lock_file = None
            return False

    def _release_lock(self):
        """
        释放设备独占锁
        """
        if self._lock_file is not None:
            try:
                lock_path = self._lock_file_path
                # 关闭文件（这会自动释放锁）
                self._lock_file.close()
                # 删除锁文件
                if lock_path and os.path.exists(lock_path):
                    try:
                        os.remove(lock_path)
                    except (OSError, IOError):
                        pass  # 忽略删除失败
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
            finally:
                self._lock_file = None
                self._lock_file_path = None

    def __new__(cls, *args, **kwargs):
        """
        创建单例实例

        Args:
            cls: 类对象
            *args: 可变位置参数
            **kwargs: 可变关键字参数

        Returns:
            EthercatClient: 返回EthercatClient类的单例实例
        """
        if not hasattr(cls, '_instance'):
            with cls._instance_lock:
                if not hasattr(cls, '_instance'):
                    cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _check_slave(slave):
        """
        检查从设备状态并进行相应处理

        Args:
            slave: 从设备对象
        """
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
        """
        处理数据的线程函数，负责发送和接收过程数据
        """
        # 添加计数器用于跟踪无效工作计数器的数量
        invalid_wkc_count = 0
        max_invalid_wkc_count = 30

        while not self._pd_thread_stop_event.is_set():
            try:
                with self._data_lock:
                    self._master.send_processdata()
                    self._actual_wkc = self._master.receive_processdata(15_000)
                if self._actual_wkc < 1:
                    logger.warning(f"Invalid working counter (WKC): {self._actual_wkc}")
                    invalid_wkc_count += 1
                    # 当无效计数超过阈值时，触发断开连接
                    if invalid_wkc_count >= max_invalid_wkc_count:
                        logger.error(f"Too many invalid WKC counts ({invalid_wkc_count}), disconnecting...")
                        # 设置连接丢失标志
                        self._connection_lost = True
                        # 在另一个线程中执行断开连接操作，避免死锁
                        threading.Thread(target=self.disconnect).start()
                        # 停止当前线程
                        self._pd_thread_stop_event.set()
                        break
                else:
                    # 重置计数器
                    invalid_wkc_count = 0
            except Exception as e:
                logger.error(f"Error in process data thread: {e}")
            time.sleep(0.01)

    def _check_thread(self):
        """
        检查线程函数，负责监控和检查从设备状态
        """
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
                logger.error(f"Error in check thread: {e}")
            time.sleep(0.01)

    def recv_data(self) -> bytes:
        """
        接收数据

        Returns:
            bytes: 从设备输入数据，如果没有连接从设备则返回空字节
        """
        with self._data_lock:
            if self._connection_lost:
                raise RuntimeError("Connection lost due to too many invalid WKC counts")
            if self._slave is not None:
                return self._slave.input
            else:
                logger.warning("No slave connected")
                return bytes()

    def send_data(self, data: bytes):
        """
        发送数据

        Args:
            data (bytes): 要发送的数据
        """
        with self._data_lock:
            if self._connection_lost:
                raise RuntimeError("Connection lost due to too many invalid WKC counts")
            if self._slave is not None:
                logger.debug(f"Sending {len(data)} bytes: \n{' '.join(f'{b:02x}' for b in data)}")
                self._slave.output = data
            else:
                logger.warning("No slave connected")

    def search(self) -> list[str]:
        """
        搜索网络接口设备

        Returns:
            list[str]: 返回网络接口设备ID列表
        """
        logger.info("Searching for network interfaces...")
        import platform
        ids = netifaces.interfaces()
        # Linux 上直接使用接口名，Windows 需要 NPF_ 前缀
        if platform.system() == 'Windows':
            for i in range(len(ids)):
                ids[i] = "\\Device\\NPF_" + ids[i]
        # Linux/macOS: 直接使用接口名，如 eth0, ens33 等
        logger.info(f"Found {len(ids)} network interface(s)")
        return ids

    def connect(self, id):
        """
        连接指定ID的设备

        Args:
            id (str): 设备ID

        Returns:
            bool: 连接成功返回True，失败返回False
        """
        if self._connected:
            return True

        # 步骤1：尝试获取设备独占锁（防止同SDK多进程）
        if not self._acquire_lock(id):
            logger.error(f"Failed to connect: device {id} is already locked by another Python-SDK process")
            return False

        try:
            # 步骤2：打开网卡并初始化
            self._master.open(id)

            if not self._master.config_init() > 0:
                self._master.close()
                self._release_lock()  # 连接失败时释放锁
                return False
            self._connected = True
            self._slave = self._master.slaves[0]
            self._slave.is_lost = False
            self._master.read_state()  # 刷新状态
            return True
        except Exception as e:
            logger.error(f"Error connecting to device {id}: {e}")
            self._release_lock()  # 异常时释放锁
            return False

    def run(self):
        """
        启动EtherCAT主站并进入操作状态

        Returns:
            bool: 启动成功返回True，失败返回False
        """
        if not self._connected or self._slave is None:
            logger.error("Not connected or no slave configured")
            return False

        expected_input_size = 708
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
                        logger.error(f"Failed to enter INIT state. Current state: {slave.state}")
                        self._master.close()
                        return False

                # 进行配置初始化
                config_result = self._master.config_init()
                if config_result <= 0:
                    logger.error(f"Config init failed with result: {config_result}")
                    self._master.close()
                    return False

                self._master.config_map()
                logger.debug(f"master state: {self._master.state}")
                
                if len(slave.input) != expected_input_size or len(
                    slave.output
                ) != expected_output_size:
                    logger.error("Expected size error!")
                    logger.error(
                        f"Expected input size: {expected_input_size}, "
                        f"actual input size: {len(slave.input)}"
                    )
                    logger.error(
                        f"Expected output size: {expected_output_size}, "
                        f"actual output size: {len(slave.output)}"
                    )
            else:
                logger.warning("No slaves found")
                self._master.close()
                return False
        except Exception as e:
            logger.error(f"Failed to configure PDO mapping: {e}")
            self._master.close()
            return False

        if self._master.state_check(pysoem.SAFEOP_STATE, timeout=500_000) != pysoem.SAFEOP_STATE:

            logger.error("Failed to enter SAFEOP state")
            for i, slave in enumerate(self._master.slaves):
                logger.error(f'Slave {i}: {slave.name}')
                logger.error(f'  Current state: {slave.state}')
                logger.error(f'  Expected state: {pysoem.SAFEOP_STATE}')
                logger.error(
                    f'  AL status code: {hex(slave.al_status)} '
                    f'({pysoem.al_status_code_to_string(slave.al_status)})'
                )
                logger.error(f'  Input size: {len(slave.input)} bytes')
                logger.error(f'  Output size: {len(slave.output)} bytes')
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
            logger.error("Failed to reach OP state")
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
        """
        断开设备连接并清理资源

        Returns:
            None
        """
        if self._connected:
            self._pd_thread_stop_event.set()
            self._ch_thread_stop_event.set()
            # 只有在线程存在且活跃时才join
            thread_join_timeout = 5.0  # 增加超时时间
            if hasattr(self, 'proc_thread') and self.proc_thread.is_alive():
                self.proc_thread.join(timeout=thread_join_timeout)
            if hasattr(self, 'check_thread') and self.check_thread.is_alive():
                self.check_thread.join(timeout=thread_join_timeout)

            # 重置线程停止事件，为下次连接做准备
            self._pd_thread_stop_event.clear()
            self._ch_thread_stop_event.clear()

            with self._data_lock:
                # 先将从站切换为init状态，再关闭主站
                try:
                    if self._slave:
                        # 将从站状态设置为INIT状态
                        self._slave.state = pysoem.INIT_STATE
                        self._slave.write_state()
                        time.sleep(0.01)  # 等待状态切换完成
                except Exception as e:
                    # 如果切换失败，记录警告但继续关闭主站
                    logger.warning(f"Failed to switch slave to INIT state: {e}")

                # 直接关闭主站
                if self._master:
                    self._master.close()
                    logger.info("Master closed")
                self._slave = None
                self._connected = False

                # 释放设备独占锁
                self._release_lock()

                # 重置所有状态标志，为下次连接做准备
                self._actual_wkc = 0
                self._connection_lost = False
                self._master.in_op = False
                self._master.do_check_state = False

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

        Returns:
            写入操作的结果
        """
        with self._data_lock:
            if self._slave is None:
                raise RuntimeError("No slave connected")
            return self._slave.sdo_write(index, subindex, value)