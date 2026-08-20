from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .types import CommType


class SdkError(Enum):
    OK = "ok"
    NOT_CONNECTED = "not_connected"
    INVALID_ARGUMENT = "invalid_argument"
    NOT_SUPPORTED = "not_supported"
    TIMEOUT = "timeout"
    TRANSPORT_ERROR = "transport_error"
    PROTOCOL_ERROR = "protocol_error"
    CONFIG_ERROR = "config_error"
    DEVICE_REJECTED = "device_rejected"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class OperationResult:
    code: SdkError = SdkError.OK
    message: str = ""
    comm: CommType | None = None


class GHandError(Exception):
    """Base class for GHand SDK exceptions."""


class CommunicationError(GHandError):
    """Raised when a communication operation fails unexpectedly."""


class HandStateError(GHandError):
    """Raised when device state prevents an operation."""
