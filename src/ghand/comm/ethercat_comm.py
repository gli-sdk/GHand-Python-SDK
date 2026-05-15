"""EtherCAT 通信实现 — 封装现有 EthercatClient"""
import logging

from .icomm import IComm
from .ethercat_driver import EthercatClient
from ..types import ProductConfig

logger = logging.getLogger("ghand.ethercat_comm")


class EtherCATComm(IComm):
    """IComm 的 EtherCAT 实现，适配现有 EthercatClient"""

    def __init__(self, config: ProductConfig):
        self._client = EthercatClient()
        self._config = config

    # ===== 连接管理 =====

    def search_adapters(self) -> list[str]:
        return self._client.search()

    def connect(self, device_name: str) -> bool:
        connected = self._client.connect(device_name)
        if not connected:
            return False
        if not self._client.run():
            self._client.disconnect()
            return False
        logger.info("Device connected via EtherCAT (%s)", device_name)
        return True

    def disconnect(self) -> bool:
        self._client.disconnect()
        logger.info("Device disconnected")
        return True

    def is_connected(self) -> bool:
        return self._client._connected

    # ===== 数据收发 =====

    def recv_data(self) -> bytes:
        return self._client.recv_data()

    def send_data(self, data: bytes) -> None:
        self._client.send_data(data)

    # ===== SDO 读写 =====

    def sdo_read(self, index: int, subindex: int = 0) -> bytes:
        return self._client.sdo_read(index, subindex)

    def sdo_write(self, index: int, subindex: int, data: bytes) -> None:
        self._client.sdo_write(index, subindex, data)

    # ===== 触觉传感器 =====

    def open_tactile(self) -> bool:
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x01')
            result = self._client.sdo_read(0x2004, 0x03)
            return result == b'\x00'
        except Exception:
            return False

    def close_tactile(self) -> bool:
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x02')
            result = self._client.sdo_read(0x2004, 0x03)
            return result == b'\x00'
        except Exception:
            return False

    def zero_tactile(self) -> bool:
        try:
            self._client.sdo_write(0x2004, 0x01, b'\x04')
            result = self._client.sdo_read(0x2004, 0x03)
            return result == b'\x00'
        except Exception:
            return False

    # ===== 设备操作 =====

    def clear_fault(self) -> bool:
        try:
            self._client.sdo_write(0x2002, 0x01, b'\x01')
            logger.info("Fault cleared")
            return True
        except Exception:
            return False

    def init_joint(self) -> bool:
        try:
            self._client.sdo_write(0x2003, 0x01, b'\x01')
            logger.info("Joint initialization completed")
            return True
        except Exception:
            return False

    def get_device_info(self) -> dict:
        info = {}
        try:
            info["device_name"] = self._client.sdo_read(0x1008, 0x00).decode("utf-8")
        except Exception:
            info["device_name"] = ""
        try:
            info["hardware_version"] = self._client.sdo_read(0x1009, 0x00).decode("utf-8")
        except Exception:
            info["hardware_version"] = ""
        try:
            info["firmware_version"] = self._client.sdo_read(0x100A, 0x00).decode("utf-8")
        except Exception:
            info["firmware_version"] = ""
        try:
            info["serial_number"] = int.from_bytes(
                self._client.sdo_read(0x1018, 0x04), byteorder="little"
            )
        except Exception:
            info["serial_number"] = 0
        try:
            main = int.from_bytes(self._client.sdo_read(0x2007, 0x01), byteorder="little")
            sub1 = int.from_bytes(self._client.sdo_read(0x2007, 0x02), byteorder="little")
            sub2 = int.from_bytes(self._client.sdo_read(0x2007, 0x03), byteorder="little")
            info["motor_driver_version"] = (main, sub1, sub2)
        except Exception:
            info["motor_driver_version"] = (0, 0, 0)
        return info

    def get_hand_type(self) -> int:
        try:
            return int.from_bytes(
                self._client.sdo_read(0x2001, 0x00), byteorder="little"
            )
        except Exception:
            return 0
