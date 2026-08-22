# Copyright 2026 GLITech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Shared self-test error query workflow for register-based transports.

RS485 and CANFD both expose the object dictionary as Modbus holding registers.
The self-test error interface lives at register ``0x0038`` (command/state) and
``0x0039 ~ 0x003F`` (13-byte error array + 1-byte result), so both backends
run the same state machine over their transport-specific primitives.

The EtherCAT backend uses SDO sub-index accesses directly (see
``EthercatComm``) and does not share this workflow.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from ..types import (
    JointId,
    MotorDiagnosticError,
    ProductConfig,
    SelfTestError,
    SelfTestErrorInfo,
    VersionCheckError,
)
from .modbus_codec import (
    SELF_TEST_COMMAND_REGISTER,
    SELF_TEST_DATA_REGISTER,
    SELF_TEST_DATA_REGISTER_COUNT,
    SELF_TEST_STATE_FAILED,
    SELF_TEST_STATE_SUCCESS,
    encode_self_test_command_register,
    parse_self_test_data_registers,
    parse_self_test_state,
)

logger = logging.getLogger("ghand.self_test_workflow")

_POLL_INTERVAL_SEC = 0.01
_POLL_TIMEOUT_SEC = 1.0


# Type aliases for the transport primitives supplied by each backend.
# ``read_registers`` returns a list of 16-bit register values.
ReadRegisters = Callable[[int, int], list[int]]
WriteRegister = Callable[[int, int], None]


def read_diagnostic_error_codes(
    command: int,
    read_registers: ReadRegisters,
    write_register: WriteRegister,
) -> list[int]:
    """Run one A0~A8 read transaction over a register-based transport.

    Args:
        command: One of ``0xA0``, ``0xA1``, ..., ``0xA8``.
        read_registers: Callable that reads ``(address, count)`` holding
            registers and returns a list of uint16 values.
        write_register: Callable that writes one holding register.

    Returns:
        13-byte error code array. The caller decides which slots are
        meaningful for the specific command.

    Raises:
        TimeoutError: If the state never settles on a terminal value.
    """
    write_register(
        SELF_TEST_COMMAND_REGISTER,
        encode_self_test_command_register(command),
    )

    # State 只用于判断事务是否结束(2 或 3 都算结束);
    # Result 不判断,只读取 error_code 数据。
    _poll_state(command, read_registers)

    registers = read_registers(
        SELF_TEST_DATA_REGISTER, SELF_TEST_DATA_REGISTER_COUNT
    )
    error_codes, _ = parse_self_test_data_registers(registers)
    return error_codes


def _poll_state(command: int, read_registers: ReadRegisters) -> int:
    """Poll ``0x0038`` low byte until the state settles or timeout expires."""
    deadline = time.monotonic() + _POLL_TIMEOUT_SEC
    while True:
        register_values = read_registers(SELF_TEST_COMMAND_REGISTER, 1)
        state = parse_self_test_state(register_values[0])
        if state in (SELF_TEST_STATE_SUCCESS, SELF_TEST_STATE_FAILED):
            return state
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Self-test query 0x{command:02X} timed out (state={state})"
            )
        time.sleep(_POLL_INTERVAL_SEC)


def build_self_test_error_info(
    config: ProductConfig,
    read_registers: ReadRegisters,
    write_register: WriteRegister,
) -> SelfTestErrorInfo:
    """Execute the A0 summary + on-demand A1~A8 flow and build the result.

    Only categories flagged by the A0 summary are queried in detail. The
    13-channel motor slots are resolved back to ``JointId`` via the ordered
    subset of ``config.valid_joints`` that have joint limits (the same
    convention the SDK already uses to identify the 13 controlled motors).
    """
    info = SelfTestErrorInfo()

    summary_byte = read_diagnostic_error_codes(
        0xA0, read_registers, write_register
    )[0]
    info.summary = SelfTestError(summary_byte)
    logger.debug("Self-test summary: 0x%02X", summary_byte)

    if info.summary == SelfTestError.NONE:
        return info

    controlled_joints = [
        j for j in config.valid_joints if j in config.joint_limits
    ]

    def collect(codes: list[int]) -> list[MotorDiagnosticError]:
        entries = []
        for index, code in enumerate(codes):
            if code == 0:
                continue
            joint = (
                controlled_joints[index]
                if 0 <= index < len(controlled_joints)
                else None
            )
            entries.append(
                MotorDiagnosticError(
                    motor_index=index, joint_id=joint, error_code=code
                )
            )
        return entries

    if info.summary & SelfTestError.VERSION:
        info.version = VersionCheckError(
            read_diagnostic_error_codes(0xA1, read_registers, write_register)[0]
        )
        logger.info("Self-test error: version mismatch (0x%02X)", int(info.version))
    if info.summary & SelfTestError.POSITION_SENSOR:
        info.position_sensor = collect(
            read_diagnostic_error_codes(0xA2, read_registers, write_register)
        )
        _log_motor_errors("position sensor", info.position_sensor)
    if info.summary & SelfTestError.TACTILE_SENSOR:
        info.tactile_sensor = collect(
            read_diagnostic_error_codes(0xA3, read_registers, write_register)
        )
        _log_motor_errors("tactile sensor", info.tactile_sensor)
    if info.summary & SelfTestError.TEMPERATURE_SENSOR:
        info.temperature = read_diagnostic_error_codes(
            0xA4, read_registers, write_register
        )[0]
        logger.info("Self-test error: temperature (0x%02X)", info.temperature)
    if info.summary & SelfTestError.FAN:
        info.fan = read_diagnostic_error_codes(
            0xA5, read_registers, write_register
        )[0]
        logger.info("Self-test error: fan (0x%02X)", info.fan)
    if info.summary & SelfTestError.ZEROING:
        info.zeroing = collect(
            read_diagnostic_error_codes(0xA6, read_registers, write_register)
        )
        _log_motor_errors("zeroing", info.zeroing)
    if info.summary & SelfTestError.MOTOR:
        info.motor = collect(
            read_diagnostic_error_codes(0xA8, read_registers, write_register)
        )
        _log_motor_errors("motor check", info.motor)

    return info


def _log_motor_errors(category: str, errors: list[MotorDiagnosticError]) -> None:
    for err in errors:
        joint = err.joint_id.name if err.joint_id is not None else "unknown"
        logger.info(
            "Self-test %s error: motor=%d joint=%s code=0x%02X",
            category,
            err.motor_index,
            joint,
            err.error_code,
        )
