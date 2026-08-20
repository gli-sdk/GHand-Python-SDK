from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import SdkError
from .types import CommType, ProductType


@dataclass(frozen=True)
class ConnectionDiagnostics:
    connected: bool
    comm_type: CommType
    device: str = ""


@dataclass(frozen=True)
class IdentityDiagnostics:
    product: ProductType
    hand_type: Any = None
    firmware_version: str = ""


@dataclass(frozen=True)
class TransportDiagnostics:
    tx_packets: int = 0
    rx_packets: int = 0
    tx_errors: int = 0
    rx_errors: int = 0
    timeouts: int = 0
    retries: int = 0
    reconnects: int = 0


@dataclass(frozen=True)
class SubscriptionDiagnostics:
    active_subscriptions: int = 0
    received_frames: int = 0
    dispatched_frames: int = 0
    dropped_frames: int = 0
    callback_errors: int = 0


@dataclass(frozen=True)
class ErrorDiagnostics:
    last_sdk_error: SdkError = SdkError.OK
    last_error_message: str = ""


@dataclass(frozen=True)
class Diagnostics:
    connection: ConnectionDiagnostics
    identity: IdentityDiagnostics
    transport: TransportDiagnostics = field(default_factory=TransportDiagnostics)
    subscription: SubscriptionDiagnostics = field(default_factory=SubscriptionDiagnostics)
    error: ErrorDiagnostics = field(default_factory=ErrorDiagnostics)
