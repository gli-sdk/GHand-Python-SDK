import math
import pytest
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.dexhand import JointId, TactileSensorId


class TestJointCommandBuilder:
    def test_open_pose_returns_all_joints(self):
        cfg = AdaptiveGraspConfig()
        builder = JointCommandBuilder(cfg, tuple())
        pose = builder.open_pose()
        assert JointId.THUMB_PIP in pose
        assert JointId.THUMB_SWING in pose
        assert JointId.FF_PIP in pose
        assert pose[JointId.THUMB_SWING] == math.radians(20)

    def test_torque_command_sets_inactive_to_zero(self):
        cfg = AdaptiveGraspConfig(pre_grasp_preset="two_finger_pinch")
        torque_joints = (
            JointId.THUMB_PIP, JointId.THUMB_MCP,
            JointId.FF_PIP, JointId.FF_MCP,
        )
        builder = JointCommandBuilder(cfg, torque_joints)
        joints = builder.torque_command(42)
        joint_map = {j.id: j for j in joints}

        active = set(torque_joints)
        for joint_id in JointCommandBuilder._TORQUE_JOINTS:
            j = joint_map[joint_id]
            if joint_id in active:
                assert j.torque == 42
            else:
                assert j.torque == 0
            assert j.angle == 0.0
            assert j.speed == 0

        assert joints[-2].id == JointId.THUMB_ROTATION
        assert joints[-1].id == JointId.THUMB_SWING
        assert joints[-2].torque == 5
        assert joints[-1].torque == 5

    def test_torque_command_uses_configured_thumb_aux_torque(self):
        cfg = AdaptiveGraspConfig(thumb_aux_torque=7)
        builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))

        joints = builder.torque_command(42)

        joint_map = {joint.id: joint for joint in joints}
        assert joint_map[JointId.THUMB_ROTATION].torque == 7
        assert joint_map[JointId.THUMB_SWING].torque == 7

    def test_torque_command_all_active_for_five_finger(self):
        cfg = AdaptiveGraspConfig(pre_grasp_preset="five_finger_grasp")
        torque_joints = tuple(JointCommandBuilder._TORQUE_JOINTS)
        builder = JointCommandBuilder(cfg, torque_joints)
        joints = builder.torque_command(77)
        joint_map = {j.id: j for j in joints}
        for joint_id in JointCommandBuilder._TORQUE_JOINTS:
            assert joint_map[joint_id].torque == 77

    def test_init_hold_angles_uses_pre_grasp_pose(self):
        cfg = AdaptiveGraspConfig(pre_grasp_preset="two_finger_pinch")
        torque_joints = (JointId.THUMB_PIP, JointId.FF_PIP)
        builder = JointCommandBuilder(cfg, torque_joints)
        angles = builder.init_hold_angles()
        assert angles[JointId.THUMB_PIP] == cfg.pre_grasp_pose[JointId.THUMB_PIP]
        assert angles[JointId.FF_PIP] == cfg.pre_grasp_pose[JointId.FF_PIP]

    def test_position_command_builds_joints(self):
        cfg = AdaptiveGraspConfig()
        builder = JointCommandBuilder(cfg, tuple())
        angles = {JointId.THUMB_PIP: 0.5, JointId.FF_PIP: 0.3}
        joints = builder.position_command(angles, speed=50, torque=60)
        joint_map = {j.id: j for j in joints}
        assert joint_map[JointId.THUMB_PIP].angle == 0.5
        assert joint_map[JointId.THUMB_PIP].speed == 50
        assert joint_map[JointId.THUMB_PIP].torque == 60

    def test_hold_position_command_limits_torque(self):
        cfg = AdaptiveGraspConfig(position_torque_limit=30, position_speed_limit=20)
        torque_joints = (JointId.THUMB_PIP,)
        builder = JointCommandBuilder(cfg, torque_joints)
        joints = builder.hold_position_command(torque=50)
        assert joints[0].torque == 30
        assert joints[0].speed == 20

    def test_hold_per_finger_torque_command_maps_finger_to_mcp_pip(self):
        cfg = AdaptiveGraspConfig(
            active_fingers={
                TactileSensorId.THUMB,
                TactileSensorId.FOREFINGER,
                TactileSensorId.MIDDLE_FINGER,
            },
        )
        builder = JointCommandBuilder(
            cfg,
            (
                JointId.THUMB_PIP,
                JointId.THUMB_MCP,
                JointId.FF_PIP,
                JointId.FF_MCP,
                JointId.MF_PIP,
                JointId.MF_MCP,
            ),
        )

        joints = builder.hold_per_finger_torque_command({
            TactileSensorId.THUMB: 5.4,
            TactileSensorId.FOREFINGER: 7.2,
            TactileSensorId.MIDDLE_FINGER: 9.0,
        })

        joint_map = {joint.id: joint for joint in joints}
        assert joint_map[JointId.THUMB_PIP].torque == 5
        assert joint_map[JointId.THUMB_MCP].torque == 5
        assert joint_map[JointId.FF_PIP].torque == 7
        assert joint_map[JointId.FF_MCP].torque == 7
        assert joint_map[JointId.MF_PIP].torque == 9
        assert joint_map[JointId.MF_MCP].torque == 9
        assert joint_map[JointId.RF_PIP].torque == 0
        assert joint_map[JointId.LF_PIP].torque == 0
