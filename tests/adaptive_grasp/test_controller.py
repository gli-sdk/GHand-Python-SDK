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


def test_adaptive_hold_sends_position_payload_with_config_limits(monkeypatch):
    hand = _MockHand()
    config = AdaptiveGraspConfig(
        position_speed_limit=17,
        position_torque_limit=29,
        torque_adjust_step=8,
        variance_threshold=0.1,
        max_normal_force_per_finger=1.0,
    )
    grasper = AdaptiveGrasper(hand, config)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper.current_torque = 10
    grasper._force_planner = ForcePlanner(config, None)
    # 通过缓存提供传感器数据（模拟 subscribe 回调已更新）
    grasper._sensor._latest_tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.2, 0.2, 0.2),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.1, 0.1, 0.2),
    }
    grasper._sensor._last_sample_time_s = 0.0
    grasper._sensor._latest_joint_feedback = []

    monkeypatch.setattr(
        grasper._tactile,
        "update",
        lambda _data: TactileAnalysis(
            variance=0.5,
            slip_risk=1.0,
            direction_distance=0.0,
            friction_utilization=0.0,
            slip_confirmed=True,
            finger_fz={TactileSensorId.THUMB: 0.2, TactileSensorId.FOREFINGER: 0.2},
            total_fz=0.4,
        ),
    )

    assert grasper._run_control_step() is True
    assert len(hand.calls) == 1
    call = hand.calls[0]
    assert call["mode"] == CtrlMode.POSITION
    assert call["joints"]
    for joint in call["joints"]:
        assert joint.speed == config.position_speed_limit
        assert 0 <= joint.torque <= config.position_torque_limit


def test_clip_clamps_and_handles_inverted_bounds():
    from xiaoyao.adaptive_grasp.utils import clip

    assert clip(5.0, 0.0, 10.0) == pytest.approx(5.0)
    assert clip(-1.0, 0.0, 10.0) == pytest.approx(0.0)
    assert clip(11.0, 0.0, 10.0) == pytest.approx(10.0)
    assert clip(3.0, 2.0, 1.0) == pytest.approx(2.0)


def test_controller_delegates_to_submodules(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        variance_threshold=0.1,
        max_normal_force_per_finger=1.0,
        enable_fault_release_fallback=False,
    )
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper.current_torque = 10
    grasper._force_planner = ForcePlanner(cfg, None)
    grasper._sensor._latest_tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.2, 0.2, 0.2),
    }
    grasper._sensor._latest_joint_feedback = []

    monkeypatch.setattr(
        grasper._safety,
        "check",
        lambda *args, **kwargs: SafetyReport(SafetyStatus.FAULT),
    )

    assert grasper._run_control_step() is False
    assert grasper.state == GraspState.ERROR
    assert grasper._running is False


def test_adaptive_hold_auto_release_uses_release_payload():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        release_hold_time_s=0.5,
        release_open_speed=13,
        release_open_torque=31,
    )
    g = AdaptiveGrasper(hand, cfg)
    g.state = GraspState.ADAPTIVE_HOLD
    g._running = True
    g._control_thread = threading.current_thread()
    g._adaptive_hold_started_at = 10.0
    g._get_monotonic_time = lambda: 10.5
    g._sensor._latest_joint_feedback = []

    assert g._run_control_step() is True
    assert g.state == GraspState.COMPLETED
    assert g._running is False
    assert len(hand.calls) == 1
    call = hand.calls[0]
    assert call["mode"] == CtrlMode.POSITION
    assert call["joints"]
    for joint in call["joints"]:
        assert joint.speed == cfg.release_open_speed
        assert joint.torque == cfg.release_open_torque


class _ContactHand(_MockHand):
    pass


def test_release_waits_until_joints_settled(monkeypatch):
    cfg = AdaptiveGraspConfig(
        release_timeout_s=0.2,
        release_check_cycles=2,
        theta_err_th=math.radians(2.0),
    )
    target = AdaptiveGrasper(_MockHand(), cfg)._get_open_pose()
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
    monkeypatch.setattr(
        g, "_safe_get_joints", lambda: next(feedback_sequence, g._sensor._latest_joint_feedback)
    )
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
    target = AdaptiveGrasper(_MockHand(), cfg)._get_open_pose()
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
    monkeypatch.setattr(
        g, "_safe_get_joints", lambda: next(feedback_sequence, g._sensor._latest_joint_feedback)
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)
    t = {"v": 0.0}
    g._get_monotonic_time = lambda: (t.__setitem__("v", t["v"] + 0.01) or t["v"])

    assert g.release() is False
    assert g.state == GraspState.ERROR


def test_full_grasp_state_transitions(monkeypatch):
    hand = _ContactHand()
    cfg = AdaptiveGraspConfig(
        release_hold_time_s=0.05,
        control_period_s=0.01,
    )
    grasper = AdaptiveGrasper(hand, cfg)

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)
    monkeypatch.setattr(grasper, "_calibrate_force", lambda *args, **kwargs: None)
    monkeypatch.setattr(grasper, "_should_auto_release", lambda: False)
    # 避免 grasp_core 内部调用 _start_sensor_subscription / _reset_runtime_state 清空缓存
    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)
    monkeypatch.setattr(grasper._sensor, "sum_active_finger_normal_force", lambda: 4.0)
    monkeypatch.setattr(
        grasper,
        "_safe_get_tactile_data",
        lambda: {
            TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
            TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
        },
    )
    monkeypatch.setattr(grasper, "_safe_get_joints", lambda: [])

    assert grasper.grasp_core() is True
    assert grasper.state == GraspState.ADAPTIVE_HOLD

    time.sleep(0.1)
    grasper.release()
    assert grasper.state in (GraspState.COMPLETED, GraspState.RELEASE)


def test_perform_release_waits_for_control_thread(monkeypatch):
    """wait_control_thread=True should join the alive control thread."""
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    g.state = GraspState.ADAPTIVE_HOLD
    g._sensor._latest_joint_feedback = []

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
    g._sensor._latest_joint_feedback = []

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)

    result = g._perform_release(wait_control_thread=False)
    assert result is True
    assert g.state == GraspState.COMPLETED
    assert g._running is False


def test_controller_runs_full_state_machine_with_submodules(monkeypatch):
    """Smoke test: controller should use submodules and reach ADAPTIVE_HOLD."""
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        contact_threshold_z=0.1,
        release_hold_time_s=0.1,
        control_period_s=0.001,
    )
    profile = ObjectProfile(
        name="test_obj", weight_kg=0.1, material="plastic",
        safe_force_min=0.5, safe_force_max=5.0,
        friction_coeff=0.4, is_fragile=False,
    )
    grasper = AdaptiveGrasper(hand, cfg)

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)
    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.monotonic", lambda: 0.0)
    # 避免 grasp_core 内部调用 _start_sensor_subscription / _reset_runtime_state 清空缓存
    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)
    monkeypatch.setattr(grasper._sensor, "sum_active_finger_normal_force", lambda: 4.0)
    monkeypatch.setattr(
        grasper,
        "_safe_get_tactile_data",
        lambda: {
            TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
            TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
        },
    )
    monkeypatch.setattr(grasper, "_safe_get_joints", lambda: [])

    call_count = [0]
    def fake_should_release():
        call_count[0] += 1
        return call_count[0] > 2
    monkeypatch.setattr(grasper, "_should_auto_release", fake_should_release)

    ok = grasper.grasp_core(object_profile=profile)
    assert ok is True
    assert grasper.state in (GraspState.ADAPTIVE_HOLD, GraspState.COMPLETED, GraspState.RELEASE)


def test_closing_ignores_inactive_finger_noise(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        contact_threshold_z=1.0,
        phase_timeout=0.1,
        control_period_s=0.001,
    )
    grasper = AdaptiveGrasper(hand, cfg)
    grasper._running = True
    grasper._force_planner = ForcePlanner(cfg, None)

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)
    monkeypatch.setattr(grasper, "_calibrate_force", lambda *args, **kwargs: None)
    now = {"v": 1.0}
    def monotonic_step():
        now["v"] += 0.001
        return now["v"]
    grasper._get_monotonic_time = monotonic_step

    reads = iter([
        {
            TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 0.0),
            TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 0.0),
            TactileSensorId.MIDDLE_FINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
        },
        {
            TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
            TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
            TactileSensorId.MIDDLE_FINGER: _FakeTactileInfo(0.0, 0.0, 0.0),
        },
    ])
    def mock_get_tactile():
        data = next(reads)
        grasper._sensor._latest_tactile_data = data
        return data
    monkeypatch.setattr(grasper, "_safe_get_tactile_data", mock_get_tactile)
    monkeypatch.setattr(grasper, "_safe_get_joints", lambda: [])

    assert grasper._phase_closing() is True


def test_calibrate_force_ignores_inactive_finger_noise(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        torque_adjust_step=5,
        base_holding_force=6.0,
    )
    grasper = AdaptiveGrasper(hand, cfg)
    grasper._force_planner = ForcePlanner(cfg, None)
    grasper.current_torque = 10

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)

    tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 1.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 1.0),
        TactileSensorId.MIDDLE_FINGER: _FakeTactileInfo(0.0, 0.0, 8.0),
    }
    grasper._sensor._latest_tactile_data = tactile_data
    grasper._calibrate_force()

    assert grasper.current_torque > 10


def test_control_step_updates_tactile_data_age(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(control_period_s=0.02)
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper._running = True

    times = iter([1.0, 1.02])
    grasper._get_monotonic_time = lambda: next(times)
    grasper._sensor._latest_tactile_data = {TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 0.0)}
    grasper._sensor._last_sample_time_s = 1.005
    grasper._sensor._latest_joint_feedback = []
    monkeypatch.setattr(
        grasper._safety,
        "check",
        lambda *args, **kwargs: SafetyReport(SafetyStatus.OK),
    )
    monkeypatch.setattr(
        grasper._tactile,
        "update",
        lambda _data: TactileAnalysis(
            variance=0.0,
            slip_risk=0.0,
            direction_distance=0.0,
            friction_utilization=0.0,
            slip_confirmed=False,
            finger_fz={},
            total_fz=0.0,
        ),
    )

    assert grasper._run_control_step() is True
    assert grasper.last_tactile_data_age_s == pytest.approx(0.015, abs=1e-6)


def test_control_step_updates_cycle_jitter(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(control_period_s=0.02)
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper._running = True
    grasper._adaptive_hold_started_at = None

    times = iter([1.0, 1.031])
    grasper._get_monotonic_time = lambda: next(times)
    monkeypatch.setattr(grasper, "_safe_get_tactile_data", lambda: None)
    monkeypatch.setattr(grasper, "_safe_get_joints", lambda: [])
    monkeypatch.setattr(
        grasper._safety,
        "check",
        lambda *args, **kwargs: SafetyReport(SafetyStatus.OK),
    )

    assert grasper._run_control_step() is True
    assert grasper.last_control_cycle_s is None
    assert grasper._run_control_step() is True
    assert grasper.last_control_cycle_s == pytest.approx(0.031, abs=1e-6)
    assert grasper.last_control_cycle_jitter_s == pytest.approx(0.011, abs=1e-6)


def test_control_step_uses_cached_tactile_snapshot(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(control_period_s=0.02)
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper._running = True
    grasper._force_planner = ForcePlanner(cfg, None)

    def fail_direct_read():
        raise AssertionError("control step should read cached tactile data")

    hand.get_tactile_data = fail_direct_read
    grasper._sensor._latest_tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 0.2),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 0.2),
    }
    grasper._sensor._last_sample_time_s = 1.0
    grasper._sensor._latest_joint_feedback = []

    times = iter([1.02, 1.03])
    grasper._get_monotonic_time = lambda: next(times)
    monkeypatch.setattr(
        grasper._safety,
        "check",
        lambda *args, **kwargs: SafetyReport(SafetyStatus.OK),
    )
    monkeypatch.setattr(
        grasper._tactile,
        "update",
        lambda _data: TactileAnalysis(
            variance=0.0,
            slip_risk=0.0,
            direction_distance=0.0,
            friction_utilization=0.0,
            slip_confirmed=False,
            finger_fz={TactileSensorId.THUMB: 0.2, TactileSensorId.FOREFINGER: 0.2},
            total_fz=0.4,
        ),
    )

    assert grasper._run_control_step() is True
    assert len(hand.calls) == 1
    assert grasper.last_tactile_data_age_s == pytest.approx(0.03, abs=1e-6)


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


def test_build_torque_joints_sets_inactive_to_zero():
    """不活动的关节必须显式下发 angle=0, speed=0, torque=0。"""
    cfg = AdaptiveGraspConfig(pre_grasp_preset="two_finger_pinch")
    grasper = AdaptiveGrasper(_MockHand(), cfg)

    joints = grasper._build_torque_joints(torque=42)
    joint_map = {j.id: j for j in joints}

    active_joints = set(grasper._torque_joints)
    for joint_id in AdaptiveGrasper._TORQUE_JOINTS:
        j = joint_map[joint_id]
        if joint_id in active_joints:
            assert j.torque == 42
            assert j.angle == 0.0
            assert j.speed == 0
        else:
            assert j.torque == 0
            assert j.angle == 0.0
            assert j.speed == 0
    assert joints[-2].id == JointId.THUMB_ROTATION
    assert joints[-1].id == JointId.THUMB_SWING
    assert joints[-2].torque == 5
    assert joints[-1].torque == 5


def test_controller_accepts_none_config():
    """AdaptiveGrasper(config=None) should not crash."""
    hand = _MockHand()
    grasper = AdaptiveGrasper(hand, config=None)
    assert grasper.config is not None
    assert grasper._sensor is not None


def test_build_torque_joints_all_active_for_five_finger():
    """五指握时所有 _TORQUE_JOINTS 都应带有目标力矩。"""
    cfg = AdaptiveGraspConfig(pre_grasp_preset="five_finger_grasp")
    grasper = AdaptiveGrasper(_MockHand(), cfg)

    joints = grasper._build_torque_joints(torque=77)
    joint_map = {j.id: j for j in joints}

    for joint_id in AdaptiveGrasper._TORQUE_JOINTS:
        assert joint_map[joint_id].torque == 77
        assert joint_map[joint_id].angle == 0.0
        assert joint_map[joint_id].speed == 0
