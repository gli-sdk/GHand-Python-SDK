import struct
from dataclasses import dataclass, field  # 添加field导入


@dataclass
class HandTpdo:
    state: int
    error: int
    temp: int

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = struct.calcsize('<BBB')
        if not data or len(data) < expected_size:
            return cls(0, 0, 0)
        state, error, temp = struct.unpack_from('<BBB', data, 0)
        return cls(state, error, temp)


@dataclass
class JointTpdo:
    state: int
    error: int
    angle: float
    speed: float
    torque: float

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = struct.calcsize('<BBfff')
        if not data or len(data) < expected_size:
            return cls(0, 0, 0.0, 0.0, 0.0)
        state, error, angle, speed, torque = struct.unpack_from(
            '<BBfff', data, 0)
        return cls(state, error, angle, speed, torque)


@dataclass
class TactileTpdo:
    state: int
    error: int
    tactile: list[int]

    @classmethod
    def from_bytes(cls, data: bytes):
        expected_size = struct.calcsize('<BB18B')
        if not data or len(data) < expected_size:
            return cls(0, 0, [0] * 18)
        state, error, *tactile = struct.unpack_from('<BB18B', data, 0)
        return cls(state, error, tactile)


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

    @classmethod
    def from_bytes(cls, data: bytes):
        if not data:
            # 返回所有字段的默认实例
            return cls(
                HandTpdo(0, 0, 0),
                # thumb
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                # ff
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                # mf
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                # rf
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                # lf
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                JointTpdo(0, 0, 0.0, 0.0, 0.0),
                # tactile
                TactileTpdo(0, 0, [0] * 18),
                TactileTpdo(0, 0, [0] * 18),
                TactileTpdo(0, 0, [0] * 18),
                TactileTpdo(0, 0, [0] * 18),
                TactileTpdo(0, 0, [0] * 18)
            )
        # hand
        hand = HandTpdo.from_bytes(data[0:4])
        # thumb
        th_dip = JointTpdo.from_bytes(data[4:14])
        th_pip = JointTpdo.from_bytes(data[14:24])
        th_mcp = JointTpdo.from_bytes(data[24:34])
        th_swing = JointTpdo.from_bytes(data[34:44])
        th_rot = JointTpdo.from_bytes(data[44:54])
        # ff
        ff_dip = JointTpdo.from_bytes(data[54:64])
        ff_pip = JointTpdo.from_bytes(data[64:74])
        ff_mcp = JointTpdo.from_bytes(data[74:84])
        ff_swing = JointTpdo.from_bytes(data[84:94])
        # mf
        mf_dip = JointTpdo.from_bytes(data[94:104])
        mf_pip = JointTpdo.from_bytes(data[104:114])
        mf_mcp = JointTpdo.from_bytes(data[114:124])
        # rf
        rf_dip = JointTpdo.from_bytes(data[124:134])
        rf_pip = JointTpdo.from_bytes(data[134:144])
        rf_mcp = JointTpdo.from_bytes(data[144:154])
        # lf
        lf_dip = JointTpdo.from_bytes(data[154:164])
        lf_pip = JointTpdo.from_bytes(data[164:174])
        lf_mcp = JointTpdo.from_bytes(data[174:184])
        # tactile
        tac_th = TactileTpdo.from_bytes(data[184:194])
        tac_ff = TactileTpdo.from_bytes(data[194:204])
        tac_mf = TactileTpdo.from_bytes(data[204:214])
        tac_rf = TactileTpdo.from_bytes(data[214:224])
        tac_lf = TactileTpdo.from_bytes(data[224:234])
        return cls(hand, th_dip, th_pip, th_mcp, th_swing, th_rot, ff_dip, ff_pip, ff_mcp, ff_swing, mf_dip, mf_pip, mf_mcp, rf_dip, rf_pip, rf_mcp, lf_dip, lf_pip, lf_mcp, tac_th, tac_ff, tac_mf, tac_rf, tac_lf)


@dataclass
class JointRpdo:
    angle: float = 0.0
    speed: float = 0.0
    torque: float = 0.0

    def to_bytes(self) -> bytes:
        return struct.pack('<fff', self.angle, self.speed, self.torque)


@dataclass
class Rpdo:
    mode: int = 0
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
        return mode + th_pip + th_mcp + th_swing + th_rot + ff_pip + ff_mcp + ff_swing + mf_pip + mf_mcp + rf_pip + rf_mcp + lf_pip + lf_mcp
