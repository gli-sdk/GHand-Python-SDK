import sys
if sys.version_info < (3, 10):
    sys.exit("GHand SDK requires Python 3.10 or higher")

from .ghand import GHand
from .types import (
    Joint, JointId, HandInfo, HandType, CommType, CtrlMode,
    TactileSensorId, TactileInfo, State, ErrorCode, ProductType, GestureType,
    GHandError, DeviceDisconnectedError, DeviceFaultError,
    JointFaultError, DataReceiveError,
)
from .version import __version__
from .gestures import execute_gesture, get_all_gestures
from ._converter import joints_to_nparray, nparray_to_joints

# ==============================================================================
# 日志初始化：符合 SDK 标准
# ==============================================================================

# 导入日志配置模块（会自动初始化 NullHandler）
from . import logging_config

# 导出便捷函数
__all__ = [
    # 核心类
    "GHand",
    "Joint",
    "JointId",
    "ProductType",
    "HandInfo",
    "HandType",
    "TactileSensorId",
    "TactileInfo",
    "CommType",
    "CtrlMode",
    # 枚举
    "State",
    "ErrorCode",
    # 异常类
    "GHandError",
    "DeviceDisconnectedError",
    "DeviceFaultError",
    "JointFaultError",
    "DataReceiveError",
    # 版本
    "__version__",
    # 手势相关
    "GestureType",
    "execute_gesture",
    "get_all_gestures",
    # 工具函数
    "joints_to_nparray",
    "nparray_to_joints",
    # 日志配置函数
    "configure_logging",
    "configure_logging_console",
    "configure_logging_file",
    "get_logger",
]

# 便捷别名（更友好的命名）
configure_logging = logging_config.configure_console
configure_logging_console = logging_config.configure_console
configure_logging_file = logging_config.configure_file
get_logger = logging_config.get_logger

# SDK 加载日志（仅在启用日志时显示）
_logger = logging_config.get_logger()
_logger.debug("GHand SDK v%s loaded", __version__)
