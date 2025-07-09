# src/xiaoyao/_internal/ethercat_client.py (最终版本)

import pysoem
import struct
import sys
import time
import threading

from xiaoyao.common import JointInfo

# ====================================================================
#  对象字典索引 (保持不变)
# ====================================================================
OD_INDEX_DEVICE_IDENTITY = 0x1018
OD_SUBINDEX_VERSION_INFO = 0x03
OD_SUBINDEX_SERIAL_NUMBER = 0x04
OD_INDEX_FACTORY_RESET = 0x1011
OD_SUBINDEX_FACTORY_RESET = 0x01
OD_INDEX_MANU_CUSTOM = 0x2000
OD_SUBINDEX_HAND_ID = 0x01
OD_SUBINDEX_REBOOT = 0x02
OD_INDEX_PROTECTION_TEMP = 0x2001
OD_SUBINDEX_PROTECTION_TEMP = 0x01
OD_INDEX_HAND_TYPE = 0x2012
OD_SUBINDEX_HAND_TYPE = 0x00
# ====================================================================

class EtherCATClient:
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None: cls._instance = cls()
        return cls._instance
    
    def find_adapters(self):
        """查找可用的网络适配器。"""
        # 直接通过类名调用静态方法，不再需要 get_instance()
        return pysoem.find_adapters()

    def __init__(self):
        self.master = pysoem.Master()
        self.is_initialized = False
        self._slave = None
        self._pdo_thread = None
        self._thread_stop_event = threading.Event()
        self._latest_rpdo_data = b''
        self._data_lock = threading.Lock()
        self._tpdo_data_to_send = bytearray(256) # 分配一个足够大的缓冲区

    def connect(self, adapter_name: str, goto_op_state: bool = True) -> bool:
        """连接设备并根据请求决定是否启动OP模式和后台线程。"""
        if self.is_initialized: return True
        try:
            self.master.open(adapter_name)
            if not self.master.config_init() > 0: raise ConnectionError("未发现从站")
            
            self._slave = self.master.slaves[0]
            self._slave.state = pysoem.PREOP_STATE
            self.master.write_state()
            self.master.state_check(0, pysoem.PREOP_STATE, timeout=1000)
            if self.master.read_state() != pysoem.PREOP_STATE: raise ConnectionError("无法进入PRE-OP")
            
            print(f"成功发现设备: {self._slave.name}, 已进入 PRE-OP 状态。")

            if goto_op_state:
                return self.start_op_mode() # 如果需要，直接启动OP模式
            
            self.is_initialized = True
            return True
        except Exception as e:
            self.master.close()
            raise e

    # src/xiaoyao/_internal/ethercat_client.py

    def start_op_mode(self):
        """从PRE-OP转换到OP，并启动心跳线程。"""
        if not self.is_initialized: raise ConnectionError("客户端未初始化")
        if self._slave.state == pysoem.OP_STATE: return True

        print("INFO: 正在配置PDO并切换到OP状态...")
        self.master.config_map()
        
        self._slave.state = pysoem.SAFEOP_STATE
        self.master.write_state()
        self.master.state_check(0, pysoem.SAFEOP_STATE, timeout=5000)
        
        self._slave.state = pysoem.OP_STATE
        self.master.write_state()
        self.master.state_check(0, pysoem.OP_STATE, timeout=5000)
        
        if self.master.read_state() != pysoem.OP_STATE:
            raise ConnectionError(f"无法进入OP状态, AL Status Code: {hex(self._slave.al_status)}")
            
        print("INFO: 设备已进入OP状态。正在启动后台PDO通信线程...")
        self._thread_stop_event.clear()
        self._pdo_thread = threading.Thread(target=self._pdo_heartbeat_loop, daemon=True)
        self._pdo_thread.start()
        
        time.sleep(0.05) # 等待线程稳定启动
        print("INFO: 后台线程已启动。")
        return True

    def disconnect(self):
        if self._pdo_thread and self._pdo_thread.is_alive():
            self._thread_stop_event.set()
            self._pdo_thread.join(timeout=1.0)
        if self.is_initialized:
            try:
                self._slave.state = pysoem.INIT_STATE
                self.master.write_state()
            except: pass
            self.master.close()
        self.is_initialized = False
        EtherCATClient._instance = None
        print("INFO: 连接已关闭。")

    # src/xiaoyao/_internal/ethercat_client.py

    def _pdo_heartbeat_loop(self):
        """【后台线程】持续收发PDO，解析数据，并执行回调。"""
        while not self._thread_stop_event.is_set():
            try:
                with self._data_lock:
                    self._slave.output = bytes(self._tpdo_data_to_send)
                
                self.master.send_processdata()
                wkc = self.master.receive_processdata(timeout=2000)

                # 解析收到的数据
                raw_rpdo = self._slave.input
                parsed_data = self._parse_all_rpdo_data(raw_rpdo)
                
                # 更新缓存并处理回调
                if parsed_data:
                    with self._data_lock:
                        self._latest_parsed_data = parsed_data
                    self._handle_callbacks(parsed_data)

            except pysoem.PacketError: continue
            except Exception as e:
                print(f"[后台线程错误] {e}")
                break
            time.sleep(0.002) # ~500Hz loop

    def _parse_all_rpdo_data(self, raw_data: bytes) -> dict:
        """【统一RPDO解析中心】"""
        # 根据协议V1.2，数据是分块的，假设它们在PDO中是连续排列的
        # 【注意】这里的格式和偏移量需要最终确认
        JOINT_OBJECT_SIZE = 16 # 假设每个关节对象在PDO中占16字节
        
        parsed_dict = {}
        if not raw_data or len(raw_data) < 18 * JOINT_OBJECT_SIZE: return {}

        try:
            # 1. 解析18个关节数据
            joints_list = []
            for i in range(18):
                offset = i * JOINT_OBJECT_SIZE
                # 解析格式: state(B), error(B), 2x(填充), angle(f), speed(f), torque(f)
                state, error, angle, speed, torque = struct.unpack_from('<BB2xfff', raw_data, offset)
                info = JointInfo()
                info.joint_id, info.angle, info.speed, info.torque, info.status = i, angle, speed, torque, state
                joints_list.append(info)
            parsed_dict['joints'] = joints_list

            # 2. 解析整手信息 (假设它跟在所有关节数据后面)
            # offset = 18 * JOINT_OBJECT_SIZE
            # state, temp, err_code = struct.unpack_from(...)
            # parsed_dict['hand_state'] = ...

            return parsed_dict
        except struct.error:
            return {}

    def _handle_callbacks(self, parsed_data: dict):
        """分发回调函数。"""
        with self._sub_lock:
            if 'joints' in parsed_data and 'joint_data' in self._subscribers:
                for callback in self._subscribers['joint_data'].values():
                    # 为了安全，将数据列表的浅拷贝传递给回调
                    callback(list(parsed_data['joints']))

    def get_latest_parsed_data(self) -> dict:
        """线程安全地获取最新解析好的所有数据。"""
        with self._data_lock:
            return self._latest_parsed_data.copy()
                
    def add_subscriber(self, data_type: str, callback) -> int:
        with self._sub_lock:
            sub_id = self._next_sub_id
            self._subscribers[data_type][sub_id] = callback
            self._next_sub_id += 1
            return sub_id

    def remove_subscriber(self, sub_id: int) -> bool:
        with self._sub_lock:
            for data_type in self._subscribers:
                if sub_id in self._subscribers[data_type]:
                    del self._subscribers[data_type][sub_id]
                    return True
        return False                

    # def get_latest_rpdo(self) -> bytes:
    #     with self._data_lock:
    #         return self._latest_rpdo_data

    def sdo_read(self, index, subindex=0):
        if not self.is_initialized: raise ConnectionError("设备未连接。")
        try:
            return self._slave.sdo_read(index, subindex)
        except pysoem.SdoError as e:
            print(f"错误: SDO读取失败 (Index: {index:04X}): {e}")
            return None

    def sdo_write(self, index, subindex, data_bytes):
        if not self.is_initialized: raise ConnectionError("设备未连接。")
        self._slave.sdo_write(index, subindex, data_bytes)

    def is_op_state(self) -> bool:
        if not self.is_initialized: return False
        self.master.read_state()
        return self.master.slaves[0].state == pysoem.OP_STATE
        
    def send_processdata(self):
        if not self.is_initialized: return
        self.master.send_processdata()

    def receive_processdata(self, timeout_us=2000) -> bytes:
        if not self.is_initialized: return b''
        self.master.receive_processdata(timeout_us)
        return self._slave.input
    
    def set_output(self, data: bytes):
        """
        【修改】线程安全地设置下一次要发送的TPDO数据。
        """
        if not self.is_initialized: return
        with self._data_lock:
            # 确保长度一致，避免底层错误
            l = len(data)
            if l <= len(self._tpdo_data_to_send):
                self._tpdo_data_to_send[:l] = data
            else:
                # 如果数据太长，只复制前面部分
                self._tpdo_data_to_send[:] = data[:len(self._tpdo_data_to_send)]