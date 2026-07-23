import math
from typing import Optional

from ghand import JointId, TactileSensorId


PASSIVE_DIP_JOINTS = {
    JointId.THUMB_IP,
    JointId.FF_DIP,
    JointId.MF_DIP,
    JointId.RF_DIP,
    JointId.LF_DIP,
}

ACTIVE_PRE_GRASP_JOINTS = (
    JointId.LF_MCP,
    JointId.LF_PIP,
    JointId.RF_MCP,
    JointId.RF_PIP,
    JointId.MF_MCP,
    JointId.MF_PIP,
    JointId.FF_MCP_AA,
    JointId.FF_MCP,
    JointId.FF_PIP,
    JointId.THUMB_TMC_PS,
    JointId.THUMB_TMC_AA,
    JointId.THUMB_TMC_FE,
    JointId.THUMB_MCP,
)

PRESET_ACTIVE_FINGERS: dict[str, set[TactileSensorId]] = {
    "two_finger_pinch": {TactileSensorId.THUMB, TactileSensorId.FF},
    "pen_pinch": {TactileSensorId.THUMB, TactileSensorId.FF},
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
    "lily_pinch": {TactileSensorId.THUMB, TactileSensorId.MF},
    "small_pinch": {TactileSensorId.THUMB, TactileSensorId.FF},
    "smooth_ball": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
    },
    "balloon_pinch": {TactileSensorId.THUMB, TactileSensorId.FF},
    "paper_cup_pinch": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
    },
    "glass_pinch": {
        TactileSensorId.THUMB,
        TactileSensorId.FF,
        TactileSensorId.MF,
    },
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
}


def pose_degrees(
    *,
    lf_mcp: float = 0.0,
    lf_pip: float = 0.0,
    rf_mcp: float = 0.0,
    rf_pip: float = 0.0,
    mf_mcp: float = 0.0,
    mf_pip: float = 0.0,
    ff_swing: float = 0.0,
    ff_mcp: float = 0.0,
    ff_pip: float = 0.0,
    thumb_rotation: float = 0.0,
    thumb_swing: float = 90.0,
    thumb_mcp: float = 0.0,
    thumb_pip: float = 0.0,
) -> dict[JointId, float]:
    return {
        JointId.LF_MCP: lf_mcp,
        JointId.LF_PIP: lf_pip,
        JointId.RF_MCP: rf_mcp,
        JointId.RF_PIP: rf_pip,
        JointId.MF_MCP: mf_mcp,
        JointId.MF_PIP: mf_pip,
        JointId.FF_MCP_AA: ff_swing,
        JointId.FF_MCP: ff_mcp,
        JointId.FF_PIP: ff_pip,
        JointId.THUMB_TMC_PS: thumb_rotation,
        JointId.THUMB_TMC_AA: thumb_swing,
        JointId.THUMB_TMC_FE: thumb_mcp,
        JointId.THUMB_MCP: thumb_pip,
    }


PRE_GRASP_PRESET_DEGREE = {
    "two_finger_pinch": pose_degrees(
        ff_mcp=60.0,
        ff_pip=20.0,
        thumb_swing=80.0,
        thumb_mcp=0.0,
        thumb_pip=0.0,
    ),
    "three_finger_pinch": pose_degrees(
        mf_mcp=50.0,
        mf_pip=10.0,
        ff_mcp=42.0,
        ff_pip=10.0,
        ff_swing=5.0,
        thumb_swing=80.0,
        thumb_pip=10,
        thumb_mcp=20.0,
        thumb_rotation=5.0,
    ),
    "three_finger_grasp": pose_degrees(
        mf_mcp=36.0,
        mf_pip=35.0,
        ff_mcp=28.0,
        ff_pip=41.0,
        thumb_swing=80.0,
        thumb_pip=28,
        thumb_mcp=10.0,
    ),
    "four_finger_grasp": pose_degrees(
        rf_mcp=47.0,
        rf_pip=19.0,
        mf_mcp=32.0,
        mf_pip=22.0,
        ff_mcp=44.0,
        ff_pip=21.0,
        thumb_rotation=11.0,
        thumb_swing=80.0,
        thumb_mcp=20.0,
        thumb_pip=5.0,
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
        thumb_rotation=2.0,
        thumb_swing=60.0,
        thumb_mcp=2.0,
        thumb_pip=21.0,
    ),
    "lily_pinch": pose_degrees(
        mf_mcp=31.0,
        thumb_rotation=7.0,
        thumb_mcp=6.0,
    ),
    "small_pinch": pose_degrees(
        thumb_swing=84,
        thumb_pip=10,
        ff_mcp=45.0,
        ff_pip=22.0,
        thumb_mcp=3.0,
    ),
    "smooth_ball": pose_degrees(
        ff_pip=26,
        ff_mcp=53.0,
        ff_swing=8,
        mf_mcp=59,
        mf_pip=20.0,
        thumb_swing=90,
        thumb_mcp=1,
        thumb_pip=7,
    ),
    "balloon_pinch": pose_degrees(
        ff_mcp=25.0,
        ff_pip=25.0,
        thumb_swing=80.0,
        thumb_mcp=3.0,
        thumb_pip=5.0,
    ),
    "paper_cup_pinch": pose_degrees(
        mf_mcp=49.0,
        mf_pip=10.0,
        ff_mcp=41.0,
        ff_pip=14.0,
        thumb_swing=85.0,
        thumb_mcp=4.0,
        thumb_pip=4.0,
    ),
    "glass_pinch": pose_degrees(
        mf_mcp=45.0,
        mf_pip=15.0,
        ff_mcp=35.0,
        ff_pip=20.0,
        thumb_mcp=11.0,
        thumb_pip=6.0,
    ),
    "plastic_three_pinch": pose_degrees(
        thumb_mcp=16,
        thumb_rotation=2,
        thumb_swing=71,
        ff_pip=20,
        ff_mcp=29,
        ff_swing=5,
        mf_pip=18,
        mf_mcp=40,
    ),
    "paper_cup_grasp": pose_degrees(
        thumb_mcp=15,
        thumb_pip=20,
        thumb_swing=80,
        thumb_rotation=4,
        ff_pip=45,
        ff_mcp=25,
        mf_pip=40,
        mf_mcp=40,
        rf_pip=40,
        rf_mcp=40,
        lf_pip=35,
        lf_mcp=35,
    ),
    "minreal_water_grasp": pose_degrees(
        thumb_mcp=15,
        thumb_pip=20,
        thumb_swing=80,
        thumb_rotation=4,
        ff_pip=45,
        ff_mcp=35,
        mf_pip=40,
        mf_mcp=40,
        rf_pip=40,
        rf_mcp=40,
        lf_pip=35,
        lf_mcp=35,
    ),
    "pen_pinch": pose_degrees(
        ff_mcp=46.0,
        ff_pip=52.0,
        thumb_swing=74.0,
        thumb_mcp=22.0,
        thumb_pip=13.0,
    ),
}

OBJECT_PRE_GRASP_PRESET = {
    "balloon": "balloon_pinch",
    "paper_cup": "paper_cup_pinch",
    "glass": "glass_pinch",
}


def resolve_pre_grasp_preset(default_object: str, explicit_preset: Optional[str]) -> str:
    if explicit_preset is not None:
        return explicit_preset
    return OBJECT_PRE_GRASP_PRESET.get(default_object, "balloon_pinch")


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
    if pre_grasp_preset not in PRE_GRASP_PRESET_DEGREE:
        supported = ", ".join(sorted(PRE_GRASP_PRESET_DEGREE.keys()))
        raise ValueError(f"pre_grasp_preset must be one of: {supported}")

    degrees_map = PRE_GRASP_PRESET_DEGREE[pre_grasp_preset]
    return {
        joint_id: math.radians(degrees_map.get(joint_id, 0.0))
        for joint_id in ACTIVE_PRE_GRASP_JOINTS
    }


def filter_passive_dip_joints(pose: dict[JointId, float]) -> dict[JointId, float]:
    return {
        joint_id: angle
        for joint_id, angle in pose.items()
        if joint_id not in PASSIVE_DIP_JOINTS
    }


def build_or_filter_pre_grasp_pose(
    pre_grasp_preset: str,
    explicit_pose: dict[JointId, float],
) -> dict[JointId, float]:
    if explicit_pose:
        filtered = filter_passive_dip_joints(explicit_pose)
        return filtered if filtered else build_pre_grasp_pose_from_preset(pre_grasp_preset)
    return build_pre_grasp_pose_from_preset(pre_grasp_preset)


def list_pre_grasp_presets() -> list[str]:
    return sorted(PRE_GRASP_PRESET_DEGREE.keys())
