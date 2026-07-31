from ghand import JointId, TactileSensorId


PASSIVE_DIP_JOINTS: set[JointId] = {
    JointId.THUMB_IP,
    JointId.FF_DIP,
    JointId.MF_DIP,
    JointId.RF_DIP,
    JointId.LF_DIP,
}

PRESET_ACTIVE_FINGERS: dict[str, set[TactileSensorId]] = {
    "two_finger_pinch": {TactileSensorId.THUMB, TactileSensorId.FF},
    "three_finger_pinch": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
    },
    "three_finger_grasp": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
    },
    "four_finger_grasp": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
        TactileSensorId.RF,
    },
    "five_finger_grasp": set(TactileSensorId),
    "balloon_pinch": {TactileSensorId.THUMB, TactileSensorId.FF},
    "plastic_three_pinch": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
    },
    "paper_cup_grasp": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
        TactileSensorId.RF,
        TactileSensorId.LF,
    },
    "minreal_water_grasp": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
        TactileSensorId.RF,
        TactileSensorId.LF,
    },
    "cylinder_piece_grasp": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
        TactileSensorId.RF,
    },
}


def pose_degrees(
    *,
    lf_mcp: float = 0.0,
    lf_pip: float = 0.0,
    rf_mcp: float = 0.0,
    rf_pip: float = 0.0,
    mf_mcp: float = 0.0,
    mf_pip: float = 0.0,
    ff_mcp_aa: float = 0.0,
    ff_mcp: float = 0.0,
    ff_pip: float = 0.0,
    thumb_tmc_ps: float = 0.0,
    thumb_tmc_aa: float = 90.0,
    thumb_tmc_fe: float = 0.0,
    thumb_mcp: float = 0.0,
) -> dict[JointId, float]:
    return {
        JointId.LF_MCP: lf_mcp,
        JointId.LF_PIP: lf_pip,
        JointId.RF_MCP: rf_mcp,
        JointId.RF_PIP: rf_pip,
        JointId.MF_MCP: mf_mcp,
        JointId.MF_PIP: mf_pip,
        JointId.FF_MCP_AA: ff_mcp_aa,
        JointId.FF_MCP: ff_mcp,
        JointId.FF_PIP: ff_pip,
        JointId.THUMB_TMC_PS: thumb_tmc_ps,
        JointId.THUMB_TMC_AA: thumb_tmc_aa,
        JointId.THUMB_TMC_FE: thumb_tmc_fe,
        JointId.THUMB_MCP: thumb_mcp,
    }


ACTIVE_PRE_GRASP_JOINTS: tuple[JointId, ...] = tuple(pose_degrees().keys())


PRE_GRASP_PRESET_DEGREES: dict[str, dict[JointId, float]] = {
    "two_finger_pinch": pose_degrees(
        ff_mcp=60.0,
        ff_pip=20.0,
        thumb_tmc_aa=80.0,
        thumb_tmc_fe=0.0,
        thumb_mcp=0.0,
    ),
    "three_finger_pinch": pose_degrees(
        mf_mcp=50.0,
        mf_pip=10.0,
        ff_mcp=42.0,
        ff_pip=10.0,
        ff_mcp_aa=5.0,
        thumb_tmc_aa=80.0,
        thumb_mcp=10.0,
        thumb_tmc_fe=20.0,
        thumb_tmc_ps=5.0,
    ),
    "three_finger_grasp": pose_degrees(
        mf_mcp=36.0,
        mf_pip=35.0,
        ff_mcp=28.0,
        ff_pip=41.0,
        thumb_tmc_aa=80.0,
        thumb_mcp=28.0,
        thumb_tmc_fe=10.0,
    ),
    "four_finger_grasp": pose_degrees(
        rf_mcp=47.0,
        rf_pip=19.0,
        mf_mcp=32.0,
        mf_pip=22.0,
        ff_mcp=44.0,
        ff_pip=21.0,
        thumb_tmc_ps=11.0,
        thumb_tmc_aa=80.0,
        thumb_tmc_fe=20.0,
        thumb_mcp=5.0,
    ),
    "five_finger_grasp": pose_degrees(
        lf_mcp=45.0,
        lf_pip=30.0,
        rf_mcp=60.0,
        rf_pip=25.0,
        mf_mcp=53.0,
        mf_pip=30.0,
        ff_mcp=45.0,
        ff_pip=35.0,
        thumb_tmc_ps=2.0,
        thumb_tmc_aa=60.0,
        thumb_tmc_fe=2.0,
        thumb_mcp=21.0,
    ),
    "balloon_pinch": pose_degrees(
        ff_mcp=25.0,
        ff_pip=25.0,
        thumb_tmc_aa=80.0,
        thumb_tmc_fe=3.0,
        thumb_mcp=5.0,
    ),
    "plastic_three_pinch": pose_degrees(
        thumb_tmc_fe=16.0,
        thumb_tmc_ps=2.0,
        thumb_tmc_aa=71.0,
        ff_pip=20.0,
        ff_mcp=29.0,
        ff_mcp_aa=5.0,
        mf_pip=18.0,
        mf_mcp=40.0,
    ),
    "paper_cup_grasp": pose_degrees(
        thumb_tmc_fe=15.0,
        thumb_mcp=20.0,
        thumb_tmc_aa=85.0,
        thumb_tmc_ps=4.0,
        ff_pip=45.0,
        ff_mcp=25.0,
        mf_pip=40.0,
        mf_mcp=40.0,
        rf_pip=40.0,
        rf_mcp=40.0,
        lf_pip=25.0,
        lf_mcp=55.0,
    ),
    "minreal_water_grasp": pose_degrees(
        thumb_tmc_fe=15.0,
        thumb_mcp=20.0,
        thumb_tmc_aa=80.0,
        thumb_tmc_ps=4.0,
        ff_pip=45.0,
        ff_mcp=35.0,
        mf_pip=40.0,
        mf_mcp=40.0,
        rf_pip=40.0,
        rf_mcp=40.0,
        lf_pip=35.0,
        lf_mcp=35.0,
    ),
    "cylinder_piece_grasp": pose_degrees(
        thumb_tmc_fe=8.0,
        thumb_mcp=8.0,
        thumb_tmc_aa=89.0,
        thumb_tmc_ps=32.0,
        ff_pip=20.0,
        ff_mcp=30.0,
        mf_pip=24.0,
        mf_mcp=36.0,
        rf_pip=28.0,
        rf_mcp=32.0,
        lf_pip=20.0,
        lf_mcp=29.0,
    )
}


def resolve_active_fingers(
    pre_grasp_preset: str,
    explicit_active_fingers: set[TactileSensorId],
) -> set[TactileSensorId]:
    if explicit_active_fingers:
        return set(explicit_active_fingers)
    if pre_grasp_preset not in PRESET_ACTIVE_FINGERS:
        supported = ", ".join(sorted(PRESET_ACTIVE_FINGERS.keys()))
        raise ValueError(
            f'pre_grasp_preset="{pre_grasp_preset}" is missing an active_fingers mapping. '
            "Add it to PRESET_ACTIVE_FINGERS in adaptive_grasp.grasp_presets, "
            "or pass active_fingers explicitly to AdaptiveGraspConfig(...). "
            f"Supported mapped presets: {supported}"
        )
    return set(PRESET_ACTIVE_FINGERS[pre_grasp_preset])


def build_pre_grasp_pose_from_preset(pre_grasp_preset: str) -> dict[JointId, float]:
    if pre_grasp_preset not in PRE_GRASP_PRESET_DEGREES:
        supported = ", ".join(sorted(PRE_GRASP_PRESET_DEGREES.keys()))
        raise ValueError(f"pre_grasp_preset must be one of: {supported}")

    degrees_map = PRE_GRASP_PRESET_DEGREES[pre_grasp_preset]
    return {
        joint_id: degrees_map.get(joint_id, 0.0)
        for joint_id in ACTIVE_PRE_GRASP_JOINTS
    }


def list_pre_grasp_presets() -> list[str]:
    return sorted(PRE_GRASP_PRESET_DEGREES.keys())
