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

"""Shared ModBus register codec for CANFD and RS485.

Pure functions that convert between raw register bytes/lists and structured
data types.  This module has no bus-layer dependencies.
"""

import struct
from dataclasses import dataclass

from ..types import (
    JointId,
    ProductType,
    TactileSensorId,
    CtrlMode,
    JointControlState,
    JointState,
    State,
    JointErrorCode,
    HandState,
    JointData,
    TactileData,
)


@dataclass(frozen=True)
class ModbusRegisterProfile:
    """Product-specific Modbus register layout."""

    product_type: ProductType
    joint_input_addresses: dict[JointId, int]
    joint_control_addresses: dict[JointId, int]
    control_layout: str
    mode_register: int | None = 0x0260
    stop_register: int | None = 0x0260
    hand_info_address: int = 0x1047
    tactile_state_address: int = 0x1110
    tactile_control_address: int = 0x0020
    tactile_resultant_register_count: int = 16
    canfd_connection_timer_address: int = 0x0001
    canfd_connection_timer_registers: int = 2
    canfd_connection_timer_values: tuple[int, ...] = (0x0000, 0x0000)
    canfd_connection_delete_address: int = 0x0000
    canfd_connection_delete_registers: int = 1
    canfd_connection_delete_values: tuple[int, ...] = (0x0000,)


# Baud rate configuration register (REG_HOLD_BAUD_CONFIG).
# Writing a gear value saves to Flash and takes effect after next power-up.
BAUDRATE_CONFIG_REGISTER = 0x0004

# Common holding register addresses (device configuration / control).
REG_CONNECTION_CONTROL = 0x0000
REG_SLAVE_ID = 0x0003
REG_CLEAR_FAULT = 0x001F
REG_INIT_JOINT = 0x001E

# Common input register addresses (device info / status).
REG_DEVICE_NAME = 0x1000
REG_HARDWARE_VERSION = 0x1008
REG_FIRMWARE_VERSION = 0x1010
REG_SERIAL_NUMBER = 0x1018
REG_HAND_TYPE = 0x1020
REG_IN_FIRMWARE_PACKAGE_VER = 0x1185
REG_IN_POSITION_SENSOR_VER = 0x1186
REG_IN_TACTILE_SENSOR_VER = 0x1187
REG_IN_MOTOR_DRV_VER = 0x1188
REG_IN_THUMB_TACTILE_SENSOR_VER = 0x1189
REG_IN_FINGER_TACTILE_SENSOR_VER = 0x118A
REG_IN_SERIAL_NUMBER = 0x119A


def build_controllable_joint_addresses(
    valid_joints: list[JointId],
    joint_limits: dict[JointId, tuple[float, float]],
    base_address: int = 0x0261,
    stride: int = 6,
) -> dict[JointId, int]:
    """Build controllable joint register address mapping from config.

    Only joints in joint_limits (active joints) are assigned control register
    addresses. Addresses are allocated sequentially in the order joints appear
    in valid_joints, starting from base_address with stride between each.

    Args:
        valid_joints: All product joints (active + passive).
        joint_limits: Active joint limits dict (only active joints have min/max).
        base_address: Starting register address (default 0x0261).
        stride: Register stride between joints (default 6).

    Returns:
        Mapping from active joint ID to control register address.
    """
    controllable_map = {}
    address_offset = 0

    for joint_id in valid_joints:
        if joint_id in joint_limits:
            controllable_map[joint_id] = base_address + address_offset
            address_offset += stride

    return controllable_map


def build_modbus_profile_from_config(config) -> ModbusRegisterProfile:
    """Build ModbusRegisterProfile dynamically from ProductConfig.

    Args:
        config: ProductConfig object.

    Returns:
        Dynamically generated Modbus register profile.
    """
    joint_input_addresses = {
        joint_id: 0x1023 + joint_id.value * 5 for joint_id in config.valid_joints
    }

    joint_control_addresses = build_controllable_joint_addresses(
        valid_joints=config.valid_joints,
        joint_limits=config.joint_limits,
        base_address=0x0261,
        stride=6,
    )

    return ModbusRegisterProfile(
        product_type=config.product_type or ProductType.GHand5,
        joint_input_addresses=joint_input_addresses,
        joint_control_addresses=joint_control_addresses,
        control_layout="shared_mode_2reg",
        mode_register=0x0260,
        stop_register=0x0260,
        tactile_control_address=0x0020,
    )


def get_modbus_profile(config_or_name=None) -> ModbusRegisterProfile:
    """Return the Modbus register profile for a product type or config.

    Args:
        config_or_name: ProductConfig object or ProductType enum.

    Returns:
        Dynamically generated Modbus register profile from config file.
    """
    # If passed a ProductConfig, use it directly
    if hasattr(config_or_name, "valid_joints") and hasattr(
        config_or_name, "joint_limits"
    ):
        return build_modbus_profile_from_config(config_or_name)

    # If passed a ProductType, load config first then generate
    from ghand._config import load_product_config

    product_type = getattr(config_or_name, "product_type", config_or_name)
    if product_type is None:
        product_type = ProductType.GHand5

    config = load_product_config(product_type)
    return build_modbus_profile_from_config(config)


def get_joint_input_span(
    valid_joints: list[JointId], profile: ModbusRegisterProfile
) -> tuple[int, int]:
    """Return the smallest contiguous input-register span covering valid joints."""
    addresses = [
        profile.joint_input_addresses[joint_id]
        for joint_id in valid_joints
        if joint_id in profile.joint_input_addresses
    ]
    if not addresses:
        return 0, 0
    start = min(addresses)
    end = max(address + 4 for address in addresses)
    return start, end - start + 1


def registers_to_bytes(registers: list[int]) -> bytes:
    """Convert a list of big-endian uint16 registers to bytes."""
    return b"".join(struct.pack(">H", reg) for reg in registers)


def parse_device_name(raw_bytes: bytes) -> str:
    """Parse device name from 16 bytes (8 registers)."""
    return raw_bytes.decode("utf-8", errors="ignore").strip("\x00")


def parse_hardware_version(raw_bytes: bytes) -> str:
    """Parse hardware version from 16 bytes (8 registers)."""
    return raw_bytes.decode("utf-8", errors="ignore").strip("\x00")


def parse_firmware_version(raw_bytes: bytes) -> str:
    """Parse firmware version from 16 bytes (8 registers)."""
    return raw_bytes.decode("utf-8", errors="ignore").strip("\x00")


def parse_packed_firmware_version(raw_bytes: bytes) -> str:
    """Parse one packed firmware-version register."""
    if len(raw_bytes) < 2:
        raise ValueError("packed firmware version requires at least 2 bytes")
    version_high = raw_bytes[0]
    version_low = raw_bytes[1]
    major = (version_high >> 5) & 0x07
    minor = version_high & 0x1F
    patch = (version_low >> 4) & 0x0F
    return f"V{major}.{minor}.{patch}"


def parse_serial_number(raw_bytes: bytes) -> int:
    """Parse serial number from 16 bytes (8 registers)."""
    return int.from_bytes(raw_bytes, byteorder="big")


def parse_ascii_serial_number(raw_bytes: bytes) -> str:
    """Parse the 19-byte ASCII product serial number."""
    return raw_bytes[:19].decode("ascii", errors="ignore").strip("\x00")


def parse_hand_type(raw_bytes: bytes) -> int:
    """Parse hand type from 2 bytes (1 register).

    Returns:
        0 for unknown, 1 for left hand, 2 for right hand.
    """
    return int.from_bytes(raw_bytes, byteorder="big") & 0xFF


def parse_hand_info(raw: list[int]) -> HandState:
    """Parse 14 input registers (0x1047~0x1054) into HandState.

    Args:
        raw: raw[0] = uint16 hand state, raw[1:4] = warn bitfield,
             raw[4:10] = fault bitfield, raw[10:13] = critical bitfield,
             raw[13] = signed int16 temperature in degrees Celsius.
    """
    state = raw[0] & 0xFFFF
    error_warn = (
        _registers_to_bytes_low_high(raw[1:4]) if len(raw) >= 4 else b"\x00" * 6
    )
    error_fault = (
        _registers_to_bytes_low_high(raw[4:10]) if len(raw) >= 10 else b"\x00" * 12
    )
    error_critical = (
        _registers_to_bytes_low_high(raw[10:13])
        if len(raw) >= 13
        else b"\x00" * 6
    )
    temperature = raw[13] if len(raw) >= 14 else 0
    if temperature >= 32768:
        temperature -= 65536
    return HandState(
        state=_parse_state(state),
        error_warn=error_warn,
        error_fault=error_fault,
        error_critical=error_critical,
        temperature=temperature,
    )


def _registers_to_bytes_low_high(raw: list[int]) -> bytes:
    return bytes(byte for reg in raw for byte in (reg & 0xFF, (reg >> 8) & 0xFF))


def _parse_state(value: int) -> State:
    try:
        return State(value)
    except ValueError:
        return State.UNKNOWN_STATE


def _parse_joint_state(value: int) -> JointState:
    try:
        return JointState(value)
    except ValueError:
        return JointState.UNKNOWN_STATE


def _parse_joint_error_code(value: int) -> JointErrorCode:
    try:
        return JointErrorCode(value)
    except ValueError:
        return JointErrorCode.UNKNOWN_ERROR


def parse_joint_data(raw: list[int], offset: int, joint_id: int) -> JointData:
    """Parse 5 input registers into JointData.

    Layout:
        Register N:   [error uint8][state uint8]
        Register N+1: [reserved uint8][mode uint8]
        Register N+2: angle int16, unit 0.01 deg
        Register N+3: speed int16, unit 1%
        Register N+4: current int16, unit 1%

    Args:
        raw: List of uint16 register values.
        offset: Starting index in *raw* for this joint.
        joint_id: Numeric joint identifier.
    """
    status_byte = raw[offset] & 0xFF
    error_byte = (raw[offset] >> 8) & 0xFF
    mode = raw[offset + 1] & 0xFF
    angle_raw = raw[offset + 2]
    if angle_raw >= 32768:
        angle_raw -= 65536
    angle = angle_raw / 100.0

    speed = raw[offset + 3]
    if speed >= 32768:
        speed -= 65536

    current = raw[offset + 4]
    if current >= 32768:
        current -= 65536

    return JointData(
        id=joint_id,
        state=_parse_joint_state(status_byte),
        error=_parse_joint_error_code(error_byte),
        mode=mode,
        angle=angle,
        speed=speed,
        current=current,
    )


def parse_joints(
    raw: list[int],
    valid_joints: list[JointId],
    profile: ModbusRegisterProfile | None = None,
    start_address: int = 0x1023,
) -> list[JointData]:
    """Parse joint data for all valid joints from a contiguous register block.

    The block starts at ``start_address``.  Each product profile maps logical
    JointId values to its own register addresses.
    """
    profile = profile or get_modbus_profile(ProductType.GHand5)
    joints = []
    for joint_id in valid_joints:
        address = profile.joint_input_addresses.get(joint_id)
        if address is None:
            continue
        offset = address - start_address
        if offset + 4 >= len(raw):
            continue
        joints.append(parse_joint_data(raw, offset, joint_id.value))
    return joints


def parse_tactile_state_error(raw: list[int]) -> tuple[int, int]:
    """Parse tactile state and error from the first register (0x1110).

    Returns:
        (state_byte, error_byte)
    """
    return (raw[0] >> 8) & 0xFF, raw[0] & 0xFF


def parse_tactile_resultant(raw: list[int], region_index: int) -> list[float]:
    """Parse resultant force (Fx, Fy, Fz) for a tactile region.

    Args:
        raw: First 16 registers starting at 0x1110.
        region_index: 0=THUMB, 1=FF, 2=MF, 3=RF, 4=LF.

    Returns:
        [Fx, Fy, Fz] in Newtons (divided by 10).
    """
    base = 1 + region_index * 3
    raw_fx = (raw[base] >> 8) & 0xFF
    fx = (raw_fx - 0x100) / 10.0 if raw_fx >= 0x80 else raw_fx / 10.0

    raw_fy = (raw[base + 1] >> 8) & 0xFF
    fy = (raw_fy - 0x100) / 10.0 if raw_fy >= 0x80 else raw_fy / 10.0

    fz = ((raw[base + 2] >> 8) & 0xFF) / 10.0
    return [fx, fy, fz]


def parse_tactile_distributed(data_bytes: bytes, count: int) -> list[float]:
    """Parse distributed force data from raw bytes.

    Args:
        data_bytes: Raw bytes read from the distributed-force registers.
        count: Number of tactile points for this region.

    Returns:
        Flat list of [fx1, fy1, fz1, fx2, fy2, fz2, ...].
        Each component is an int8 (signed) or uint8 (unsigned for Fz).
    """
    distributed = []
    for i in range(0, len(data_bytes) - 2, 3):
        fx_d = data_bytes[i]
        fy_d = data_bytes[i + 1]
        fz_d = data_bytes[i + 2]
        if fx_d >= 0x80:
            fx_d -= 0x100
        if fy_d >= 0x80:
            fy_d -= 0x100
        distributed.extend([fx_d, fy_d, fz_d])
    return distributed


def encode_hand_control(mode: CtrlMode, enabled: bool) -> int:
    """Encode the shared hand mode/enable register."""
    mode_value = mode.value if isinstance(mode, CtrlMode) else int(mode)
    return ((mode_value & 0x0F) << 8) | int(enabled)


def resolve_joint_mode(joint, mode: CtrlMode, default_mode: int = 0) -> int:
    """Resolve the mode encoded in a per-joint control register."""
    joint_mode = getattr(joint, "mode", None)
    if joint_mode is None:
        joint_mode = default_mode if mode == CtrlMode.CUSTOM else mode
    mode_value = joint_mode.value if isinstance(joint_mode, CtrlMode) else int(joint_mode)
    if mode_value not in (
        CtrlMode.POSITION.value,
        CtrlMode.SPEED.value,
        CtrlMode.CURRENT.value,
        CtrlMode.MIT.value,
    ):
        raise ValueError(f"Invalid per-joint control mode: {mode_value}")
    return mode_value


def encode_joint_mode_stop(mode: int, stop: JointControlState | int) -> int:
    """Encode one joint's mode/stop register."""
    return (JointControlState(stop).value << 8) | (mode & 0x0F)


def encode_joint_command(
    joint, mode: CtrlMode, default_mode: int = CtrlMode.POSITION.value
) -> list[int]:
    """Encode a JointCommand into six holding-register values.

    Layout:
        Register N:   [stop uint8][mode uint8]
        Register N+1: angle int16, unit 0.1 deg
        Register N+2: speed int16, unit 1%
        Register N+3: current int16, unit 1%
        Register N+4: kp int16
        Register N+5: kd int16

    Returns:
        [reg0, reg1, reg2, reg3, reg4, reg5]
    """
    angle_raw = int(joint.angle * 10)
    mode_value = resolve_joint_mode(joint, mode, default_mode)
    mode_stop = encode_joint_mode_stop(mode_value, joint.stop)
    return [
        mode_stop,
        angle_raw & 0xFFFF,
        int(joint.speed) & 0xFFFF,
        int(joint.current) & 0xFFFF,
        int(getattr(joint, "kp", 0)) & 0xFFFF,
        int(getattr(joint, "kd", 0)) & 0xFFFF,
    ]


def encode_joint_command_registers(
    joint,
    mode: CtrlMode,
    profile: ModbusRegisterProfile,
) -> list[int]:
    """Encode a joint command according to the product's control layout."""
    return encode_joint_command(joint, mode)


def build_tactile_info(
    state_bit: bool,
    resultant_force: list[float],
    distributed_force: list[float] | None,
) -> TactileData:
    """Convenience wrapper to build a TactileData dataclass."""
    return TactileData(
        state=state_bit,
        resultant_force=resultant_force,
        distributed_force=distributed_force,
    )


# ============================================================================
# Self-test error registers (0x0038 ~ 0x003F, shared by RS485 and CANFD)
# ============================================================================

SELF_TEST_COMMAND_REGISTER = 0x0038
SELF_TEST_DATA_REGISTER = 0x0039
SELF_TEST_DATA_REGISTER_COUNT = 7  # 7 * 16 bits = 14 bytes (13 error + 1 result)

SELF_TEST_STATE_IDLE = 0
SELF_TEST_STATE_PROCESSING = 1
SELF_TEST_STATE_SUCCESS = 2
SELF_TEST_STATE_FAILED = 3


def encode_self_test_command_register(command: int) -> int:
    """Pack the self-test command byte into ``0x0038`` (high byte = command,
    low byte = state; the state field is read-only from the master's side)."""
    return (command & 0xFF) << 8


def parse_self_test_state(register_value: int) -> int:
    """Return the state byte contained in the low byte of ``0x0038``."""
    return register_value & 0x00FF


def parse_self_test_data_registers(
    registers: list[int],
) -> tuple[list[int], int]:
    """Decode the 7 data registers into ``(error_code[13], result)``.

    Modbus registers are big-endian: register N -> two bytes ``[hi, lo]``.
    The 14-byte payload contains the 13 error bytes followed by the result.
    """
    if len(registers) < SELF_TEST_DATA_REGISTER_COUNT:
        raise ValueError(
            f"Self-test data must have {SELF_TEST_DATA_REGISTER_COUNT} "
            f"registers, got {len(registers)}"
        )
    payload = bytearray()
    for reg in registers[:SELF_TEST_DATA_REGISTER_COUNT]:
        payload.append((reg >> 8) & 0xFF)
        payload.append(reg & 0xFF)
    error_codes = list(payload[:13])
    result = payload[13]
    return error_codes, result
