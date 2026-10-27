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

import struct
from dataclasses import dataclass, field

from .._product_config import ProductConfig
from .._device_value import format_device_value, parse_device_value
from ..types import JointErrorCode, JointId, JointState, HandControlState

# TPDO component byte sizes
_HAND_TPDO_SIZE = struct.calcsize('<H6s12s6sh')  # 28
_JOINT_TPDO_SIZE = struct.calcsize('<BBBBhhh')  # 10
_TACTILE_STATE_SIZE = 2  # BB
_TACTILE_RESULTANT_SIZE = 6  # resultant xyz (int16[3], low byte valid)
_TACTILE_SAMPLE_PER_GROUP = 3  # xyz per sample group

def compute_tpdo_size(joint_count: int, tactile_region_counts: list[int] | None = None) -> int:
    """Calculate the total TPDO byte size based on joint count and tactile sample groups.

    Args:
        joint_count: Total number of joints.
        tactile_region_counts: List of tactile region sample-group counts.
            If omitted, tactile data is excluded from the calculation.

    Returns:
        Expected TPDO size in bytes.
    """
    total = _HAND_TPDO_SIZE + joint_count * _JOINT_TPDO_SIZE
    if tactile_region_counts:
        total += _TACTILE_STATE_SIZE
        for count in tactile_region_counts:
            total += _TACTILE_RESULTANT_SIZE + count * _TACTILE_SAMPLE_PER_GROUP
    return total


@dataclass
class HandTpdo:
    """Hand-level status fields within a TPDO frame."""

    state: int
    error_warn: bytes
    error_fault: bytes
    error_critical: bytes
    temperature: int

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = struct.calcsize('<H6s12s6sh')
        if len(data) < expected_size:
            return cls(0, b"\x00" * 6, b"\x00" * 12, b"\x00" * 6, 0)
        state, error_warn, error_fault, error_critical, temperature = (
            struct.unpack_from('<H6s12s6sh', data, 0)
        )
        return cls(state, error_warn, error_fault, error_critical, temperature)

    def __str__(self):
        return (
            f"HandTpdo(state={format_device_value(parse_device_value(HandControlState, self.state))}, error_warn={self.error_warn!r}, "
            f"error_fault={self.error_fault!r}, error_critical={self.error_critical!r}, "
            f"temperature={self.temperature})"
        )


@dataclass
class JointTpdo:
    """Joint-level status fields within a TPDO frame."""

    state: int
    error: int
    mode: int
    stop: int
    angle: float
    speed: int
    current: int

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = struct.calcsize('<BBBBhhh')
        if len(data) < expected_size:
            return cls(0, 0, 0, 0, 0.0, 0, 0)
        state, error, mode, stop, angle_raw, speed, current = struct.unpack_from(
            '<BBBBhhh', data, 0
        )
        angle = angle_raw * 0.1
        return cls(state, error, mode, stop, angle, speed, current)

    def __str__(self):
        return (
            f"JointTpdo(state={format_device_value(parse_device_value(JointState, self.state))}, "
            f"error={format_device_value(parse_device_value(JointErrorCode, self.error))}, "
            f"mode={self.mode}, stop={self.stop}, angle={self.angle:.3f}, "
            f"speed={self.speed}, current={self.current})"
        )


@dataclass
class TactileSensorState:
    """Tactile sensor state flags."""

    state: int = 0  # uint8 status code
    error: int = 0  # uint8 error code

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = 2  # 1 byte state + 1 byte error
        if len(data) < expected_size:
            return cls()
        state, error = struct.unpack_from('<BB', data, 0)
        return cls(state=state, error=error)


@dataclass
class TactileData:
    """Tactile data for a single finger region."""

    count: int = 0
    resultant_force: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    sample_force: list[float] = field(default_factory=list)

    @classmethod
    def from_bytes(cls, data: bytes, count: int):
        """Parse tactile data from raw bytes.

        Args:
            data: Raw byte sequence.
            count: Number of sample groups.

        Returns:
            Populated TactileData instance.
        """
        expected_size = 6 + count * 3
        if len(data) < expected_size:
            return cls(count=count)

        rf_x = struct.unpack_from('<h', data, 0)[0] / 10.0
        rf_y = struct.unpack_from('<h', data, 2)[0] / 10.0
        rf_z = struct.unpack_from('<h', data, 4)[0] / 10.0
        resultant_force = [rf_x, rf_y, rf_z]

        sample_force = []
        for i in range(count):
            offset = 6 + i * 3
            x, y, z = struct.unpack_from('<bbB', data, offset)
            sample_force.extend([x / 10.0, y / 10.0, z / 10.0])

        return cls(count=count, resultant_force=resultant_force, sample_force=sample_force)


class Tpdo:
    """Full TPDO (Transmit Process Data Object) frame."""

    def __init__(self, config: ProductConfig):
        self.hand = HandTpdo(0, b"\x00" * 6, b"\x00" * 12, b"\x00" * 6, 0)
        self.joints: dict[JointId, JointTpdo] = {}
        self.tactile_state = TactileSensorState()

        for jid in config.valid_joints:
            joint = JointTpdo(0, 0, 0, 0, 0.0, 0, 0)
            self.joints[jid] = joint
            setattr(self, jid.name.lower(), joint)

        if config.has_tactile:
            for region in config.tactile_regions:
                setattr(self, f"{region.id.name.lower()}_tactile", TactileData(count=region.count))

    @classmethod
    def from_bytes(cls, data: bytes, config: ProductConfig):
        """Parse a TPDO frame from raw bytes using the given product config.

        Args:
            data: Raw byte sequence.
            config: Product configuration defining joint and tactile layout.

        Returns:
            Populated Tpdo instance.
        """
        expected_size = compute_tpdo_size(
            len(config.valid_joints),
            [r.count for r in config.tactile_regions] if config.has_tactile else None,
        )
        instance = cls(config)
        if len(data) < expected_size:
            return instance

        offset = 0
        instance.hand = HandTpdo.from_bytes(data[offset:offset + _HAND_TPDO_SIZE])
        offset += _HAND_TPDO_SIZE

        for jid in config.valid_joints:
            joint = JointTpdo.from_bytes(data[offset:offset + _JOINT_TPDO_SIZE])
            instance.joints[jid] = joint
            setattr(instance, jid.name.lower(), joint)
            offset += _JOINT_TPDO_SIZE

        if not config.has_tactile:
            return instance

        instance.tactile_state = TactileSensorState.from_bytes(
            data[offset:offset + _TACTILE_STATE_SIZE]
        )
        offset += _TACTILE_STATE_SIZE

        for region in config.tactile_regions:
            size = _TACTILE_RESULTANT_SIZE + region.count * _TACTILE_SAMPLE_PER_GROUP
            attr = f"{region.id.name.lower()}_tactile"
            setattr(
                instance,
                attr,
                TactileData.from_bytes(data[offset:offset + size], region.count),
            )
            offset += size

        return instance


@dataclass
class JointRpdo:
    """Per-joint control fields within an RPDO frame."""

    mode: int = 0
    stop: int = 0
    angle: float = 0.0
    speed: int = 0
    current: int = 0
    kp: int = 0
    kd: int = 0


class Rpdo:
    """Full RPDO (Receive Process Data Object) frame.

    Joint data is stored in a dictionary keyed by JointId,
    so the frame only contains joints declared by the product config.
    """

    def __init__(self, controlled_joints: list[JointId]):
        self.mode: int = 0
        self.stop: int = 0
        self.joints: dict[JointId, JointRpdo] = {
            jid: JointRpdo() for jid in controlled_joints
        }

    def to_bytes(self) -> bytes:
        """Pack the RPDO into bytes according to the configured joint order.

        Returns:
            Packed byte sequence.
        """
        data = bytearray()
        data.extend(struct.pack('<B', self.mode))
        data.extend(struct.pack('<B', self.stop))
        for joint in self.joints.values():
            data.extend(
                struct.pack(
                    '<BBhhhhh',
                    joint.mode,
                    joint.stop,
                    int(joint.angle * 10),
                    joint.speed,
                    joint.current,
                    joint.kp,
                    joint.kd,
                )
            )
        return bytes(data)
