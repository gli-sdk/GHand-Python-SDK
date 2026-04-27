from xiaoyao.dexhand import JointId, TactileSensorId


def clip(value: float, lower: float, upper: float) -> float:
    """Clip value to [lower, upper], swapping bounds if inverted."""
    if upper < lower:
        upper = lower
    return max(lower, min(upper, value))


JOINT_TO_FINGER: dict[JointId, TactileSensorId] = {
    JointId.THUMB_PIP: TactileSensorId.THUMB,
    JointId.THUMB_MCP: TactileSensorId.THUMB,
    JointId.FF_PIP: TactileSensorId.FOREFINGER,
    JointId.FF_MCP: TactileSensorId.FOREFINGER,
    JointId.FF_SWING: TactileSensorId.FOREFINGER,
    JointId.MF_PIP: TactileSensorId.MIDDLE_FINGER,
    JointId.MF_MCP: TactileSensorId.MIDDLE_FINGER,
    JointId.RF_PIP: TactileSensorId.RING_FINGER,
    JointId.RF_MCP: TactileSensorId.RING_FINGER,
    JointId.LF_PIP: TactileSensorId.LITTLE_FINGER,
    JointId.LF_MCP: TactileSensorId.LITTLE_FINGER,
}

FINGER_TO_MCP_PIP: dict[TactileSensorId, tuple[JointId, JointId]] = {
    TactileSensorId.THUMB: (JointId.THUMB_MCP, JointId.THUMB_PIP),
    TactileSensorId.FOREFINGER: (JointId.FF_MCP, JointId.FF_PIP),
    TactileSensorId.MIDDLE_FINGER: (JointId.MF_MCP, JointId.MF_PIP),
    TactileSensorId.RING_FINGER: (JointId.RF_MCP, JointId.RF_PIP),
    TactileSensorId.LITTLE_FINGER: (JointId.LF_MCP, JointId.LF_PIP),
}
