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

"""GHand SDK public API.

This package provides a high-level interface for controlling the GHand
dexterous hand via EtherCAT, CAN-FD, or RS-485.
"""

import sys

if sys.version_info < (3, 10):
    sys.exit("GHand SDK requires Python 3.10 or higher")

from . import logging_config  # auto-initialize logging handlers
from ._converter import JointConverter, joints_to_nparray, nparray_to_joints
from .gestures import execute_gesture, get_all_gestures
from .ghand import GHand
from .types import (
    CommType,
    CtrlMode,
    DeviceData,
    ErrorCode,
    GestureType,
    HandState,
    HandType,
    JointCommand,
    JointData,
    JointId,
    ProductType,
    State,
    TactileInfo,
    TactileSensorId,
)
from .version import __version__

__all__ = [
    # Core classes
    "GHand",
    "DeviceData",
    "JointCommand",
    "JointData",
    "JointId",
    "ProductType",
    "HandState",
    "HandType",
    "TactileSensorId",
    "TactileInfo",
    "CommType",
    "CtrlMode",
    # Enums
    "State",
    "ErrorCode",
    # Version
    "__version__",
    # Gestures
    "GestureType",
    "execute_gesture",
    "get_all_gestures",
    # Utilities
    "JointConverter",
    "joints_to_nparray",
    "nparray_to_joints",
    # Logging helpers
    "configure_logging",
    "configure_logging_console",
    "configure_logging_file",
    "get_logger",
]

# Convenience aliases
configure_logging = logging_config.configure_console
configure_logging_console = logging_config.configure_console
configure_logging_file = logging_config.configure_file
get_logger = logging_config.get_logger

_logger = logging_config.get_logger()
_logger.debug("GHand SDK v%s loaded", __version__)
