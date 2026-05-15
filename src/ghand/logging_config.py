"""
GHand SDK 日志配置模块

提供符合 SDK 标准的日志配置方案：
- 默认输出 WARNING 和 ERROR 到 stderr
- 支持升级到 INFO 或 DEBUG 级别
- 支持可选的文件日志输出
- 保持简单，只支持三个固定级别
"""

import logging
import sys
from typing import Union


# ============================================================================
# Logger 命名空间
# ============================================================================

ROOT_LOGGER_NAME = "ghand"

MODULE_LOGGERS = {
    "ghand": f"{ROOT_LOGGER_NAME}.ghand",
    "ethercat_driver": f"{ROOT_LOGGER_NAME}.ethercat_driver",
}


# ============================================================================
# 日志格式
# ============================================================================

# 简洁格式（默认）
FORMAT_SIMPLE = "%(asctime)s [%(levelname)s] %(message)s"

# 详细格式（调试）
FORMAT_VERBOSE = "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"

# 开发格式（带颜色，需要 colorlog）
FORMAT_COLOR = (
    "%(log_color)s%(asctime)s%(reset)s "
    "[%(log_color)s%(levelname)s%(reset)s] "
    "[%(cyan)s%(name)s:%(lineno)d%(reset)s] "
    "%(message)s"
)

# 时间格式
DATEFMT_STANDARD = "%Y-%m-%d %H:%M:%S"
DATEFMT_ISO = "%Y-%m-%dT%H:%M:%S"

# 颜色配置
LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red,bg_white",
}


def _init_package_loggers():
    """
    包初始化时调用，创建默认的 WARNING 级别控制台 handler

    这确保了：
    1. SDK 默认输出 WARNING 和 ERROR 到 stderr
    2. 不会产生 "No handler found" 警告
    3. 用户可以通过 configure_logging() 升级到 INFO 或 DEBUG
    """
    # 防止重复初始化
    root_logger = logging.getLogger(ROOT_LOGGER_NAME)
    if hasattr(root_logger, '_ghand_initialized'):
        return

    root_logger._ghand_initialized = True

    # 创建默认的 stderr handler，WARNING 级别
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter(FORMAT_SIMPLE, DATEFMT_STANDARD))

    root_logger.addHandler(handler)
    root_logger._ghand_stderr_handler = handler

    # 模块 loggers 不需要单独的 handler，它们会继承根 logger 的配置


# ============================================================================
# 便捷配置函数
# ============================================================================


def configure_console(level: Union[int, str]) -> None:
    """
    配置控制台日志级别

    只支持 INFO 和 DEBUG 两个级别，用于降低日志级别门槛（从默认 WARNING 升级）。

    Args:
        level: 日志级别，只接受 logging.INFO 或 logging.DEBUG

    Raises:
        ValueError: 如果传入其他级别

    Example:
        >>> from ghand.logging_config import configure_console
        >>> configure_console(level=logging.INFO)  # 显示 INFO+ 的日志
        >>> configure_console(level=logging.DEBUG)  # 显示所有日志
    """
    # 验证级别
    valid_levels = {logging.INFO, logging.DEBUG}
    if level not in valid_levels:
        raise ValueError(
            f"只支持级别: INFO 或 DEBUG (收到: {logging.getLevelName(level)})"
        )

    logger = logging.getLogger(ROOT_LOGGER_NAME)

    # 获取或创建 stderr handler
    if not hasattr(logger, '_ghand_stderr_handler'):
        # 理论上不应该到这里，因为 _init_package_loggers 已经创建了
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter(FORMAT_SIMPLE, DATEFMT_STANDARD))
        logger.addHandler(handler)
        logger._ghand_stderr_handler = handler
    else:
        handler = logger._ghand_stderr_handler

    # 升级级别（如果用户请求的级别更低）
    # WARNING=30, INFO=20, DEBUG=10
    # 数字越小，级别越低（输出越多）
    if level < handler.level:
        handler.setLevel(level)

    # 同时设置 logger 级别，确保消息能到达 handler
    logger.setLevel(level)


def configure_file(filename: str, level: Union[int, str] = logging.DEBUG) -> None:
    """
    配置文件日志输出

    文件日志与控制台日志独立，可以设置不同的级别。默认使用详细格式（包含文件名和行号）。

    Args:
        filename: 日志文件路径
        level: 日志级别，默认为 DEBUG

    Example:
        >>> from ghand.logging_config import configure_file
        >>> configure_file("ghand.log", level=logging.DEBUG)
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)

    # 创建 file handler
    handler = logging.FileHandler(filename, mode="a", encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(FORMAT_VERBOSE, DATEFMT_ISO))
    logger.addHandler(handler)

    # 设置 logger 级别为所有 handler 中最低的级别
    # 这样可以确保所有 handler 都能接收到它们需要的消息
    for h in logger.handlers:
        if h.level < logger.level or logger.level == 0:
            logger.setLevel(h.level)


def get_logger(name: str = ROOT_LOGGER_NAME) -> logging.Logger:
    """
    获取指定名称的 logger

    Args:
        name: logger 名称，支持 "ghand", "ghand.ghand" 等
             也支持简写，如 "ghand" 会自动加上 "ghand." 前缀

    Returns:
        Logger 实例

    Example:
        >>> from ghand.logging_config import get_logger
        >>> logger = get_logger("ghand.ghand")
        >>> logger = get_logger("ghand")  # 等同于上
    """
    # 支持简写形式
    if not name.startswith(ROOT_LOGGER_NAME):
        name = f"{ROOT_LOGGER_NAME}.{name}"
    return logging.getLogger(name)


# 自动初始化
_init_package_loggers()
