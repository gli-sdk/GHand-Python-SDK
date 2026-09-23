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
    HandStateMachine,
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
    hand_info_address: int = 0x1051
    tactile_state_address: int = 0x1110
    tactile_control_address: int = 0x0020
    tactile_resultant_register_count: int = 16


# Baud rate configuration register (REG_HOLD_BAUD_CONFIG).
# Writing a gear value saves to Flash and takes effect after next power-up.
BAUDRATE_CONFIG_REGISTER = 0x0004

# Common holding register addresses (device configuration / control).
REG_CONNECTION_CONTROL = 0x0000
REG_SLAVE_ID = 0x0003
REG_CLEAR_FAULT = 0x001F

# Command mailbox encoding: low byte status, high byte result.
MAILBOX_BUSY = 0x0001
MAILBOX_OK = 0x0100
MAILBOX_FAILED = 0x0200
MAILBOX_INVALID = 0x0300

# Host connection state values (REG_HOST_CONN_STATE).
CONN_STATE_CONNECTED = 0x01
CONN_STATE_ERROR = 0x03

# Common input register addresses (device info / status).
REG_SERIAL_NUMBER = 0x1000
REG_DEVICE_NAME = 0x100A
REG_HAND_TYPE = 0x1012
REG_FIRMWARE_VERSION = 0x1019
REG_IN_POSITION_SENSOR_VER = 0x101A
REG_IN_TACTILE_SENSOR_VER = 0x101B
REG_IN_MOTOR_DRV_VER = 0x101C
REG_IN_FIRMWARE_PACKAGE_VER = 0x101D
REG_CONNECTION_STATUS = 0x1026
REG_MODIFY_ID_STATUS = 0x1029
REG_MODIFY_BAUD_STATUS = 0x102A
REG_HOST_CONN_STATE = 0x1047
REG_HAND_STATE_MACHINE = 0x1048


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
        joint_id: 0x105F + joint_id.value * 5 for joint_id in config.valid_joints
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


def _to_int16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def parse_device_name(raw_bytes: bytes) -> str:
    """Parse device name from 16 bytes (8 registers)."""
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
    """Parse 14 input registers (0x1051~0x105E) into HandState.

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
        Register N+1: [stop uint8][mode uint8]
        Register N+2: angle int16, unit 0.1 deg
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
    stop = (raw[offset + 1] >> 8) & 0xFF
    angle_raw = raw[offset + 2]
    if angle_raw >= 32768:
        angle_raw -= 65536
    angle = angle_raw / 10.0

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
        stop=stop,
        angle=angle,
        speed=speed,
        current=current,
    )


def parse_joints(
    raw: list[int],
    valid_joints: list[JointId],
    profile: ModbusRegisterProfile | None = None,
    start_address: int = 0x105F,
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
    return [_to_int16(raw[base + i]) / 10.0 for i in range(3)]


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
    return (int(enabled) << 8) | (mode_value & 0x0F)


def resolve_joint_mode(joint, mode: CtrlMode, default_mode: int = 0) -> int:
    """Resolve the mode encoded in a per-joint control register."""
    joint_mode = getattr(joint, "mode", None)
    if joint_mode is None:
        joint_mode = default_mode if mode == CtrlMode.CUSTOM else mode
    mode_value = joint_mode.value if isinstance(joint_mode, CtrlMode) else int(joint_mode)
    if (mode_value & 0x0F) not in (
        CtrlMode.POSITION.value,
        CtrlMode.SPEED.value,
        CtrlMode.CURRENT.value,
        CtrlMode.MIT.value,
    ):
        raise ValueError(f"Invalid per-joint control mode: {mode_value}")
    return mode_value


def encode_joint_mode_stop(mode: int, stop: JointControlState | int) -> int:
    """Encode one joint's mode/stop register."""
    return (JointControlState(stop).value << 8) | (mode & 0xFF)


def parse_hand_state_machine(raw: list[int]) -> HandStateMachine:
    """Parse one input register containing the whole-hand state machine."""
    return HandStateMachine(raw[0] & 0xFF)


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


def encode_hand_command_frame(
    joints,
    mode: CtrlMode,
    profile: ModbusRegisterProfile,
    joint_modes: dict[JointId, int],
) -> tuple[int, list[int], dict[JointId, int]]:
    """Encode one complete, contiguous whole-hand control frame."""
    commands = {}
    updated_modes = {}
    for joint in joints:
        joint_id = JointId(joint.id)
        if joint_id not in profile.joint_control_addresses:
            continue
        registers = encode_joint_command(
            joint, mode, joint_modes.get(joint_id, CtrlMode.POSITION.value)
        )
        commands[joint_id] = registers
        updated_modes[joint_id] = registers[0] & 0x0F

    ordered_joints = sorted(
        profile.joint_control_addresses.items(), key=lambda item: item[1]
    )
    if profile.mode_register is not None:
        start_address = profile.mode_register
        registers = [encode_hand_control(mode, True)]
    elif ordered_joints:
        start_address = ordered_joints[0][1]
        registers = []
    else:
        raise ValueError("No joint control registers configured")

    for joint_id, address in ordered_joints:
        offset = address - start_address
        if offset < len(registers):
            raise ValueError("Joint control registers overlap")
        registers.extend([0] * (offset - len(registers)))
        registers.extend(
            commands.get(
                joint_id,
                [
                    encode_joint_mode_stop(
                        joint_modes.get(joint_id, CtrlMode.POSITION.value),
                        JointControlState.STOPPED,
                    ),
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
            )
        )

    return start_address, registers, updated_modes


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
