"""
xiaoyao-SDK 日志配置模块

提供符合 SDK 标准的日志配置方案：
- 默认静默（NullHandler）
- 便捷配置函数
- 完全用户可控
"""

import logging
import sys
from typing import Optional, Union


# ============================================================================
# Logger 命名空间
# ============================================================================

ROOT_LOGGER_NAME = "xiaoyao"

MODULE_LOGGERS = {
    "dexhand": f"{ROOT_LOGGER_NAME}.dexhand",
    "ecatclient": f"{ROOT_LOGGER_NAME}.ecatclient",
    "error": f"{ROOT_LOGGER_NAME}.error",
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
    包初始化时调用，为所有 logger 添加 NullHandler

    这确保了：
    1. SDK 默认静默（不输出日志）
    2. 不会产生 "No handler found" 警告
    3. 用户可以完全控制日志行为
    """
    # 根 logger
    root_logger = logging.getLogger(ROOT_LOGGER_NAME)
    if not root_logger.handlers:
        root_logger.addHandler(logging.NullHandler())

    # 模块 loggers
    for module_name, logger_name in MODULE_LOGGERS.items():
        module_logger = logging.getLogger(logger_name)
        if not module_logger.handlers:
            module_logger.addHandler(logging.NullHandler())


# ============================================================================
# 便捷配置函数
# ============================================================================


def configure_console(
    level: Union[int, str] = logging.INFO,
    format_string: str = FORMAT_SIMPLE,
    datefmt: str = DATEFMT_STANDARD,
    use_color: bool = False,
) -> logging.Logger:
    """
    配置控制台日志输出

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        format_string: 日志格式字符串
        datefmt: 时间格式
        use_color: 是否使用彩色输出（需要 colorlog）

    Returns:
        配置好的根 logger

    Example:
        >>> from xiaoyao.logging_config import configure_console
        >>> configure_console(level=logging.DEBUG)
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(level)

    # 移除已存在的 handlers（避免重复）
    logger.handlers.clear()

    # 创建 handler
    if use_color:
        try:
            import colorlog
            handler = colorlog.StreamHandler(sys.stdout)
            formatter = colorlog.ColoredFormatter(
                format_string,
                datefmt=datefmt,
                log_colors=LOG_COLORS,
            )
        except ImportError:
            # 降级到普通格式
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(format_string, datefmt=datefmt)
    else:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(format_string, datefmt=datefmt)

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def configure_file(
    filename: str,
    level: Union[int, str] = logging.DEBUG,
    format_string: str = FORMAT_VERBOSE,
    datefmt: str = DATEFMT_ISO,
    mode: str = "a",
    encoding: str = "utf-8",
) -> logging.Logger:
    """
    配置文件日志输出

    Args:
        filename: 日志文件路径
        level: 日志级别
        format_string: 日志格式字符串
        datefmt: 时间格式
        mode: 文件打开模式 ('a' 追加, 'w' 覆盖)
        encoding: 文件编码

    Returns:
        配置好的根 logger

    Example:
        >>> from xiaoyao.logging_config import configure_file
        >>> configure_file("xiaoyao.log", level=logging.DEBUG)
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(level)

    # 创建 file handler
    handler = logging.FileHandler(filename, mode=mode, encoding=encoding)
    formatter = logging.Formatter(format_string, datefmt=datefmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def configure_both(
    level_console: Union[int, str] = logging.INFO,
    level_file: Union[int, str] = logging.DEBUG,
    filename: str = "xiaoyao.log",
    use_color: bool = False,
) -> logging.Logger:
    """
    同时配置控制台和文件日志

    Args:
        level_console: 控制台日志级别
        level_file: 文件日志级别
        filename: 日志文件路径
        use_color: 控制台是否使用彩色

    Returns:
        配置好的根 logger

    Example:
        >>> from xiaoyao.logging_config import configure_both
        >>> configure_both(level_console=logging.INFO, filename="debug.log")
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(min(level_console, level_file))

    # 清除现有 handlers
    logger.handlers.clear()

    # 控制台 handler
    if use_color:
        try:
            import colorlog
            console_handler = colorlog.StreamHandler(sys.stdout)
            console_handler.setFormatter(
                colorlog.ColoredFormatter(
                    FORMAT_SIMPLE,
                    datefmt=DATEFMT_STANDARD,
                    log_colors=LOG_COLORS,
                )
            )
        except ImportError:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(
                logging.Formatter(FORMAT_SIMPLE, DATEFMT_STANDARD)
            )
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter(FORMAT_SIMPLE, DATEFMT_STANDARD)
        )

    console_handler.setLevel(level_console)
    logger.addHandler(console_handler)

    # 文件 handler
    file_handler = logging.FileHandler(filename, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter(FORMAT_VERBOSE, DATEFMT_ISO)
    )
    file_handler.setLevel(level_file)
    logger.addHandler(file_handler)

    return logger


def disable_logging() -> None:
    """
    禁用 xiaoyao-SDK 的所有日志输出

    Example:
        >>> from xiaoyao.logging_config import disable_logging
        >>> disable_logging()
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(logging.CRITICAL + 1)
    logger.propagate = False


def get_logger(name: str = ROOT_LOGGER_NAME) -> logging.Logger:
    """
    获取指定名称的 logger

    Args:
        name: logger 名称，支持 "xiaoyao", "xiaoyao.dexhand" 等
             也支持简写，如 "dexhand" 会自动加上 "xiaoyao." 前缀

    Returns:
        Logger 实例

    Example:
        >>> from xiaoyao.logging_config import get_logger
        >>> logger = get_logger("xiaoyao.dexhand")
        >>> logger = get_logger("dexhand")  # 等同于上
    """
    # 支持简写形式
    if not name.startswith(ROOT_LOGGER_NAME):
        name = f"{ROOT_LOGGER_NAME}.{name}"
    return logging.getLogger(name)


# 自动初始化
_init_package_loggers()
