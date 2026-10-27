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

"""Product, communication, control, and feedback state enums."""

import enum


class JointId(enum.IntEnum):
    THUMB_IP = 0  # Thumb interphalangeal joint.
    THUMB_MCP = 1  # Thumb metacarpophalangeal joint.
    THUMB_TMC_FE = 2  # Thumb trapeziometacarpal flexion and extension.
    THUMB_TMC_AA = 3  # Thumb trapeziometacarpal abduction and adduction.
    THUMB_TMC_PS = 4  # Thumb trapeziometacarpal pronation and supination.
    FF_DIP = 5  # Index finger distal interphalangeal joint.
    FF_PIP = 6  # Index finger proximal interphalangeal joint.
    FF_MCP = 7  # Index finger metacarpophalangeal flexion and extension.
    FF_MCP_AA = 8  # Index finger metacarpophalangeal abduction and adduction.
    MF_DIP = 9  # Middle finger distal interphalangeal joint.
    MF_PIP = 10  # Middle finger proximal interphalangeal joint.
    MF_MCP = 11  # Middle finger metacarpophalangeal joint.
    RF_DIP = 12  # Ring finger distal interphalangeal joint.
    RF_PIP = 13  # Ring finger proximal interphalangeal joint.
    RF_MCP = 14  # Ring finger metacarpophalangeal joint.
    LF_DIP = 15  # Little finger distal interphalangeal joint.
    LF_PIP = 16  # Little finger proximal interphalangeal joint.
    LF_MCP = 17  # Little finger metacarpophalangeal joint.


class RS485BaudRate(enum.IntEnum):
    """Predefined RS485 baud rates mapped to GHand protocol gear values."""

    BAUD_57600 = 0x00  # 57600 baud; protocol gear 0.
    BAUD_115200 = 0x01  # 115200 baud; protocol gear 1.
    BAUD_230400 = 0x02  # 230400 baud; protocol gear 2.
    BAUD_460800 = 0x03  # 460800 baud; protocol gear 3.
    BAUD_921600 = 0x04  # 921600 baud; protocol gear 4.
    BAUD_1000000 = 0x05  # 1000000 baud; protocol gear 5.


class CANFDBitTiming(enum.IntEnum):
    """Predefined CAN FD bit timing profiles.

    Names use ``TIMING_<arbitration bitrate>_<data bitrate>``. Each value maps
    directly to the protocol gear stored by the GHand device.
    """

    # Arbitration: 500 Kbps @ 80%; data: 800 Kbps @ 80%.
    TIMING_500K_800K = 0x00  # Arbitration: 500 kbit/s at 80% sample point; data: 800 kbit/s at 80% sample point.
    # Arbitration: 500 Kbps @ 80%; data: 1 Mbps @ 75%.
    TIMING_500K_1M = 0x01  # Arbitration: 500 kbit/s at 80% sample point; data: 1 Mbit/s at 75% sample point.
    # Arbitration: 500 Kbps @ 80%; data: 2 Mbps @ 80%.
    TIMING_500K_2M = 0x02  # Arbitration: 500 kbit/s at 80% sample point; data: 2 Mbit/s at 80% sample point.
    # Arbitration: 500 Kbps @ 80%; data: 4 Mbps @ 80%.
    TIMING_500K_4M = 0x03  # Arbitration: 500 kbit/s at 80% sample point; data: 4 Mbit/s at 80% sample point.
    # Arbitration: 1 Mbps @ 75%; data: 1 Mbps @ 75%.
    TIMING_1M_1M = 0x04  # Arbitration: 1 Mbit/s at 75% sample point; data: 1 Mbit/s at 75% sample point.
    # Arbitration: 1 Mbps @ 75%; data: 2 Mbps @ 80%.
    TIMING_1M_2M = 0x05  # Arbitration: 1 Mbit/s at 75% sample point; data: 2 Mbit/s at 80% sample point.
    # Arbitration: 1 Mbps @ 75%; data: 4 Mbps @ 80%.
    TIMING_1M_4M = 0x06  # Arbitration: 1 Mbit/s at 75% sample point; data: 4 Mbit/s at 80% sample point.
    # Arbitration: 1 Mbps @ 75%; data: 5 Mbps @ 75%.
    TIMING_1M_5M = 0x07  # Arbitration: 1 Mbit/s at 75% sample point; data: 5 Mbit/s at 75% sample point.


class CommType(enum.Enum):
    UNKNOWN = "unknown"  # Unknown or undetermined communication type.
    ETHERCAT = "ethercat"  # EtherCAT communication.
    CANFD = "canfd"  # CAN FD communication.
    RS485 = "rs485"  # RS485 communication.


class TactileSensorId(enum.IntEnum):
    THUMB = 0  # Thumb tactile sensor.
    FF = 1  # Index finger tactile sensor.
    MF = 2  # Middle finger tactile sensor.
    RF = 3  # Ring finger tactile sensor.
    LF = 4  # Little finger tactile sensor.


class HandType(enum.Enum):
    NONE = "none"  # Unspecified or undetermined hand side.
    LEFT_HAND = "left_hand"  # Left hand.
    RIGHT_HAND = "right_hand"  # Right hand.

class GestureType(enum.Enum):
    OPEN_HAND = "open_hand"  # Open palm gesture.
    FIST = "fist"  # Closed fist gesture.
    OK = "ok"  # OK gesture.
    THUMBS_UP = "thumbs_up"  # Thumbs-up gesture.
    SIX_SIGN = "six_sign"  # Number six hand gesture.


class ProductType(enum.Enum):
    GHand5 = "GHand5"  # GHand5 dexterous hand model.
    GHandLite1 = "GHandLite1"  # GHandLite1 dexterous hand model.

class HandRuntimeState(enum.IntEnum):
    """Whole-hand runtime state reported by EtherCAT SDO 0x200A."""

    INITIALIZED = 0  # Initialization state.
    POWER_ON_SELF_TEST = 1  # Power-on self-test state.
    IDLE = 2  # Idle state.
    MOVING = 3  # Moving state.
    FAULT = 4  # Fault state.
    LOW_POWER = 5  # Low-power state.
    FIRMWARE_UPGRADE = 6  # Firmware upgrade state.
class HandControlMode(enum.Enum):
    POSITION = 0  # Position control using the target joint position.
    VELOCITY = 1  # Velocity control using the target joint velocity.
    CURRENT = 2  # Current control using the target motor current.
    MIT = 3  # MIT control combining target position, target speed, control gains, and other parameters.
    CUSTOM = 0x0F  # Custom control with semi-closed-loop or closed-loop selection via JointControlMode.
class HandControlState(enum.IntEnum):
    DISABLED = 0  # Disabled; the exact meaning depends on the interface using this enum.
    ENABLED = 1  # Enabled; the exact meaning depends on the interface using this enum.


class JointControlMode(enum.IntEnum):
    """Per-joint control modes; CUSTOM is only available at hand level."""

    POSITION = 0  # Position control using the target joint angle.
    VELOCITY = 1  # Velocity control using the target joint velocity (%).
    CURRENT = 2  # Current (torque) control using the target motor current (%).
    MIT = 3  # MIT control combining target angle, velocity, current, and kp/kd gains.
class JointLoopType(enum.IntEnum):
    """Feedback loop type encoded in the high nibble of TPDO joint mode."""
    # Only effective when CtrlMode is CUSTOM; other modes default to CLOSED_LOOP.

    SEMI_CLOSED_LOOP = 0  # Semi-closed-loop control.
    CLOSED_LOOP = 1  # Closed-loop control.

class JointControlState(enum.IntEnum):
    """Per-joint control state sent to the device."""

    DISABLED = 0  # Request joint disable, releasing drive force.
    RUNNING = 1  # Request the joint to enter the running state.
    STOPPED = 2  # Request the joint to stop moving and hold its current position.

class JointState(enum.IntEnum):
    DISABLED = 0  # Joint is disabled, with drive force released.
    RUNNING = 1  # Joint is in the running state.
    STOPPED = 2  # Joint has stopped moving and holds its current position.
    FAULT = 3  # Joint is in the fault state.

