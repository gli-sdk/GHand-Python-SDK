import math
import threading
import time

import pytest

import xiaoyao
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig, AdaptiveGrasper, GraspState
from xiaoyao.adaptive_grasp.object_profile import ObjectProfile
from xiaoyao.adaptive_grasp.force_planner import ForcePlanner
from xiaoyao.adaptive_grasp.safety import SafetyReport, SafetyStatus
from xiaoyao.adaptive_grasp.tactility import TactileAnalysis
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.adaptive_grasp.sensor import SensorClient
from xiaoyao.dexhand import CtrlMode, Joint, JointId, TactileSensorId

print(xiaoyao.adaptive_grasp.__file__)
print("hello world")


class _FakeTactileInfo:
    def __init__(self, fx: float, fy: float, fz: float, state: bool = True):
        self._fx = fx
        self._fy = fy
        self._fz = fz
        self.state = state

    def get_force_x(self) -> float:
        return self._fx

    def get_force_y(self) -> float:
        return self._fy

    def get_force_z(self) -> float:
        return self._fz


class _MockHand:
    """支持 subscribe/unsubscribe 的 mock hand，所有传感器数据通过缓存统一更新。"""

    def __init__(self):
        self.calls: list[dict] = []
        self._subscribers: dict[int, Callable] = {}
        self._sub_id = 0

    def move_joints(self, joints, mode=None):  # noqa: ANN001
        self.calls.append({"mode": mode, "joints": list(joints)})
        return True

    def stop(self):
        return None

    def subscribe(self, callback):
        self._sub_id += 1
        self._subscribers[self._sub_id] = callback
        return self._sub_id

    def unsubscribe(self, sub_id):
        if sub_id in self._subscribers:
            del self._subscribers[sub_id]

    def get_joints(self):
        return []


def _joint_map(call):
    return {joint.id: joint for joint in call["joints"]}


def test_clip_clamps_and_handles_inverted_bounds():
    from xiaoyao.adaptive_grasp.utils import clip

    assert clip(5.0, 0.0, 10.0) == pytest.approx(5.0)
    assert clip(-1.0, 0.0, 10.0) == pytest.approx(0.0)
    assert clip(11.0, 0.0, 10.0) == pytest.approx(10.0)
    assert clip(3.0, 2.0, 1.0) == pytest.approx(2.0)


def test_release_waits_until_joints_settled(monkeypatch):
    cfg = AdaptiveGraspConfig(
        release_timeout_s=0.2,
        release_check_cycles=2,
        theta_err_th=math.radians(2.0),
    )
    target = JointCommandBuilder(cfg, tuple()).open_pose()
    hand = _MockHand()
    g = AdaptiveGrasper(hand, cfg)
    g._running = True
    # 通过缓存提供关节反馈序列
    feedback_sequence = iter([
        [Joint(id=joint_id, angle=angle) for joint_id, angle in target.items()],
        [Joint(id=joint_id, angle=angle) for joint_id, angle in target.items()],
        [Joint(id=joint_id, angle=angle) for joint_id, angle in target.items()],
    ])
    g._sensor._latest_joint_feedback = next(feedback_sequence)

    def mock_joint_feedback(self):
        return next(feedback_sequence, self._latest_joint_feedback)

    monkeypatch.setattr(SensorClient, "joint_feedback", property(mock_joint_feedback))
    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)
    t = {"v": 0.0}
    g._get_monotonic_time = lambda: (t.__setitem__("v", t["v"] + 0.01) or t["v"])

    assert g.release() is True
    assert g.state == GraspState.COMPLETED


def test_release_fails_when_timeout_before_settled(monkeypatch):
    cfg = AdaptiveGraspConfig(
        release_timeout_s=0.02,
        release_check_cycles=2,
        theta_err_th=math.radians(1.0),
    )
    target = JointCommandBuilder(cfg, tuple()).open_pose()
    far = {joint_id: angle + math.radians(10.0) for joint_id, angle in target.items()}
    hand = _MockHand()
    g = AdaptiveGrasper(hand, cfg)
    g._running = True
    feedback_sequence = iter([
        [Joint(id=joint_id, angle=angle) for joint_id, angle in far.items()],
        [Joint(id=joint_id, angle=angle) for joint_id, angle in far.items()],
        [Joint(id=joint_id, angle=angle) for joint_id, angle in far.items()],
        [Joint(id=joint_id, angle=angle) for joint_id, angle in far.items()],
    ])
    g._sensor._latest_joint_feedback = next(feedback_sequence)

    def mock_joint_feedback(self):
        return next(feedback_sequence, self._latest_joint_feedback)

    monkeypatch.setattr(SensorClient, "joint_feedback", property(mock_joint_feedback))
    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)
    t = {"v": 0.0}
    g._get_monotonic_time = lambda: (t.__setitem__("v", t["v"] + 0.01) or t["v"])

    assert g.release() is False
    assert g.state == GraspState.ERROR


def test_full_grasp_state_transitions(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        release_hold_time_s=0.05,
        control_period_s=0.01,
    )
    grasper = AdaptiveGrasper(hand, cfg)

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)
    monkeypatch.setattr("xiaoyao.adaptive_grasp.phase_controller.time.sleep", lambda *_: None)
    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)
    monkeypatch.setattr(grasper._sensor, "reset", lambda: None)
    monkeypatch.setattr(grasper._sensor, "sum_active_finger_normal_force", lambda: 4.0)
    grasper._sensor._latest_tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    grasper._sensor._latest_joint_feedback = []
    monkeypatch.setattr(grasper, "_should_auto_release", lambda: False)

    assert grasper.grasp_core() is True
    assert grasper.state == GraspState.ADAPTIVE_HOLD

    time.sleep(0.1)
    # Provide joint feedback matching open pose so release settles successfully
    open_pose = grasper._joint_builder.open_pose()
    grasper._sensor._latest_joint_feedback = [
        Joint(id=joint_id, angle=angle) for joint_id, angle in open_pose.items()
    ]
    grasper.release()
    assert grasper.state in (GraspState.COMPLETED, GraspState.RELEASE)


def test_perform_release_waits_for_control_thread(monkeypatch):
    """wait_control_thread=True should join the alive control thread."""
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    g.state = GraspState.ADAPTIVE_HOLD
    # Provide joint feedback matching open pose so _wait_joints_settled succeeds
    open_pose = g._joint_builder.open_pose()
    g._sensor._latest_joint_feedback = [
        Joint(id=joint_id, angle=angle) for joint_id, angle in open_pose.items()
    ]

    joined = [False]
    def fake_loop():
        while not joined[0]:
            time.sleep(0.001)

    t = threading.Thread(target=fake_loop, daemon=True)
    t.start()
    g._control_thread = t

    original_join = t.join
    def tracking_join(timeout=None):
        joined[0] = True
        original_join(timeout=timeout)
    monkeypatch.setattr(t, "join", tracking_join)
    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)

    g._perform_release(wait_control_thread=True)
    assert joined[0] is True
    assert g.state == GraspState.COMPLETED
    assert g._running is False


def test_perform_release_from_control_thread_does_not_deadlock(monkeypatch):
    """wait_control_thread=False should skip join when called inside the control thread."""
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    g.state = GraspState.ADAPTIVE_HOLD
    g._control_thread = threading.current_thread()
    # Provide joint feedback matching open pose so _wait_joints_settled succeeds
    open_pose = g._joint_builder.open_pose()
    g._sensor._latest_joint_feedback = [
        Joint(id=joint_id, angle=angle) for joint_id, angle in open_pose.items()
    ]

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)

    result = g._perform_release(wait_control_thread=False)
    assert result is True
    assert g.state == GraspState.COMPLETED
    assert g._running is False


def test_sensor_subscription_callback_updates_cache():
    """订阅回调应正确解析 Tpdo 并更新触觉/关节缓存。"""
    from types import SimpleNamespace

    hand = _MockHand()
    cfg = AdaptiveGraspConfig(control_period_s=0.02, pre_grasp_preset="two_finger_pinch")
    grasper = AdaptiveGrasper(hand, cfg)

    now = {"v": 1.0}
    grasper._get_monotonic_time = lambda: now["v"]
    grasper._sensor._get_monotonic_time = lambda: now["v"]

    def make_tactile(fz: float):
        return SimpleNamespace(resultant_force=[0.0, 0.0, fz], sample_force=[0.0] * 16)

    def make_joint(angle: float):
        return SimpleNamespace(angle=angle, speed=0, torque=0, state=0, error=0)

    tpdo = SimpleNamespace(
        tactile_state=SimpleNamespace(state=0b11111),
        thumb_tactile=make_tactile(0.2),
        ff_tactile=make_tactile(0.3),
        mf_tactile=make_tactile(0.5),
        rf_tactile=make_tactile(0.7),
        lf_tactile=make_tactile(0.9),
        th_dip=make_joint(0.1),
        th_pip=make_joint(0.2),
        th_mcp=make_joint(0.3),
        th_swing=make_joint(0.4),
        th_rot=make_joint(0.5),
        ff_dip=make_joint(0.6),
        ff_pip=make_joint(0.7),
        ff_mcp=make_joint(0.8),
        ff_swing=make_joint(0.9),
        mf_dip=make_joint(1.0),
        mf_pip=make_joint(1.1),
        mf_mcp=make_joint(1.2),
        rf_dip=make_joint(1.3),
        rf_pip=make_joint(1.4),
        rf_mcp=make_joint(1.5),
        lf_dip=make_joint(1.6),
        lf_pip=make_joint(1.7),
        lf_mcp=make_joint(1.8),
    )

    grasper._sensor._on_data(tpdo)

    assert grasper._sensor._latest_tactile_data is not None
    assert TactileSensorId.THUMB in grasper._sensor._latest_tactile_data
    assert TactileSensorId.FOREFINGER in grasper._sensor._latest_tactile_data
    assert TactileSensorId.MIDDLE_FINGER not in grasper._sensor._latest_tactile_data
    assert grasper._sensor._latest_tactile_data[TactileSensorId.THUMB].get_force_z() == pytest.approx(0.2)
    assert grasper._sensor._latest_tactile_data[TactileSensorId.FOREFINGER].get_force_z() == pytest.approx(0.3)
    assert grasper._sensor._last_sample_time_s == 1.0

    assert grasper._sensor._latest_joint_feedback is not None
    joint_map = {j.id: j for j in grasper._sensor._latest_joint_feedback}
    assert JointId.THUMB_PIP in joint_map
    assert joint_map[JointId.THUMB_PIP].angle == pytest.approx(0.2)
    assert JointId.LF_MCP in joint_map
    assert joint_map[JointId.LF_MCP].angle == pytest.approx(1.8)

    tpdo.thumb_tactile = make_tactile(1.0)
    now["v"] = 2.0
    grasper._sensor._on_data(tpdo)
    assert grasper._sensor._latest_tactile_data[TactileSensorId.THUMB].get_force_z() == pytest.approx(1.0)
    assert grasper._sensor._last_sample_time_s == 2.0


def test_controller_accepts_none_config():
    """AdaptiveGrasper(config=None) should not crash。"""
    hand = _MockHand()
    grasper = AdaptiveGrasper(hand, config=None)
    assert grasper.config is not None
    assert grasper._sensor is not None


def test_full_grasp_lifecycle(monkeypatch):
    """Integration test: IDLE -> OPEN -> PRE_GRASP -> CLOSING -> ADAPTIVE_HOLD -> RELEASE -> COMPLETED。"""
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        contact_threshold_z=0.5,
        release_hold_time_s=0.05,
        control_period_s=0.01,
        release_timeout_s=0.2,
        release_check_cycles=2,
        theta_err_th=math.radians(2.0),
    )
    grasper = AdaptiveGrasper(hand, cfg)

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)
    monkeypatch.setattr("xiaoyao.adaptive_grasp.phase_controller.time.sleep", lambda *_: None)
    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)
    monkeypatch.setattr(grasper._sensor, "reset", lambda: None)
    monkeypatch.setattr(grasper._sensor, "sum_active_finger_normal_force", lambda: 4.0)

    # Provide tactile and joint feedback for the closing phase and adaptive hold
    grasper._sensor._latest_tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    grasper._sensor._latest_joint_feedback = []
    monkeypatch.setattr(grasper, "_should_auto_release", lambda: False)

    assert grasper.state == GraspState.IDLE

    ok = grasper.grasp_core()
    assert ok is True
    assert grasper.state == GraspState.ADAPTIVE_HOLD
    assert grasper._running is True
    assert grasper._control_thread is not None
    assert grasper._control_thread.is_alive()

    # Let the adaptive hold loop run briefly
    time.sleep(0.05)

    # Provide joint feedback matching open pose so release settles successfully
    open_pose = grasper._joint_builder.open_pose()
    grasper._sensor._latest_joint_feedback = [
        Joint(id=joint_id, angle=angle) for joint_id, angle in open_pose.items()
    ]

    # Release and verify it reaches COMPLETED
    ok_release = grasper.release()
    assert ok_release is True
    assert grasper.state == GraspState.COMPLETED
    assert grasper._running is False

    # Verify hand received the expected phases:
    # OPEN, PRE_GRASP, CLOSING (multiple torque commands), RELEASE
    modes = [call["mode"] for call in hand.calls]
    assert modes[0] == CtrlMode.POSITION  # OPEN
    assert modes[1] == CtrlMode.POSITION  # PRE_GRASP
    assert CtrlMode.TORQUE in modes[2:-1]  # CLOSING phase uses TORQUE
    assert modes[-1] == CtrlMode.POSITION  # RELEASE
