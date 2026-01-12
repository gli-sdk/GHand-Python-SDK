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
class TactileTpdo:
    state: int
    error: int
    tactile: list[int]  # 存储8个uint8值

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = struct.calcsize('<BB8B')  # B(1字节) + B(1字节) + 8B(8字节)
        if len(data) < expected_size:
            return cls(0, 0, [0] * 8)
        state, error, *tactile = struct.unpack_from('<BB8B', data, 0)
        return cls(state, error, tactile)
    
    def scaled_data(self) -> list[float]:
        """
        将触觉数据进行缩放处理，获取真实值
        缩放方式:接收到的数据除以10

        Returns:
            list[float]: 缩放后的触觉数据列表,每个元素为float类型
        """
        return [t / 10.0 for t in self.tactile]


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
    tac_th: TactileTpdo
    tac_ff: TactileTpdo
    tac_mf: TactileTpdo
    tac_rf: TactileTpdo
    tac_lf: TactileTpdo
    tac_palm: TactileTpdo

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
                TactileTpdo(0, 0, [0] * 8),
                TactileTpdo(0, 0, [0] * 8),
                TactileTpdo(0, 0, [0] * 8),
                TactileTpdo(0, 0, [0] * 8),
                TactileTpdo(0, 0, [0] * 8),
                TactileTpdo(0, 0, [0] * 8)
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
        # tactile (6 sensors × 10 bytes = 60 bytes)
        tac_th = TactileTpdo.from_bytes(data[148:158]).scaled_data() # bytes 148-157
        tac_ff = TactileTpdo.from_bytes(data[158:168]).scaled_data() # bytes 158-167
        tac_mf = TactileTpdo.from_bytes(data[168:178]).scaled_data() # bytes 168-177
        tac_rf = TactileTpdo.from_bytes(data[178:188]).scaled_data() # bytes 178-187
        tac_lf = TactileTpdo.from_bytes(data[188:198]).scaled_data() # bytes 188-197
        tac_palm = TactileTpdo.from_bytes(data[198:208]).scaled_data()  # bytes 198-207

        return cls(hand, th_dip, th_pip, th_mcp, th_swing, th_rot, ff_dip, ff_pip, ff_mcp, ff_swing, mf_dip, mf_pip, mf_mcp, rf_dip, rf_pip, rf_mcp, lf_dip, lf_pip, lf_mcp, tac_th, tac_ff, tac_mf, tac_rf, tac_lf, tac_palm)


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
