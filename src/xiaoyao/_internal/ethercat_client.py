# src/xiaoyao/_internal/ethercat_client.py (最终版本)

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

    def connect_to_hand(adapter_name: str, setup_only: bool = False) -> bool:
        try:
            # goto_op_state 的值为 True 当且仅当 setup_only 为 False
            return EtherCATClient.get_instance().connect(
                adapter_name=adapter_name, 
                goto_op_state=(not setup_only)
            )
        except Exception as e:
            print(f"【Hand】底层连接过程中发生错误: {e}")
            return False 

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

    def open_ethercat(adapter_name: str) -> bool:
        """
        打开EtherCAT设备并进入 PRE-OP (配置) 状态。
        """
        print(f"【Hand】正在打开 EtherCAT 设备至配置模式: {adapter_name}...")
        # 内部调用核心连接函数，并明确指定 setup_only=True
        return EtherCATClient.connect_to_hand(adapter_name, setup_only=True)

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
        
    def get_error_code() -> int:
        """获取当前的错误码。"""
        data = EtherCATClient.get_realtime_data()
        return data.get('error_code', 0)

    def get_sensor_data() -> list:
        """获取11个传感器的浮点型数据列表。"""
        data = EtherCATClient.get_realtime_data()
        return data.get('sensor_floats', [])
    
    def execute_command(command_code: int) -> bool:
        """
        【内部函数】向设备发送一个2字节的指令码。
        这是在当前2字节TPDO配置下，唯一能做的控制。
        :param command_code: 要发送的整数指令码。
        :return: True 如果指令被成功发送，否则 False。
        """
        client = EtherCATClient.get_instance()
        if not client.is_op_state():
            print("错误: 设备未处于OP状态，无法发送指令。")
            return False
        
        try:
            # 将指令码打包成2个字节 (unsigned short)
            tpdo_data = struct.pack('<H', command_code)
            
            # 将数据写入输出缓冲区并发送
            client.set_output(tpdo_data)
            client.send_processdata()
            
            # 为了确保指令被接收，我们可以等待一个或两个通信周期
            time.sleep(0.004)
            
            return True
        except Exception as e:
            print(f"发送指令时发生错误: {e}")
            return False

    def _update_and_get_rpdo_data() -> tuple:
        """执行一个PDO通信周期，并返回解析后的RPDO数据元组。"""
        client = EtherCATClient.get_instance()
        if not client.is_op_state():
            print("警告: PDO通信需要设备处于OP状态。")
            return None
            
        client.send_processdata()
        input_data = client.receive_processdata()
        # RPDO (PC接收, 来自灵巧手 - 0x6001)
        RPDO_FORMAT = (
            '< 18h 18H 18H 5x 30h B b H'
        )
        RPDO_STRUCT = struct.Struct(RPDO_FORMAT)

        # 假设第一个字节为控制模式: 1=单关节, 2=所有关节
        TPDO_BUFFER = bytearray(1 + 8 + 78) # 1(mode) + 8(single) + 78(all) = 87 bytes


        if not input_data or len(input_data) < RPDO_STRUCT.size:
            # print(f"【PDO调试】: 长度不匹配! 期望: {RPDO_STRUCT.size}, 实际: {len(input_data)}")
            return None

        try:
            return RPDO_STRUCT.unpack(input_data[:RPDO_STRUCT.size])
        except struct.error as e:
            print(f"【PDO调试】: 数据解析错误: {e}.")
            return None


    def _send_pdo_command(target_index_start: int, data_format: str, *data_args):
        """【内部函数】用于构造并发送一个通用的TPDO指令。"""
        client = EtherCATClient.get_instance()
        if not client.is_op_state():
            print("错误：设置关节需要设备处于OP状态。")
            return False

        try:
            command_type = 0x01 # 关节指令
            buffer = struct.pack(f'<BH{data_format}', command_type, target_index_start, *data_args)
            
            client.set_output(buffer)
            client.send_processdata()
            return True
        except struct.error as e:
            print(f"打包PDO指令时发生错误: {e}")
            return False    

    def connect_for_setup(adapter_name: str) -> bool:
        """第一步：连接并进入配置模式。"""
        return EtherCATClient.get_instance().connect_to_preop(adapter_name)

    def start_pdo_communication() -> bool:
        """第二步：启动高速PDO通信。"""
        return EtherCATClient.get_instance().start_op_mode()

    def _exchange_pdo_data(tpdo_value: int = 0) -> bytes:
        """
        执行一次完整的PDO数据交换。
        - 发送一个2字节的TPDO（默认为0，作为心跳）。
        - 接收硬件返回的RPDO数据。
        - 如果在交换后掉线，则抛出异常。
        """
        client = EtherCATClient.get_instance()

        # 1. 准备并发送TPDO (根据硬件要求的2字节长度构建)
        tpdo_data = struct.pack('<H', tpdo_value)
        client.set_output(tpdo_data)
        
        # 2. 执行发送和接收
        client.send_processdata()
        rpdo_data = client.receive_processdata()

        # 3. 交换后立即检查状态，确保链路稳定
        if not client.is_op_state():
            raise ConnectionError("设备在PDO交换后从OP状态掉线。请与硬件方确认2字节TPDO心跳包的正确内容。")
        
        return rpdo_data
    
    def _execute_pdo_cycle(command_code: int = 0) -> bytes:
        """
        执行一次完整的PDO通信周期。
        :param command_code: 要发送的2字节指令码。
        :return: 接收到的48字节RPDO数据，失败则返回空bytes。
        """
        client = EtherCATClient.get_instance()
        if not client.is_op_state():
            print("错误: 设备未处于OP状态。")
            return b''
            
        client.set_output(struct.pack('<H', command_code))
        client.send_processdata()
        return client.receive_processdata()
    
    def get_realtime_data() -> dict:
        """
        【PDO】从输入缓冲区获取并解析所有最新的实时数据。
        """
        JOINT_BLOCK_SIZE = 16
        client = EtherCATClient.get_instance()
        if not client.is_op_state():
            return {}

        # 假设 client.get_raw_pdo_inputs() 返回原始的PDO输入字节串
        raw_bytes = client.get_latest_rpdo() 

        if not raw_bytes or len(raw_bytes) < (NUM_JOINTS * JOINT_BLOCK_SIZE):
            # 字节太短，无法解析
            return {}
        
        # 初始化用于存放解析结果的列表
        joint_angles = []
        joint_speeds = []
        joint_torques = []
        
        # --- 核心解析逻辑 ---
        try:
            # 遍历18个关节的数据块
            for i in range(NUM_JOINTS):
                # 计算当前关节块的起始偏移量
                offset = i * JOINT_BLOCK_SIZE
                
                # 从偏移量处解析数据
                # 'B' = unsigned char (1 byte) for state
                # 'x' = padding byte
                # 'f' = float (4 bytes)
                # '<' 表示小端字节序 (Little-endian)，EtherCAT标准
                # 我们只关心 angle, speed, torque
                _state, angle, speed, torque = struct.unpack_from('<B 3x f f f', raw_bytes, offset)
                
                joint_angles.append(angle)
                joint_speeds.append(speed)
                joint_torques.append(torque)

            # --- 解析其他数据 ---
            # 假设关节数据块之后是整手信息 (0x6041)
            # 偏移量 = 18 * 16 = 288
            other_data_offset = NUM_JOINTS * JOINT_BLOCK_SIZE
            
            # 解析整手信息: operating_state(u8), hand_temperature(i8), error_code(u8)
            # '<B b B' -> u-char, char, u-char
            op_state, temp, err_code = struct.unpack_from('<B b B', raw_bytes, other_data_offset)

            # --- 构造返回字典 ---
            info_dict = {
                'operation_state_code': op_state,
                'current_temperature': temp,
                'error_code': err_code,
                'joint_angles': joint_angles,
                'joint_speeds': joint_speeds,
                'joint_torques': joint_torques,
                # 你可以继续在这里解析指尖、触觉等其他数据
            }
            return info_dict
            
        except struct.error as e:
            # 如果字节长度或格式不匹配，会抛出 struct.error
            print(f"【SDK内部错误】解析PDO字节流失败: {e}")
            return {}
        except Exception as e:
            print(f"【SDK内部错误】在 get_realtime_data 中发生未知错误: {e}")
            return {}

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