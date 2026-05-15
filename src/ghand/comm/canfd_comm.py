"""CANFD 通信实现 — 桩（待开发）"""
from .icomm import IComm
from ..types import ProductConfig


class CANFDComm(IComm):
    """IComm 的 CANFD 桩实现"""

    def __init__(self, config: ProductConfig):
        self._config = config

    def connect(self, device_name: str) -> bool:
        raise NotImplementedError("CANFD communication not yet implemented")

    def disconnect(self) -> bool:
        raise NotImplementedError("CANFD communication not yet implemented")

    def is_connected(self) -> bool:
        raise NotImplementedError("CANFD communication not yet implemented")

    def search_adapters(self) -> list[str]:
        raise NotImplementedError("CANFD communication not yet implemented")

    def recv_data(self) -> bytes:
        raise NotImplementedError("CANFD communication not yet implemented")

    def send_data(self, data: bytes) -> None:
        raise NotImplementedError("CANFD communication not yet implemented")

    def sdo_read(self, index: int, subindex: int = 0) -> bytes:
        raise NotImplementedError("CANFD communication not yet implemented")

    def sdo_write(self, index: int, subindex: int, data: bytes) -> None:
        raise NotImplementedError("CANFD communication not yet implemented")

    def open_tactile(self) -> bool:
        raise NotImplementedError("CANFD communication not yet implemented")

    def close_tactile(self) -> bool:
        raise NotImplementedError("CANFD communication not yet implemented")

    def zero_tactile(self) -> bool:
        raise NotImplementedError("CANFD communication not yet implemented")

    def clear_fault(self) -> bool:
        raise NotImplementedError("CANFD communication not yet implemented")

    def init_joint(self) -> bool:
        raise NotImplementedError("CANFD communication not yet implemented")

    def get_device_info(self) -> dict:
        raise NotImplementedError("CANFD communication not yet implemented")

    def get_hand_type(self) -> int:
        raise NotImplementedError("CANFD communication not yet implemented")
