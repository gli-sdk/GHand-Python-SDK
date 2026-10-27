#1.这个是产品
class ProductType(enum.Enum):
    GHand5 = "GHand5"
    GHandLite1 = "GHandLite1"

#1.1 根据产品来获取配置文件，并赋值给ProductConfig和TactileRegionConfig
class TactileRegionConfig:
    """Configuration for a single tactile sensor region."""

    id: TactileSensorId
    count: int


@dataclass
class ProductConfig:
    """Product-specific configuration loaded from JSON."""

    name: str = ""
    model: str = ""
    valid_joints: list[JointId] = field(default_factory=list)
    joint_limits: dict[JointId, tuple[float, float]] = field(default_factory=dict)
    has_tactile: bool = False
    tactile_regions: list[TactileRegionConfig] = field(default_factory=list)
    product_type: ProductType | None = None
    slave_id: int = 0x31

# 这几个是控制模式和状态的枚举类
class CtrlMode(enum.Enum):
    POSITION = 0
    SPEED = 1
    CURRENT = 2
    MIT = 3
    CUSTOM = 0x0F

class JointControlState(enum.IntEnum):
    """Per-joint control state sent to the device."""

    DISABLED = 0
    RUNNING = 1
    STOPPED = 2

class JointControlMode(DeviceCode):
    """Feedback loop type encoded in the high nibble of TPDO joint mode."""
    #只有CtrlMode=CUSTOM时，这个才生效，其他模式下默认为CLOSED_LOOP

    SEMI_CLOSED_LOOP = 0
    CLOSED_LOOP = 1

    @classmethod
    def _missing_(cls, value):
        """Map undefined device values to UNKNOWN_TYPE while preserving the value."""
        return unknown_member(cls, cls.UNKNOWN_TYPE, value)

#2.1 是关节的指令
@dataclass
class JointCommand:
    """Single joint command sent to the device."""

    id: int = JointId.THUMB_IP
    mode: CtrlMode | None = None
    stop: JointControlState | int = JointControlState.RUNNING
    angle: float = 0.0  # degrees
    speed: int = 0
    current: int = 0
    kp: int = 0
    kd: int = 0

# 3.1整手状态机
class HandStateMachine(DeviceCode):
    """Whole-hand runtime state reported by EtherCAT SDO 0x200A."""

    INITIALIZED = 0
    POWER_ON_SELF_TEST = 1
    IDLE = 2
    MOVING = 3
    FAULT = 4
    LOW_POWER = 5
    FIRMWARE_UPGRADE = 6
    UNKNOWN_STATE = 255

    @classmethod
    def _missing_(cls, value):
        """Map undefined device values to UNKNOWN_STATE while preserving the value."""
        return unknown_member(cls, cls.UNKNOWN_STATE, value)


#3.2 整手关节状态、错误和数据
class HandState(DeviceCode):
    DISABLED = 0
    ENABLED = 1

class HandWarning(enum.IntFlag):
    """Hand-level warning bits from the EtherCAT V2.1 TPDO."""

    NONE = 0
    TEMPERATURE_SENSOR_1_ABNORMAL = 1 << 0
    TEMPERATURE_SENSOR_2_ABNORMAL = 1 << 1
    FAN_ABNORMAL = 1 << 2
    TACTILE_BOARD_COMMUNICATION_ABNORMAL = 1 << 3
    THUMB_TACTILE_SENSOR_DISCONNECTED = 1 << 4
    FOREFINGER_TACTILE_SENSOR_DISCONNECTED = 1 << 5
    MIDDLE_FINGER_TACTILE_SENSOR_DISCONNECTED = 1 << 6
    RING_FINGER_TACTILE_SENSOR_DISCONNECTED = 1 << 7
    LITTLE_FINGER_TACTILE_SENSOR_DISCONNECTED = 1 << 8
    SELF_TEST_ERROR = 1 << 9


class HandFault(enum.IntFlag):
    """Hand-level fault categories from the EtherCAT V2.1 TPDO."""

    NONE = 0
    JOINT_MOTOR = 1 << 0
    POSITION_SENSOR_ABNORMAL = 1 << 1
    POSITION_SENSOR_UNCALIBRATED = 1 << 2
    ZEROING_JOINT_STALL = 1 << 3
    ZEROING_BRAKE_TIMEOUT = 1 << 4
    ZEROING_MOTOR_COMMUNICATION = 1 << 5


class HandCriticalError(enum.IntFlag):
    """Hand-level critical-error bits from the EtherCAT V2.1 TPDO."""

    NONE = 0
    UNKNOWN_ERROR = 1 << 0
    POSITION_SENSOR_VERSION_MISMATCH = 1 << 2
    TACTILE_SENSOR_VERSION_MISMATCH = 1 << 3
    MOTOR_DRIVER_VERSION_MISMATCH = 1 << 4
    POSITION_BOARD_DETECTION_ABNORMAL = 1 << 5
    TEMPERATURE_TOO_HIGH = 1 << 6
    TEMPERATURE_TOO_LOW = 1 << 7
    ZEROING_GLOBAL_TIMEOUT = 1 << 8

class HandData:
    """High-level status of the dexterous hand."""

    state: HandState = HandState.DISABLED
    error_warn: bytes = b"\x00" * 6  #可以继续使用
    error_fault: bytes = b"\x00" * 12  #只是报错的那一块不可以使用
    error_critical: bytes = b"\x00" * 6   #全部都不可用
    temperature: int = 0

# 3.3 关节状态、错误和数据
class JointState(DeviceCode):
    DISABLED = 0
    RUNNING = 1
    STOPPED = 2
    FAULT = 3
    UNKNOWN_STATE = 255

    @classmethod
    def _missing_(cls, value):
        """Map any undefined joint state to UNKNOWN_STATE, keeping the raw value."""
        return unknown_member(cls, cls.UNKNOWN_STATE, value)

    @property
    def is_abnormal(self) -> bool:
        """True for fault or any undefined joint state."""
        return self not in (
            JointState.DISABLED,
            JointState.RUNNING,
            JointState.STOPPED,
        )

class JointErrorCode(DeviceCode):
    NORMAL = 0
    MOTOR_HARDWARE_OVERCURRENT = 1
    MOTOR_CONTINUOUS_CURRENT_HIGH = 2
    MOTOR_BUS_OVERCURRENT = 3
    MOTOR_HARDWARE_OVERVOLTAGE = 4
    MOTOR_HARDWARE_UNDERVOLTAGE = 5
    MOTOR_PHASE_LOSS = 6
    MOTOR_STALLED = 7
    MOTOR_CHIP_OVERTEMPERATURE = 8
    COMMUNICATION_LOST = 9
    MOTOR_SOFTWARE_OVERVOLTAGE = 10
    MOTOR_SOFTWARE_UNDERVOLTAGE = 11
    MOTOR_OVERTEMPERATURE = 12
    MOTOR_WINDING_OVERTEMPERATURE = 13
    UNKNOWN_ERROR = 255

###这个错误码是不是没有用到？
class ErrorCode(DeviceCode):
    NORMAL = 0
    MOTOR_HARDWARE_OVERCURRENT = 1
    MOTOR_SOFTWARE_OVERCURRENT = 2
    MOTOR_BUS_OVERCURRENT = 3
    MOTOR_PHASE_LOST = 4
    MOTOR_STALLED = 5
    MOTOR_DRIVER_OVERTEMP = 6
    MOTOR_COMM_ERROR = 7
    MOTOR_OVERTEMP = 8
    JOINT_CONFLICT = 11
    TIP_CONFLICT = 12
    JOINT_POSITION_ABNORMAL = 13
    LOW_TEMP = 21
    HIGH_TEMP = 22
    LOW_VOLTAGE = 23
    HIGH_VOLTAGE = 24
    TACTILE_DISCONNECTED = 31
    TACTILE_ERROR = 31
    TACTILE_DATA_ABNORMAL = 32
    SELF_TEST_ERROR = 41
    PARAM_ERROR = 101
    UNKNOWN_ERROR = 201

    @classmethod
    def _missing_(cls, value):
        """Map any undefined code to UNKNOWN_ERROR, keeping the raw value."""
        return unknown_member(cls, cls.UNKNOWN_ERROR, value)
    
class JointData:
    """Single joint state received from the device."""

    id: int = JointId.THUMB_IP
    state: JointState = JointState.DISABLED
    error: JointErrorCode = JointErrorCode.NORMAL
    mode: int = 0
    stop: int = 0
    angle: float = 0.0  # degrees
    speed: int = 0
    current: int = 0

    @property
    def control_mode(self) -> CtrlMode | None:
        """Return the control mode encoded in bits 0..3 of ``mode``."""
        try:
            return CtrlMode(self.mode & 0x0F)
        except ValueError:
            return None

    @property
    def closed_loop_type(self) -> JointControlMode:
        """Return the feedback loop type encoded in bits 4..7 of ``mode``."""
        return JointControlMode((self.mode >> 4) & 0x0F)

# 3.4 触觉传感器状态和数据
@dataclass
class TactileData:
    """Tactile sensor reading for a single finger, with forces in Newtons."""

    state: bool = False
    resultant_force: list[float] | None = None
    distributed_force: list[float] | None = None

# 3.5 包含整手，单关节，触觉所有数据
class DeviceData:
    """Unified data carrier for subscription callbacks across all protocols."""

    hand: HandData
    joints: list[JointData]
    tactile: dict[TactileSensorId, TactileData] | None = None
    timestamp: float | None = None

# 4 关节ID
class JointId(enum.IntEnum):
    THUMB_IP = 0
    THUMB_MCP = 1
    THUMB_TMC_FE = 2
    THUMB_TMC_AA = 3
    THUMB_TMC_PS = 4
    FF_DIP = 5
    FF_PIP = 6
    FF_MCP = 7
    FF_MCP_AA = 8
    MF_DIP = 9
    MF_PIP = 10
    MF_MCP = 11
    RF_DIP = 12
    RF_PIP = 13
    RF_MCP = 14
    LF_DIP = 15
    LF_PIP = 16
    LF_MCP = 17

# 5 波特率枚举
class RS485BaudRate(enum.IntEnum):
    """Predefined RS485 baud rates mapped to GHand protocol gear values."""

    BAUD_57600 = 0x00
    BAUD_115200 = 0x01
    BAUD_230400 = 0x02
    BAUD_460800 = 0x03
    BAUD_921600 = 0x04
    BAUD_1000000 = 0x05


class CANFDBitTiming(enum.IntEnum):
    """Predefined CAN FD bit timing profiles.

    Names use ``TIMING_<arbitration bitrate>_<data bitrate>``. Each value maps
    directly to the protocol gear stored by the GHand device.
    """

    # Arbitration: 500 Kbps @ 80%; data: 800 Kbps @ 80%.
    TIMING_500K_800K = 0x00
    # Arbitration: 500 Kbps @ 80%; data: 1 Mbps @ 75%.
    TIMING_500K_1M = 0x01
    # Arbitration: 500 Kbps @ 80%; data: 2 Mbps @ 80%.
    TIMING_500K_2M = 0x02
    # Arbitration: 500 Kbps @ 80%; data: 4 Mbps @ 80%.
    TIMING_500K_4M = 0x03
    # Arbitration: 1 Mbps @ 75%; data: 1 Mbps @ 75%.
    TIMING_1M_1M = 0x04
    # Arbitration: 1 Mbps @ 75%; data: 2 Mbps @ 80%.
    TIMING_1M_2M = 0x05
    # Arbitration: 1 Mbps @ 75%; data: 4 Mbps @ 80%.
    TIMING_1M_4M = 0x06
    # Arbitration: 1 Mbps @ 75%; data: 5 Mbps @ 75%.
    TIMING_1M_5M = 0x07

# 6 通信类型枚举
class CommType(enum.Enum):
    UNKNOWN = "unknown"
    ETHERCAT = "ethercat"
    CANFD = "canfd"
    RS485 = "rs485"

# 7 触觉传感器ID
class TactileSensorId(enum.IntEnum):
    THUMB = 0
    FF = 1
    MF = 2
    RF = 3
    LF = 4

# 8 手部类型
class HandType(enum.Enum):
    NONE = "none"
    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"
