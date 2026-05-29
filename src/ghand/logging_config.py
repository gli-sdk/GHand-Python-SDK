# Copyright (c) 2026 GLITech
#
# Licensed under the MIT License. See LICENSE in the project root for license information.

"""GHand SDK logging configuration module.

Provides SDK-standard logging setup:
- Default output of WARNING and ERROR to stderr
- Support for upgrading to INFO or DEBUG level
- Optional file log output
- Simple design with three fixed levels
"""

import logging
import sys

# ============================================================================
# Logger namespace
# ============================================================================

ROOT_LOGGER_NAME = "ghand"

MODULE_LOGGERS = {
    "ghand": f"{ROOT_LOGGER_NAME}.ghand",
    "ethercat_client": f"{ROOT_LOGGER_NAME}.ethercat_client",
}


# ============================================================================
# Log formats
# ============================================================================

FORMAT_SIMPLE = "%(asctime)s [%(levelname)s] %(message)s"
FORMAT_VERBOSE = "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
FORMAT_COLOR = (
    "%(log_color)s%(asctime)s%(reset)s "
    "[%(log_color)s%(levelname)s%(reset)s] "
    "[%(cyan)s%(name)s:%(lineno)d%(reset)s] "
    "%(message)s"
)

DATEFMT_STANDARD = "%Y-%m-%d %H:%M:%S"
DATEFMT_ISO = "%Y-%m-%dT%H:%M:%S"

LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red,bg_white",
}


def _init_package_loggers():
    """Initialize the package logger with a default WARNING-level stderr handler.

    This ensures:
    1. SDK defaults to emitting WARNING and ERROR to stderr.
    2. No "No handler found" warnings are produced.
    3. Users can upgrade verbosity via ``configure_console()``.
    """
    root_logger = logging.getLogger(ROOT_LOGGER_NAME)
    if hasattr(root_logger, "_ghand_initialized"):
        return

    root_logger._ghand_initialized = True

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter(FORMAT_SIMPLE, DATEFMT_STANDARD))

    root_logger.addHandler(handler)
    root_logger._ghand_stderr_handler = handler


# ============================================================================
# Convenience configuration functions
# ============================================================================


def configure_console(level: int | str) -> None:
    """Configure the console log level.

    Only INFO and DEBUG are supported, intended to lower the verbosity
    threshold from the default WARNING.

    Args:
        level: Log level. Only ``logging.INFO`` or ``logging.DEBUG`` are accepted.

    Raises:
        ValueError: If a level other than INFO or DEBUG is provided.

    Example:
        >>> from ghand.logging_config import configure_console
        >>> configure_console(level=logging.INFO)
    """
    valid_levels = {logging.INFO, logging.DEBUG}
    if level not in valid_levels:
        raise ValueError(
            f"Only INFO or DEBUG are supported (received: {logging.getLevelName(level)})"
        )

    logger = logging.getLogger(ROOT_LOGGER_NAME)

    if not hasattr(logger, "_ghand_stderr_handler"):
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter(FORMAT_SIMPLE, DATEFMT_STANDARD))
        logger.addHandler(handler)
        logger._ghand_stderr_handler = handler
    else:
        handler = logger._ghand_stderr_handler

    if level < handler.level:
        handler.setLevel(level)

    logger.setLevel(level)


def configure_file(filename: str, level: int | str = logging.DEBUG) -> None:
    """Configure file log output.

    File logging is independent of console logging and defaults to the verbose
    format (includes file name and line number).

    Args:
        filename: Path to the log file.
        level: Log level for the file handler. Defaults to DEBUG.

    Example:
        >>> from ghand.logging_config import configure_file
        >>> configure_file("ghand.log", level=logging.DEBUG)
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)

    handler = logging.FileHandler(filename, mode="a", encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(FORMAT_VERBOSE, DATEFMT_ISO))
    logger.addHandler(handler)

    for h in logger.handlers:
        if h.level < logger.level or logger.level == 0:
            logger.setLevel(h.level)


def get_logger(name: str = ROOT_LOGGER_NAME) -> logging.Logger:
    """Retrieve a logger by name.

    Args:
        name: Logger name, e.g. ``"ghand"`` or ``"ghand.ghand"``.
            Short names are automatically prefixed with ``"ghand."``.

    Returns:
        A ``logging.Logger`` instance.

    Example:
        >>> from ghand.logging_config import get_logger
        >>> logger = get_logger("ghand.ghand")
    """
    if not name.startswith(ROOT_LOGGER_NAME):
        name = f"{ROOT_LOGGER_NAME}.{name}"
    return logging.getLogger(name)


_init_package_loggers()
