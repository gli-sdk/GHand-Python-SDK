# src/xiaoyao/_internal/ethercat_client.py (清理并修正后的最终版)

import pysoem
import struct
import sys

# ====================================================================
#  直接使用协议定义的数字状态码，不再依赖pysoem的常量
# ====================================================================
STATE_INIT = 1
STATE_PRE_OP = 2
STATE_SAFE_OP = 4
STATE_OP = 8
# ====================================================================

# ====================================================================
#  对象字典索引 (根据《枭尧灵巧手 EtherCAT 通信协议》V1.1 更新)
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
# ====================================================================

class EtherCATClient:
    """
    一个管理 pysoem 连接的单例客户端。
    本版本使用经过调试验证的、与您本地环境兼容的API。
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if EtherCATClient._instance is not None:
            raise Exception("这是一个单例类，请使用 get_instance() 获取实例")
        
        self.master = pysoem.Master()
        self.is_initialized = False
        self._slave = None
        
    def find_adapters(self):
        return pysoem.find_adapters()

    def connect(self, adapter_name: str, goto_op_state: bool = False):
        if self.is_initialized:
            return True
        try:
            self.master.open(adapter_name)
            if not self.master.config_init() > 0:
                raise ConnectionError("网络中未找到任何EtherCAT从站设备。")
            
            self._slave = self.master.slaves[0]
            print(f"成功发现设备: {self._slave.name}")

            self._slave.state = STATE_PRE_OP
            self.master.write_state()
            self.master.state_check(0, STATE_PRE_OP)

            if self.master.read_state() != STATE_PRE_OP:
                raise ConnectionError("无法将从站切换到 PRE-OP 状态。")
            
            print("设备已进入 PRE-OP 状态。")
            # 我们知道 config_map 会导致问题，所以在这里先不调用它
            
            self.is_initialized = True
            return True
        except OSError as e:
            raise ConnectionError(f"连接失败: {e}")
        except Exception as e:
            self.master.close()
            raise ConnectionError(f"连接过程中发生未知错误: {e}")

    def disconnect(self):
        if self.is_initialized:
            try:
                self._slave.state = STATE_INIT
                self.master.write_state()
            except Exception: pass
            self.master.close()
        
        self.is_initialized = False
        EtherCATClient._instance = None

    def sdo_read(self, index, subindex=0):
        if not self.is_initialized: raise ConnectionError("设备未连接。")
        try:
            return self._slave.sdo_read(index, subindex)
        except Exception as e:
            print(f"错误: SDO读取失败 (Index: {index:04X}): {e}")
            return None

    def sdo_write(self, index, subindex, data_bytes):
        if not self.is_initialized: raise ConnectionError("设备未连接。")
        self._slave.sdo_write(index, subindex, data_bytes)

    def is_op_state(self) -> bool:
        if not self.is_initialized: return False
        return self.master.read_state() == STATE_OP

    # ... 其他 PDO 相关函数 ...
    def send_processdata(self):
        if not self.is_initialized: return
        self.master.send_processdata()

    def receive_processdata(self, timeout_us=2000) -> bytes:
        if not self.is_initialized: return b''
        self.master.receive_processdata(timeout_us)
        return self._slave.input
    
    def set_output(self, data: bytes):
        if not self.is_initialized: return
        self._slave.output = data