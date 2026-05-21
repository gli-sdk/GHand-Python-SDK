# Copyright (c) 2026 GLITech
#
# Licensed under the MIT License. See LICENSE in the project root for license information.

"""GHand SDK public API.

This package provides a high-level interface for controlling the GHand
dexterous hand via EtherCAT, CAN-FD, or RS-485.
"""

import sys

if sys.version_info < (3, 10):
    sys.exit("GHand SDK requires Python 3.10 or higher")

from . import logging_config  # auto-initialize logging handlers
from ._converter import joints_to_nparray, nparray_to_joints
from .gestures import execute_gesture, get_all_gestures
from .ghand import GHand
from .types import (
    CommType,
    CommunicationError,
    CtrlMode,
    ErrorCode,
    GestureType,
    GHandError,
    HandState,
    HandStateError,
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
    # Exceptions
    "GHandError",
    "CommunicationError",
    "HandStateError",
    # Version
    "__version__",
    # Gestures
    "GestureType",
    "execute_gesture",
    "get_all_gestures",
    # Utilities
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
