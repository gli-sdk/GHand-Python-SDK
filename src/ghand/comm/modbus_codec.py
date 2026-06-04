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

from ..types import (
    ErrorCode,
    HandState,
    JointData,
    JointId,
    State,
    TactileInfo,
    TactileSensorId,
)

# Mapping from controlled joint ID to holding-register base address.
HOLDING_REG_MAP = {
    JointId.THUMB_PIP: 0x0011,
    JointId.THUMB_MCP: 0x0013,
    JointId.THUMB_SWING: 0x0015,
    JointId.THUMB_ROTATION: 0x0017,
    JointId.FF_PIP: 0x0019,
    JointId.FF_MCP: 0x001B,
    JointId.FF_SWING: 0x001D,
    JointId.MF_PIP: 0x001F,
    JointId.MF_MCP: 0x0021,
    JointId.RF_PIP: 0x0023,
    JointId.RF_MCP: 0x0025,
    JointId.LF_PIP: 0x0027,
    JointId.LF_MCP: 0x0029,
}


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


def parse_serial_number(raw_bytes: bytes) -> int:
    """Parse serial number from 16 bytes (8 registers)."""
    return int.from_bytes(raw_bytes, byteorder="big")


def parse_hand_type(raw_bytes: bytes) -> int:
    """Parse hand type from 2 bytes (1 register).

    Returns:
        0 for unknown, 1 for left hand, 2 for right hand.
    """
    return int.from_bytes(raw_bytes, byteorder="big")


def parse_hand_info(raw: list[int]) -> HandState:
    """Parse 2 input registers (0x1021~0x1022) into HandState.

    Args:
        raw: List of uint16 register values.  raw[0] = state+error,
             raw[1] = temperature.
    """
    state_byte = (raw[0] >> 8) & 0xFF
    error_byte = raw[0] & 0xFF
    temperature = raw[1]
    return HandState(
        state=State(state_byte),
        error=ErrorCode(error_byte),
        temperature=temperature,
    )


def parse_joint_data(raw: list[int], offset: int, joint_id: int) -> JointData:
    """Parse 3 input registers into JointData.

    Layout (big-endian device bytes):
        Register N:   [state uint8][error uint8]
        Register N+1: [angle high][angle low]  -> int16, divide by 10
        Register N+2: [speed int8][torque int8]

    Args:
        raw: List of uint16 register values.
        offset: Starting index in *raw* for this joint.
        joint_id: Numeric joint identifier.
    """
    status_byte = (raw[offset] >> 8) & 0xFF
    error_byte = raw[offset] & 0xFF
    angle_raw = raw[offset + 1]
    if angle_raw >= 32768:
        angle_raw -= 65536
    angle = angle_raw / 10.0

    speed = (raw[offset + 2] >> 8) & 0xFF
    if speed >= 128:
        speed -= 256

    torque = raw[offset + 2] & 0xFF
    if torque >= 128:
        torque -= 256

    return JointData(
        id=joint_id,
        state=State(status_byte),
        error=ErrorCode(error_byte),
        angle=angle,
        speed=speed,
        torque=torque,
    )


def parse_joints(raw: list[int], valid_joints: list[JointId]) -> list[JointData]:
    """Parse joint data for all valid joints from a contiguous register block.

    The block is assumed to start at register 0x1023 and contain
    (max_joint_id + 1) * 3 registers.
    """
    joints = []
    for joint_id in valid_joints:
        offset = joint_id.value * 3
        if offset + 2 >= len(raw):
            continue
        joints.append(parse_joint_data(raw, offset, joint_id.value))
    return joints


def parse_tactile_state_error(raw: list[int]) -> tuple[int, int]:
    """Parse tactile state and error from the first register (0x1080).

    Returns:
        (state_byte, error_byte)
    """
    return (raw[0] >> 8) & 0xFF, raw[0] & 0xFF


def parse_tactile_resultant(raw: list[int], region_index: int) -> list[float]:
    """Parse resultant force (Fx, Fy, Fz) for a tactile region.

    Args:
        raw: First 16 registers starting at 0x1080.
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


def encode_joint_command(joint) -> tuple[int, int]:
    """Encode a JointCommand into two holding-register values.

    Layout:
        Register N:   uint16(angle * 10)
        Register N+1: [speed int8][torque int8]

    Returns:
        (reg0, reg1)
    """
    angle_raw = int(joint.angle * 10)
    reg0 = angle_raw & 0xFFFF
    reg1 = ((joint.speed & 0xFF) << 8) | (joint.torque & 0xFF)
    return reg0, reg1


def build_tactile_info(
    state_bit: bool,
    resultant_force: list[float],
    distributed_force: list[float] | None,
) -> TactileInfo:
    """Convenience wrapper to build a TactileInfo dataclass."""
    return TactileInfo(
        state=state_bit,
        resultant_force=resultant_force,
        distributed_force=distributed_force,
    )
