# Copyright (c) 2026 GLITech
#
# Licensed under the MIT License. See LICENSE in the project root for license information.

"""RS485 communication stub — not yet implemented."""

from typing import NoReturn

from ..types import ProductConfig
from .icomm import IComm


class Rs485Comm(IComm):
    """IComm stub implementation for RS485."""

    def __init__(self, config: ProductConfig):
        self._config = config

    def update_config(self, config: ProductConfig) -> None:
        """Update the cached product configuration."""
        self._config = config

    def _raise(self) -> NoReturn:
        raise NotImplementedError("RS485 communication not yet implemented")

    def connect(self, device_name: str) -> bool:
        self._raise()

    def disconnect(self) -> bool:
        self._raise()

    def is_connected(self) -> bool:
        self._raise()

    def search_adapters(self) -> list[str]:
        self._raise()

    def move_joints(self, joints: list, mode) -> bool:
        self._raise()

    def get_joints(self) -> list:
        self._raise()

    def stop(self) -> bool:
        self._raise()

    def get_hand_info(self):
        self._raise()

    def get_tactile_data(self) -> dict:
        self._raise()

    def open_tactile(self) -> bool:
        self._raise()

    def close_tactile(self) -> bool:
        self._raise()

    def zero_tactile(self) -> bool:
        self._raise()

    def clear_fault(self) -> bool:
        self._raise()

    def init_joint(self) -> bool:
        self._raise()

    def get_device_name(self) -> str:
        self._raise()

    def get_hardware_version(self) -> str:
        self._raise()

    def get_firmware_version(self) -> str:
        self._raise()

    def get_serial_number(self) -> int:
        self._raise()

    def get_motor_driver_version(self) -> tuple:
        self._raise()

    def get_hand_type(self) -> int:
        self._raise()

    def subscribe(self, callback, *args, **kwargs) -> int:
        self._raise()

    def unsubscribe(self, sub_id) -> bool:
        self._raise()
