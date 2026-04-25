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


class _PositionTraceHand:
    def __init__(self):
        self.calls: list[dict] = []

    def move_joints(self, joints, mode=None):  # noqa: ANN001
        self.calls.append({"mode": mode, "joints": list(joints)})
        return True

    def get_tactile_data(self):
        return {
            TactileSensorId.THUMB: _FakeTactileInfo(0.2, 0.2, 0.2),
            TactileSensorId.FOREFINGER: _FakeTactileInfo(0.1, 0.1, 0.2),
        }

    def stop(self):
        return None

    def get_joints(self):
        return []


def _joint_map(call):
    return {joint.id: joint for joint in call["joints"]}


def test_adaptive_hold_sends_position_payload_with_config_limits(monkeypatch):
    hand = _PositionTraceHand()
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
    # Ensure force planner exists so _run_control_step can delegate
    grasper._force_planner = ForcePlanner(config, None)
    grasper._store_tactile_snapshot(hand.get_tactile_data(), sample_time_s=0.0)

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
    hand = _PositionTraceHand()
    cfg = AdaptiveGraspConfig(
        variance_threshold=0.1,
        max_normal_force_per_finger=1.0,
        enable_fault_release_fallback=False,
    )
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper.current_torque = 10
    grasper._force_planner = ForcePlanner(cfg, None)

    monkeypatch.setattr(
        grasper._safety,
        "check",
        lambda *args, **kwargs: SafetyReport(SafetyStatus.FAULT),
    )

    assert grasper._run_control_step() is False
    assert grasper.state == GraspState.ERROR
    assert grasper._running is False


def test_adaptive_hold_auto_release_uses_release_payload():
    hand = _PositionTraceHand()
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


class _ContactHand(_PositionTraceHand):
    def get_tactile_data(self):
        return {
            TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
            TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
        }


class _ReleaseFeedbackHand(_PositionTraceHand):
    def __init__(self, feedback_angles: list[dict[JointId, float]]):
        super().__init__()
        self._feedback_angles = list(feedback_angles)
        self._idx = 0

    def get_joints(self):
        if self._idx < len(self._feedback_angles):
            angles = self._feedback_angles[self._idx]
            self._idx += 1
        else:
            angles = self._feedback_angles[-1]
        return [Joint(id=joint_id, angle=angle) for joint_id, angle in angles.items()]


class _NoisyInactiveFingerHand(_PositionTraceHand):
    def __init__(self):
        super().__init__()
        self._tactile_reads = 0

    def get_tactile_data(self):
        self._tactile_reads += 1
        if self._tactile_reads == 1:
            return {
                TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 0.0),
                TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 0.0),
                TactileSensorId.MIDDLE_FINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
            }
        return {
            TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
            TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
            TactileSensorId.MIDDLE_FINGER: _FakeTactileInfo(0.0, 0.0, 0.0),
        }


class _CalibrationNoiseHand(_PositionTraceHand):
    def __init__(self):
        super().__init__()
        self._tactile_reads = 0

    def get_tactile_data(self):
        self._tactile_reads += 1
        if self._tactile_reads == 1:
            return {
                TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 1.0),
                TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 1.0),
                TactileSensorId.MIDDLE_FINGER: _FakeTactileInfo(0.0, 0.0, 8.0),
            }
        return {
            TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 1.0),
            TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 1.0),
            TactileSensorId.MIDDLE_FINGER: _FakeTactileInfo(0.0, 0.0, 8.0),
        }


def test_release_waits_until_joints_settled(monkeypatch):
    cfg = AdaptiveGraspConfig(
        release_timeout_s=0.2,
        release_check_cycles=2,
        theta_err_th=math.radians(2.0),
    )
    target = AdaptiveGrasper(_PositionTraceHand(), cfg)._get_open_pose()
    hand = _ReleaseFeedbackHand([target, target, target])
    g = AdaptiveGrasper(hand, cfg)
    g._running = True
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
    target = AdaptiveGrasper(_PositionTraceHand(), cfg)._get_open_pose()
    far = {joint_id: angle + math.radians(10.0) for joint_id, angle in target.items()}
    hand = _ReleaseFeedbackHand([far, far, far, far])
    g = AdaptiveGrasper(hand, cfg)
    g._running = True
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
    # 跳过力校准，直接返回成功（本测试仅验证状态流转，不验证力校准细节）
    monkeypatch.setattr(grasper, "_calibrate_force", lambda *args, **kwargs: None)
    monkeypatch.setattr(grasper, "_should_auto_release", lambda: False)

    assert grasper.grasp_core() is True
    assert grasper.state == GraspState.ADAPTIVE_HOLD

    time.sleep(0.1)
    grasper.release()
    assert grasper.state in (GraspState.COMPLETED, GraspState.RELEASE)


def test_perform_release_waits_for_control_thread(monkeypatch):
    """wait_control_thread=True should join the alive control thread."""
    hand = _PositionTraceHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    g.state = GraspState.ADAPTIVE_HOLD

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
    hand = _PositionTraceHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    g.state = GraspState.ADAPTIVE_HOLD
    g._control_thread = threading.current_thread()

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)

    # Must return immediately without attempting to join itself
    result = g._perform_release(wait_control_thread=False)
    assert result is True
    assert g.state == GraspState.COMPLETED
    assert g._running is False


def test_controller_runs_full_state_machine_with_submodules(monkeypatch):
    """Smoke test: controller should use submodules and reach ADAPTIVE_HOLD."""
    hand = _PositionTraceHand()
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

    call_count = [0]
    def fake_should_release():
        call_count[0] += 1
        return call_count[0] > 2
    monkeypatch.setattr(grasper, "_should_auto_release", fake_should_release)

    ok = grasper.grasp_core(object_profile=profile)
    assert ok is True
    assert grasper.state in (GraspState.ADAPTIVE_HOLD, GraspState.COMPLETED, GraspState.RELEASE)


def test_closing_ignores_inactive_finger_noise(monkeypatch):
    hand = _NoisyInactiveFingerHand()
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
    grasper._start_tactile_capture()

    assert grasper._phase_closing() is True
    grasper._stop_tactile_capture()
    assert hand._tactile_reads >= 2


def test_calibrate_force_ignores_inactive_finger_noise(monkeypatch):
    hand = _CalibrationNoiseHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        torque_adjust_step=5,
        base_holding_force=6.0,
    )
    grasper = AdaptiveGrasper(hand, cfg)
    grasper._force_planner = ForcePlanner(cfg, None)
    grasper.current_torque = 10

    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)

    tactile_data = hand.get_tactile_data()
    grasper._calibrate_force(tactile_data)

    assert grasper.current_torque > 10


def test_control_step_updates_tactile_data_age(monkeypatch):
    hand = _PositionTraceHand()
    cfg = AdaptiveGraspConfig(control_period_s=0.02)
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper._running = True

    times = iter([1.0, 1.02])
    grasper._get_monotonic_time = lambda: next(times)
    grasper._store_tactile_snapshot(
        {TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 0.0)},
        sample_time_s=1.005,
    )
    monkeypatch.setattr(grasper, "_safe_get_joints", lambda: [])
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
    hand = _PositionTraceHand()
    cfg = AdaptiveGraspConfig(control_period_s=0.02)
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper._running = True
    grasper._adaptive_hold_started_at = None

    times = iter([1.0, 1.031])
    grasper._get_monotonic_time = lambda: next(times)
    monkeypatch.setattr(grasper, "_safe_get_tactile_data", lambda: None)
    monkeypatch.setattr(grasper, "_safe_get_joints", lambda: None)
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
    hand = _PositionTraceHand()
    cfg = AdaptiveGraspConfig(control_period_s=0.02)
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper._running = True
    grasper._force_planner = ForcePlanner(cfg, None)

    def fail_direct_read():
        raise AssertionError("control step should read cached tactile data")

    hand.get_tactile_data = fail_direct_read
    grasper._store_tactile_snapshot(
        {
            TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 0.2),
            TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 0.2),
        },
        sample_time_s=1.0,
    )

    times = iter([1.02, 1.03])
    grasper._get_monotonic_time = lambda: next(times)
    monkeypatch.setattr(grasper, "_safe_get_joints", lambda: [])
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


def test_tactile_capture_polls_without_thread():
    hand = _PositionTraceHand()
    cfg = AdaptiveGraspConfig(control_period_s=0.02)
    grasper = AdaptiveGrasper(hand, cfg)

    now = {"v": 1.0}
    grasper._get_monotonic_time = lambda: now["v"]

    grasper._start_tactile_capture()
    assert not hasattr(grasper, "_tactile_thread")
    assert grasper._get_tactile_snapshot() is not None

    hand.get_tactile_data = lambda: {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 1.0),
    }
    now["v"] = 1.01
    grasper._poll_tactile_if_due()
    assert grasper._get_tactile_snapshot()[TactileSensorId.THUMB].get_force_z() == pytest.approx(0.2)

    now["v"] = 1.02
    grasper._poll_tactile_if_due()
    assert grasper._get_tactile_snapshot()[TactileSensorId.THUMB].get_force_z() == pytest.approx(1.0)


def test_build_torque_joints_sets_inactive_to_zero():
    """不活动的关节必须显式下发 angle=0, speed=0, torque=0。"""
    cfg = AdaptiveGraspConfig(pre_grasp_preset="two_finger_pinch")
    grasper = AdaptiveGrasper(_PositionTraceHand(), cfg)

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


def test_build_torque_joints_all_active_for_five_finger():
    """五指握时所有 _TORQUE_JOINTS 都应带有目标力矩。"""
    cfg = AdaptiveGraspConfig(pre_grasp_preset="five_finger_grasp")
    grasper = AdaptiveGrasper(_PositionTraceHand(), cfg)

    joints = grasper._build_torque_joints(torque=77)
    joint_map = {j.id: j for j in joints}

    
    for joint_id in AdaptiveGrasper._TORQUE_JOINTS:
        assert joint_map[joint_id].torque == 77
        assert joint_map[joint_id].angle == 0.0
        assert joint_map[joint_id].speed == 0
