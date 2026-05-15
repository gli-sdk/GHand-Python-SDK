"""通信协议抽象接口 — 与 C++ SDK 的 IComm 对齐"""
from abc import ABC, abstractmethod


class IComm(ABC):
    """通信抽象接口，为 EtherCAT/CANFD/RS485 提供统一的业务级通信 API"""

    # ===== 连接管理 =====

    @abstractmethod
    def connect(self, device_name: str) -> bool:
        """连接到指定设备，返回是否成功"""
        ...

    @abstractmethod
    def disconnect(self) -> bool:
        """断开连接"""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """是否已连接"""
        ...

    @abstractmethod
    def search_adapters(self) -> list[str]:
        """搜索可用适配器，返回适配器 ID 列表"""
        ...

    # ===== 数据收发 =====

    @abstractmethod
    def recv_data(self) -> bytes:
        """
        接收设备数据

        Raises:
            RuntimeError: 设备未连接或通信失败
        """
        ...

    @abstractmethod
    def send_data(self, data: bytes) -> None:
        """
        发送数据到设备

        Raises:
            RuntimeError: 设备未连接或通信失败
        """
        ...

    # ===== SDO 读写 =====

    @abstractmethod
    def sdo_read(self, index: int, subindex: int = 0) -> bytes:
        """
        读取 SDO 对象字典

        Raises:
            RuntimeError: 设备未连接
        """
        ...

    @abstractmethod
    def sdo_write(self, index: int, subindex: int, data: bytes) -> None:
        """
        写入 SDO 对象字典

        Raises:
            RuntimeError: 设备未连接
        """
        ...

    # ===== 触觉传感器 =====

    @abstractmethod
    def open_tactile(self) -> bool:
        """打开触觉传感器"""
        ...

    @abstractmethod
    def close_tactile(self) -> bool:
        """关闭触觉传感器"""
        ...

    @abstractmethod
    def zero_tactile(self) -> bool:
        """调零触觉传感器"""
        ...

    # ===== 设备操作 =====

    @abstractmethod
    def clear_fault(self) -> bool:
        """清除故障"""
        ...

    @abstractmethod
    def init_joint(self) -> bool:
        """初始化关节位置"""
        ...

    @abstractmethod
    def get_device_info(self) -> dict:
        """获取设备信息 (name, hardware_ver, software_ver, serial_number)"""
        ...

    @abstractmethod
    def get_hand_type(self) -> int:
        """获取手部类型 (0=未知, 1=左手, 2=右手)"""
        ...
