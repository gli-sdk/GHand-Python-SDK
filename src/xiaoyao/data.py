import struct
from dataclasses import dataclass, field  # 添加field导入


@dataclass
class HandTpdo:
    state: int
    error: int
    temp: int

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = struct.calcsize('<BBH')
        if len(data) < expected_size:
            return cls(0, 0, 0)
        state, error, temp = struct.unpack_from('<BBH', data, 0)
        return cls(state, error, temp)


@dataclass
class JointTpdo:
    state: int
    error: int
    angle: float
    speed: int
    torque: int

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = struct.calcsize('<BBfBB')
        if len(data) < expected_size:
            return cls(0, 0, 0.0, 0, 0)
        state, error, angle, speed, torque = struct.unpack_from('<BBfBB', data, 0)
        return cls(state, error, angle, speed, torque)


@dataclass
class TactileSensorStatus:
    """触觉传感器状态类"""
    state: int = 0  # uint8 状态码
    error: int = 0  # uint8 错误码

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = 2  # 2字节：1字节state + 1字节error
        if len(data) < expected_size:
            return cls()
        
        # 解析状态和错误码 (uint8, uint8)
        state, error = struct.unpack_from('<BB', data, 0)
        return cls(state=state, error=error)

@dataclass
class ThumbTactileData:
    """大拇指触觉数据类"""
    resultant_force: list[int] = field(default_factory=lambda: [0, 0, 0])  # 合力数据 xyz (int16, int16, uint16)
    sample_force: list[int] = field(default_factory=lambda: [0] * 156)     # 分布力数据 52组xyz

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = 162  # 6字节合力数据 + 156字节分布力数据
        if len(data) < expected_size:
            return cls()
        
        # 解析合力数据 (虽然为int16, int16, uint16，但只取低字节为有效值)
        rf_x_low = struct.unpack_from('<b', data, 0)[0]  # 取低字节作为int8
        rf_y_low = struct.unpack_from('<b', data, 2)[0]  # 取低字节作为int8
        rf_z_low = struct.unpack_from('<B', data, 4)[0]  # 取低字节作为uint8
        resultant_force = [rf_x_low, rf_y_low, rf_z_low]
        
        # 解析分布力数据 (52组xyz，其中xy为int8，z为uint8) - 共156字节
        sample_force = []
        for i in range(52):
            offset = 6 + i * 3  # 6字节合力数据偏移
            x, y, z = struct.unpack_from('<bbB', data, offset)
            sample_force.extend([x, y, z])
            
        return cls(resultant_force=resultant_force, sample_force=sample_force)

@dataclass
class FingerTactileData:
    """其余四指触觉数据类"""
    resultant_force: list[int] = field(default_factory=lambda: [0, 0, 0])  # 合力数据 xyz (int16, int16, uint16)
    sample_force: list[int] = field(default_factory=lambda: [0] * 93)      # 分布力数据 31组xyz

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = 99  # 6字节合力数据 + 93字节分布力数据
        if len(data) < expected_size:
            return cls()
        
        # 解析合力数据 (虽然为int16, int16, uint16，但只取低字节为有效值)
        rf_x_low = struct.unpack_from('<b', data, 0)[0]  # 取低字节作为int8
        rf_y_low = struct.unpack_from('<b', data, 2)[0]  # 取低字节作为int8
        rf_z_low = struct.unpack_from('<B', data, 4)[0]  # 取低字节作为uint8
        resultant_force = [rf_x_low, rf_y_low, rf_z_low]
        
        # 解析分布力数据 (31组xyz，其中xy为int8，z为uint8) - 共93字节
        sample_force = []
        for i in range(31):
            offset = 6 + i * 3  # 6字节合力数据偏移
            x, y, z = struct.unpack_from('<bbB', data, offset)
            sample_force.extend([x, y, z])
            
        return cls(resultant_force=resultant_force, sample_force=sample_force)



def _convert_tactile_to_N(tactile_data):
    """将触觉数据从0.1N单位转换为N单位"""
    if isinstance(tactile_data, ThumbTactileData):
        return ThumbTactileData(
            resultant_force=[round(f * 0.1, 1) for f in tactile_data.resultant_force],
            sample_force=[round(f * 0.1, 1) for f in tactile_data.sample_force]
        )
    elif isinstance(tactile_data, FingerTactileData):
        return FingerTactileData(
            resultant_force=[round(f * 0.1, 1) for f in tactile_data.resultant_force],
            sample_force=[round(f * 0.1, 1) for f in tactile_data.sample_force]
        )
    else:
        return tactile_data

@dataclass
class Tpdo:
    hand: HandTpdo
    # thumb
    th_dip: JointTpdo
    th_pip: JointTpdo
    th_mcp: JointTpdo
    th_swing: JointTpdo
    th_rot: JointTpdo
    # ff
    ff_dip: JointTpdo
    ff_pip: JointTpdo
    ff_mcp: JointTpdo
    ff_swing: JointTpdo
    # mf
    mf_dip: JointTpdo
    mf_pip: JointTpdo
    mf_mcp: JointTpdo
    # rf
    rf_dip: JointTpdo
    rf_pip: JointTpdo
    rf_mcp: JointTpdo
    # lf
    lf_dip: JointTpdo
    lf_pip: JointTpdo
    lf_mcp: JointTpdo
    # tactile
    tactile_status: TactileSensorStatus     # 触觉传感器状态
    thumb_tactile: ThumbTactileData         # 大拇指触觉数据
    ff_tactile: FingerTactileData           # 食指触觉数据
    mf_tactile: FingerTactileData           # 中指触觉数据
    rf_tactile: FingerTactileData           # 无名指触觉数据
    lf_tactile: FingerTactileData           # 小指触觉数据

    @classmethod
    def from_bytes(cls, data: bytes):
        if len(data) < 208:
            # 返回所有字段的默认实例
            return cls(
                HandTpdo(0, 0, 0),
                # thumb
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                # ff
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                # mf
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                # rf
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                # lf
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                JointTpdo(0, 0, 0.0, 0, 0),
                # tactile
                TactileSensorStatus(),
                ThumbTactileData(),
                FingerTactileData(),
                FingerTactileData(),
                FingerTactileData(),
                FingerTactileData()
            )
        
        # hand (4 bytes)
        hand = HandTpdo.from_bytes(data[0:4])  # 实际使用4个字节（索引0-3）BBH
        # thumb(BBfBB) (5 joints × 8 bytes = 40 bytes)
        th_dip = JointTpdo.from_bytes(data[4:12])    # bytes 4-11
        th_pip = JointTpdo.from_bytes(data[12:20])   # bytes 12-19
        th_mcp = JointTpdo.from_bytes(data[20:28])   # bytes 20-27
        th_swing = JointTpdo.from_bytes(data[28:36]) # bytes 28-35
        th_rot = JointTpdo.from_bytes(data[36:44])   # bytes 36-43
        # ff (4 joints × 8 bytes = 32 bytes)
        ff_dip = JointTpdo.from_bytes(data[44:52])   # bytes 44-51
        ff_pip = JointTpdo.from_bytes(data[52:60])  # bytes 52-59
        ff_mcp = JointTpdo.from_bytes(data[60:68]) # bytes 60-67
        ff_swing = JointTpdo.from_bytes(data[68:76]) # bytes 68-75
        # mf (3 joints × 8 bytes = 24 bytes)
        mf_dip = JointTpdo.from_bytes(data[76:84]) # bytes 76-83
        mf_pip = JointTpdo.from_bytes(data[84:92]) # bytes 84-91
        mf_mcp = JointTpdo.from_bytes(data[92:100]) # bytes 92-99
        # rf (3 joints × 8 bytes = 24 bytes)
        rf_dip = JointTpdo.from_bytes(data[100:108]) # bytes 100-107
        rf_pip = JointTpdo.from_bytes(data[108:116]) # bytes 108-115
        rf_mcp = JointTpdo.from_bytes(data[116:124]) # bytes 116-123
        # lf (3 joints × 8 bytes = 24 bytes)
        lf_dip = JointTpdo.from_bytes(data[124:132]) # bytes 124-131
        lf_pip = JointTpdo.from_bytes(data[132:140]) # bytes 132-139
        lf_mcp = JointTpdo.from_bytes(data[140:148]) # bytes 140-147
        # tactile 31 + 157 + 94*4 = 564 bytes
        tactile_status = TactileSensorStatus.from_bytes(data[148:150])      # bytes 148-149
        
        # 解析触觉数据并转换为N单位
        thumb_tactile_raw = ThumbTactileData.from_bytes(data[150:312])          # bytes 150-311
        ff_tactile_raw = FingerTactileData.from_bytes(data[312:411])            # bytes 312-410
        mf_tactile_raw = FingerTactileData.from_bytes(data[411:510])            # bytes 411-509
        rf_tactile_raw = FingerTactileData.from_bytes(data[510:609])            # bytes 510-608
        lf_tactile_raw = FingerTactileData.from_bytes(data[609:708])            # bytes 609-707 (总共560字节触觉数据)
        
        # 使用辅助函数转换触觉数据为N单位
        thumb_tactile = _convert_tactile_to_N(thumb_tactile_raw)
        ff_tactile = _convert_tactile_to_N(ff_tactile_raw)
        mf_tactile = _convert_tactile_to_N(mf_tactile_raw)
        rf_tactile = _convert_tactile_to_N(rf_tactile_raw)
        lf_tactile = _convert_tactile_to_N(lf_tactile_raw)

        return cls(hand, th_dip, th_pip, th_mcp, th_swing, th_rot,
                   ff_dip, ff_pip, ff_mcp, ff_swing,
                   mf_dip, mf_pip, mf_mcp,
                   rf_dip, rf_pip, rf_mcp,
                   lf_dip, lf_pip, lf_mcp,
                   tactile_status, thumb_tactile, ff_tactile, mf_tactile, rf_tactile, lf_tactile)


@dataclass
class JointRpdo:
    angle: float = 0.0
    speed: int = 0
    torque: int = 0

    def to_bytes(self) -> bytes:
        return struct.pack('<fBB', self.angle, self.speed, self.torque)


@dataclass
class Rpdo:
    mode: int = 0
    stop: int = 0
    # thumb
    th_pip: JointRpdo = field(default_factory=JointRpdo)
    th_mcp: JointRpdo = field(default_factory=JointRpdo)
    th_swing: JointRpdo = field(default_factory=JointRpdo)
    th_rot: JointRpdo = field(default_factory=JointRpdo)
    # ff
    ff_pip: JointRpdo = field(default_factory=JointRpdo)
    ff_mcp: JointRpdo = field(default_factory=JointRpdo)
    ff_swing: JointRpdo = field(default_factory=JointRpdo)
    # mf
    mf_pip: JointRpdo = field(default_factory=JointRpdo)
    mf_mcp: JointRpdo = field(default_factory=JointRpdo)
    # rf
    rf_pip: JointRpdo = field(default_factory=JointRpdo)
    rf_mcp: JointRpdo = field(default_factory=JointRpdo)
    # lf
    lf_pip: JointRpdo = field(default_factory=JointRpdo)
    lf_mcp: JointRpdo = field(default_factory=JointRpdo)

    def to_bytes(self) -> bytes:
        # control mode
        mode = struct.pack('<B', self.mode)
        stop = struct.pack('<B', self.stop)
        # thumb
        th_pip = self.th_pip.to_bytes()
        th_mcp = self.th_mcp.to_bytes()
        th_swing = self.th_swing.to_bytes()
        th_rot = self.th_rot.to_bytes()
        # ff
        ff_pip = self.ff_pip.to_bytes()
        ff_mcp = self.ff_mcp.to_bytes()
        ff_swing = self.ff_swing.to_bytes()
        # mf
        mf_pip = self.mf_pip.to_bytes()
        mf_mcp = self.mf_mcp.to_bytes()
        # rf
        rf_pip = self.rf_pip.to_bytes()
        rf_mcp = self.rf_mcp.to_bytes()
        # lf
        lf_pip = self.lf_pip.to_bytes()
        lf_mcp = self.lf_mcp.to_bytes()
        return mode + stop + th_pip + th_mcp + th_swing + th_rot + ff_pip + ff_mcp + ff_swing + mf_pip + mf_mcp + rf_pip + rf_mcp + lf_pip + lf_mcp
