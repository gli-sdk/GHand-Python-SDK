from ghand import JointId, TactileSensorId


def clip(value: float, lower: float, upper: float) -> float:
    """Clip value to [lower, upper], swapping bounds if inverted."""
    if upper < lower:
        upper = lower
    return max(lower, min(upper, value))


def tactile_force_xyz(info) -> tuple[float, float, float]:
    force = getattr(info, "resultant_force", None)
    if force is not None:
        values = list(force)
        return (
            float(values[0]) if len(values) > 0 else 0.0,
            float(values[1]) if len(values) > 1 else 0.0,
            float(values[2]) if len(values) > 2 else 0.0,
        )
    return (
        float(info.get_force_x()) if hasattr(info, "get_force_x") else 0.0,
        float(info.get_force_y()) if hasattr(info, "get_force_y") else 0.0,
        float(info.get_force_z()) if hasattr(info, "get_force_z") else 0.0,
    )


def tactile_distributed_force(info) -> list[float]:
    force = getattr(info, "distributed_force", None)
    if force is not None:
        return [float(value) for value in force]
    if hasattr(info, "get_distributed_force"):
        return [float(value) for value in info.get_distributed_force()]
    return []


JOINT_TO_FINGER: dict[JointId, TactileSensorId] = {
    JointId.THUMB_PIP: TactileSensorId.THUMB,
    JointId.THUMB_MCP: TactileSensorId.THUMB,
    JointId.FF_PIP: TactileSensorId.FF,
    JointId.FF_MCP: TactileSensorId.FF,
    JointId.FF_SWING: TactileSensorId.FF,
    JointId.MF_PIP: TactileSensorId.MF,
    JointId.MF_MCP: TactileSensorId.MF,
    JointId.RF_PIP: TactileSensorId.RF,
    JointId.RF_MCP: TactileSensorId.RF,
    JointId.LF_PIP: TactileSensorId.LF,
    JointId.LF_MCP: TactileSensorId.LF,
}

FINGER_TO_MCP_PIP: dict[TactileSensorId, tuple[JointId, JointId]] = {
    TactileSensorId.THUMB: (JointId.THUMB_MCP, JointId.THUMB_PIP),
    TactileSensorId.FF: (JointId.FF_MCP, JointId.FF_PIP),
    TactileSensorId.MF: (JointId.MF_MCP, JointId.MF_PIP),
    TactileSensorId.RF: (JointId.RF_MCP, JointId.RF_PIP),
    TactileSensorId.LF: (JointId.LF_MCP, JointId.LF_PIP),
}
