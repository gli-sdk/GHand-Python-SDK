# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

# Copyright 2026 GLITech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Base enums for product, protocol, joint, and sensor identity."""

import enum


def unknown_member(cls, fallback, value):
    """Create a fallback enum member while preserving the raw device value."""
    if type(value) is not int:
        return None
    pseudo = int.__new__(cls, value)
    pseudo._name_ = fallback.name
    pseudo._value_ = value
    return pseudo


_NUMERIC_FORMAT_TYPES = "bcdeEfFgGnoxX%"


class DeviceCode(enum.IntEnum):
    """Integer device code with diagnosable unknown-value formatting."""

    def __str__(self):
        return f"{self.name}({self.value})"

    def __format__(self, format_spec):
        if format_spec and format_spec[-1] in _NUMERIC_FORMAT_TYPES:
            return int.__format__(self, format_spec)
        return str.__format__(str(self), format_spec)


class JointId(enum.IntEnum):
    THUMB_IP = 0
    THUMB_MCP = 1
    THUMB_TMC_FE = 2
    THUMB_TMC_AA = 3
    THUMB_TMC_PS = 4
    FF_DIP = 5
    FF_PIP = 6
    FF_MCP = 7
    FF_MCP_AA = 8
    MF_DIP = 9
    MF_PIP = 10
    MF_MCP = 11
    RF_DIP = 12
    RF_PIP = 13
    RF_MCP = 14
    LF_DIP = 15
    LF_PIP = 16
    LF_MCP = 17


class RS485BaudRate(enum.IntEnum):
    """Predefined RS485 baud rates mapped to GHand protocol gear values."""

    BAUD_57600 = 0x00
    BAUD_115200 = 0x01
    BAUD_230400 = 0x02
    BAUD_460800 = 0x03
    BAUD_921600 = 0x04
    BAUD_1000000 = 0x05


class CANFDBitTiming(enum.IntEnum):
    """Predefined CAN FD bit timing profiles.

    Names use ``TIMING_<arbitration bitrate>_<data bitrate>``. Each value maps
    directly to the protocol gear stored by the GHand device.
    """

    # Arbitration: 500 Kbps @ 80%; data: 1 Mbps @ 75%.
    TIMING_500K_1M = 0x00
    # Arbitration: 500 Kbps @ 80%; data: 2 Mbps @ 80%.
    TIMING_500K_2M = 0x01
    # Arbitration: 500 Kbps @ 80%; data: 4 Mbps @ 80%.
    TIMING_500K_4M = 0x02
    # Arbitration: 500 Kbps @ 80%; data: 5 Mbps @ 75%.
    TIMING_500K_5M = 0x03
    # Arbitration: 1 Mbps @ 75%; data: 4 Mbps @ 80%.
    TIMING_1M_4M = 0x04
    # Arbitration: 1 Mbps @ 75%; data: 5 Mbps @ 75%.
    TIMING_1M_5M = 0x05


class CommType(enum.Enum):
    UNKNOWN = "unknown"
    ETHERCAT = "ethercat"
    CANFD = "canfd"
    RS485 = "rs485"


class TactileSensorId(enum.IntEnum):
    THUMB = 0
    FF = 1
    MF = 2
    RF = 3
    LF = 4


class ProductType(enum.Enum):
    GHand5 = "GHand5"
    GHandLite1 = "GHandLite1"


class GestureType(enum.Enum):
    OPEN_HAND = "open_hand"
    FIST = "fist"
    OK = "ok"
    THUMBS_UP = "thumbs_up"
    SIX_SIGN = "six_sign"
