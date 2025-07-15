# src/xiaoyao/_internal/ethercat_client.py

import pysoem
import struct
import sys
import time
import threading

from xiaoyao import hand
from xiaoyao.common import NUM_JOINTS, JointInfo

class EtherCATClient:
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None: cls._instance = cls()
        return cls._instance
    
    def find_adapters():
        """查找可用的网络适配器。"""
        return EtherCATClient.get_instance().find_adapters()
    
    def auto_connect_to_hand():
        print("--- 正在自动扫描并连接灵巧手 ---")
        try:
            adapters = hand.find_adapters()
            if not adapters:
                print("错误: 未找到任何网络适配器。请确认：")
                print("1. Npcap 驱动已正确安装 (并勾选了'WinPcap API兼容模式')。")
                print("2. 您正以管理员/root权限运行此脚本。")
                return False
        except Exception as e:
            print(f"查找适配器时出错: {e}")
            return False

        for adapter in adapters:
            adapter_desc = adapter.desc.decode('utf-8', errors='ignore')
            print(f"[*] 正在尝试适配器: {adapter_desc} ...")
            
            try:
                # 尝试连接，如果此适配器连接着从站，则会成功进入PRE-OP并返回True
                if hand.open_ethercat(adapter.name):
                    print(f"[成功] 已通过适配器 '{adapter_desc}' 连接到灵巧手。\n")
                    return True # 连接成功，返回True
            except Exception:
                # 捕获所有可能的连接异常（如超时、未找到从站等）
                # 这是预料之中的失败，我们只需重置客户端并继续尝试下一个
                hand.close_device() 
                continue
                
        return False # 如果遍历完所有适配器都未成功，则返回False

    def __init__(self):
        self.master = pysoem.Master()
        self.is_initialized = False
        self._slave = None
        self._pdo_thread = None
        self._thread_stop_event = threading.Event()
        self._latest_rpdo_data = b''
        self._data_lock = threading.Lock()
        self._tpdo_data_to_send = bytearray(256)


    def connect(self, adapter_name: str) -> bool:
        if self.is_initialized: return True
        try:
            self.master.open(adapter_name)
            if not self.master.config_init() > 0:
                self.master.close()
                raise ConnectionError("未在网络上发现任何EtherCAT从站设备。")
            
            self._slave = self.master.slaves[0]
            self._slave.state = pysoem.PREOP_STATE
            self.master.write_state()
            # 增加一点延时等待状态写入
            time.sleep(0.01)
            self.master.state_check(0, pysoem.PREOP_STATE, timeout=1000)
            
            if self.master.read_state() != pysoem.PREOP_STATE:
                raise ConnectionError(f"设备无法进入 PRE-OP 状态。AL Status Code: {hex(self._slave.al_status)}")
            
            print(f"  -> 设备 '{self._slave.name}' 已成功发现并进入 PRE-OP 状态。")
            self.is_initialized = True
            return True
        except Exception as e:
            # 确保在任何失败情况下都关闭 master
            if self.master.is_open:
                self.master.close()
            # 重置内部状态
            self.is_initialized = False
            self._slave = None
            raise e # 将异常继续向上抛出，由调用者处理

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

    def _pdo_heartbeat_loop(self):
        while not self._thread_stop_event.is_set():
            try:
                # 线程安全地获取要发送的数据
                with self._data_lock:
                    self._slave.output = bytes(self._tpdo_data_to_send)
                
                self.master.send_processdata()
                # 增加一个合理的超时
                wkc = self.master.receive_processdata(timeout=2000)

                if wkc > 0:
                    raw_rpdo = self._slave.input
                    parsed_data = self._parse_all_rpdo_data(raw_rpdo)
                    
                    if parsed_data:
                        # 线程安全地更新缓存
                        with self._data_lock:
                            self._latest_parsed_data = parsed_data
                        # 处理回调
                        self._handle_callbacks(parsed_data)
                else:
                    # 如果WKC为0，可能意味着通信中断
                    time.sleep(0.01) # 短暂等待，避免空转CPU过载
                    continue

            except pysoem.PacketError: 
                # 这是非致命错误，通常是网络抖动，继续循环
                continue
            except Exception as e:
                print(f"[后台线程严重错误] {e} - 线程即将停止。")
                break
            
            # 控制循环频率，约500Hz
            time.sleep(0.002) 

    def _parse_all_rpdo_data(self, raw_data: bytes) -> dict:
        parsed_dict = {}
        # 协议确认: 18个关节 * 每个16字节 = 288字节
        # 协议确认: 额外信息 state(1) + temp(1) + err_code(1) = 3字节
        # 总长度至少为 288 + 3 = 291 字节
        EXPECTED_MIN_LENGTH = (18 * 16) + 3 
        
        if not raw_data or len(raw_data) < EXPECTED_MIN_LENGTH: 
            return {}

        try:
            # 1. 解析18个关节数据
            joints_list = []
            JOINT_OBJECT_SIZE = 16
            for i in range(18):
                offset = i * JOINT_OBJECT_SIZE
                # 解析格式: state(B), error(B), 2x(填充), angle(f), speed(f), torque(f)
                state, error, angle, speed, torque = struct.unpack_from('<BB2xfff', raw_data, offset)
                info = JointInfo()
                info.joint_id, info.angle, info.speed, info.torque, info.status = i, angle, speed, torque, state
                joints_list.append(info)
            parsed_dict['joints'] = joints_list

            # 2. 解析整手信息 (紧跟在关节数据之后)
            hand_info_offset = 18 * JOINT_OBJECT_SIZE
            # 解析格式: hand_state(B), temperature(b), error_code(B)
            hand_state, temperature, error_code = struct.unpack_from('<BbB', raw_data, hand_info_offset)
            parsed_dict['hand_state'] = hand_state
            parsed_dict['hand_temperature'] = temperature
            parsed_dict['error_code'] = error_code

            # 未来可以在此继续解析传感器等其他数据...

            return parsed_dict
        except struct.error:
            # 数据长度或格式不匹配
            return {}
        
    def get_error_code() -> int:
        """获取当前的错误码。"""
        data = EtherCATClient.get_realtime_data()
        return data.get('error_code', 0)

    def get_sensor_data() -> list:
        """获取11个传感器的浮点型数据列表。"""
        data = EtherCATClient.get_realtime_data()
        return data.get('sensor_floats', [])
    
    def execute_command(self, command_code: int) -> bool:
        if not self.is_op_state():
            print("错误: 设备未处于OP状态，无法发送指令。")
            return False
        
        try:
            # 此处假设指令码通过一个2字节的短整型发送
            tpdo_data = struct.pack('<H', command_code)
            self.set_output(tpdo_data)
            
            # 短暂等待以确保指令被处理
            time.sleep(0.004)
            return True
        except Exception as e:
            print(f"发送指令时发生错误: {e}")
            return False

    def connect_for_setup(adapter_name: str) -> bool:
        """第一步：连接并进入配置模式。"""
        return EtherCATClient.get_instance().connect_to_preop(adapter_name)

    def start_pdo_communication() -> bool:
        print("【SDK】正在请求启动实时通信模式 (OP)...")
        try:
            return EtherCATClient.get_instance().start_op_mode()
        except Exception as e:
            print(f"【SDK】启动实时通信失败: {e}")
            return False
    
    # --- 上层便捷API ---
    def send_command(command_code: int) -> bool:
        """
        向设备发送一个2字节的指令码。
        这是改变设备应用状态的关键函数。
        :param command_code: 要发送的整数指令码。
        :return: True 如果指令被成功发送。
        """
        client = EtherCATClient.get_instance()
        if not client.is_op_state():
            print("错误: 设备未处于OP状态，无法发送指令。")
            return False
        
        # 直接使用 client 的底层方法来发送数据
        try:
            client.set_output(struct.pack('<H', command_code))
            client.master.send_processdata()
            client.master.receive_processdata(timeout=2000)
            return True
        except Exception as e:
            print(f"发送指令时发生错误: {e}")
            return False

    def _handle_callbacks(self, parsed_data: dict):
        """分发回调函数。"""
        with self._sub_lock:
            if 'joints' in parsed_data and 'joint_data' in self._subscribers:
                for callback in self._subscribers['joint_data'].values():
                    # 为了安全，将数据列表的浅拷贝传递给回调
                    callback(list(parsed_data['joints']))

    def get_latest_parsed_data(self) -> dict:
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
    
    def set_output(self, data: bytes):
        if not self.is_initialized: return
        with self._data_lock:
            l = len(data)
            # 使用切片赋值来覆盖，而不是重新分配内存
            if l <= len(self._tpdo_data_to_send):
                self._tpdo_data_to_send[:l] = data
                # 如果新数据比旧数据短，用0填充剩余部分
                for i in range(l, len(self._tpdo_data_to_send)):
                    self._tpdo_data_to_send[i] = 0
            else:
                self._tpdo_data_to_send[:] = data[:len(self._tpdo_data_to_send)]