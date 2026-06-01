import math
import threading
import time
from typing import Callable
from types import SimpleNamespace

import pytest

from adaptive_grasp import AdaptiveGraspConfig, AdaptiveGrasper, GraspState
from adaptive_grasp.adaptive_hold_runner import AdaptiveHoldRunner
from adaptive_grasp.adaptive_hold_loop import HoldResult, HoldStepResult
from adaptive_grasp.force_reference_planner import ForceReferencePlanner
from adaptive_grasp.position_hold_planner import PositionHoldPlanner
from adaptive_grasp.torque_hold_planner import TorqueHoldPlanner
from adaptive_grasp.object_profile import ObjectProfile
from adaptive_grasp.grasp_sequence import ContactSnapshot
from adaptive_grasp.safety import SafetyReport, SafetyStatus
from adaptive_grasp.tactility import TactileAnalysis
from adaptive_grasp.joint_builder import JointCommandBuilder
from adaptive_grasp.sensor import SensorClient
from adaptive_grasp.utils import tactile_force_xyz
from ghand import CtrlMode, JointCommand, JointId, TactileSensorId


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
    is_ghand = True
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

    def get_hand_info(self):
        return SimpleNamespace(state=0, error=0)


class _FakeSubscriptionManager:
    def __init__(self):
        self.calls: list[dict[str, float]] = []

    def configure_periods(self, *, recv_period_s: float, dispatch_period_s: float) -> None:
        self.calls.append(
            {
                "recv_period_s": recv_period_s,
                "dispatch_period_s": dispatch_period_s,
            }
        )


class _MockHandWithSubscriptionManager(_MockHand):
    def __init__(self):
        super().__init__()
        self._sub_manager = _FakeSubscriptionManager()


def _joint_map(call):
    return {joint.id: joint for joint in call["joints"]}


def test_clip_clamps_and_handles_inverted_bounds():
    from adaptive_grasp.utils import clip

    assert clip(5.0, 0.0, 10.0) == pytest.approx(5.0)
    assert clip(-1.0, 0.0, 10.0) == pytest.approx(0.0)
    assert clip(11.0, 0.0, 10.0) == pytest.approx(10.0)
    assert clip(3.0, 2.0, 1.0) == pytest.approx(2.0)


def test_adaptive_grasper_runtime_public_proxies():
    hand = _MockHand()
    grasper = AdaptiveGrasper(hand, AdaptiveGraspConfig())

    assert grasper.hand is hand
    assert grasper._runtime is not None

    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper._running = True
    grasper.current_torque = 17

    assert grasper._runtime.state == GraspState.ADAPTIVE_HOLD
    assert grasper.get_state() == GraspState.ADAPTIVE_HOLD
    assert grasper._runtime.running is True
    assert grasper._runtime.current_torque == 17


def test_telemetry_properties_are_runtime_backed():
    grasper = AdaptiveGrasper(_MockHand(), AdaptiveGraspConfig())
    contact_snapshot = object()
    tactile_analysis = object()
    safety_report = object()
    force_decisions = object()
    torque_decision = object()

    grasper._runtime.last_contact_snapshot = contact_snapshot
    grasper._runtime.last_tactile_analysis = tactile_analysis
    grasper._runtime.last_safety_report = safety_report
    grasper._runtime.last_force_decisions = force_decisions
    grasper._runtime.last_torque_hold_decision = torque_decision
    grasper._runtime.last_tactile_data_age_s = 0.25
    grasper._runtime.last_control_cycle_s = 0.03
    grasper._runtime.last_control_cycle_jitter_s = 0.01

    assert grasper.last_contact_snapshot is contact_snapshot
    assert grasper.last_tactile_analysis is tactile_analysis
    assert grasper.last_safety_report is safety_report
    assert grasper.last_force_decisions is force_decisions
    assert grasper.last_torque_hold_decision is torque_decision
    assert grasper.last_tactile_data_age_s == pytest.approx(0.25)
    assert grasper.last_control_cycle_s == pytest.approx(0.03)
    assert grasper.last_control_cycle_jitter_s == pytest.approx(0.01)


def test_adaptive_grasper_does_not_expose_migrated_runtime_wrappers():
    grasper = AdaptiveGrasper(_MockHand(), AdaptiveGraspConfig())

    migrated_names = (
        "_contact_joint_angles",
        "_update_control_cycle_timing",
        "_record_hold_step",
        "_handle_hold_result",
        "_should_auto_release",
        "_reset_runtime_state",
        "_object_profile",
        "_adaptive_hold_started_at",
        "_last_tactile_analysis",
        "_last_safety_report",
        "_last_force_decisions",
        "_last_torque_hold_decision",
        "_last_tactile_data_age_s",
        "_last_control_step_start_s",
        "_last_control_cycle_s",
        "_last_control_cycle_jitter_s",
        "_last_contact_snapshot",
    )

    for name in migrated_names:
        assert not hasattr(grasper, name)


def test_start_adaptive_control_uses_hold_runner_thread(monkeypatch):
    import adaptive_grasp.adaptive_hold_runner as runner_module

    hand = _MockHand()
    cfg = AdaptiveGraspConfig(enable_visualization=False)
    grasper = AdaptiveGrasper(hand, cfg)
    grasper._runtime.object_profile = ObjectProfile(
        name="paper_cup_test",
        weight_kg=0.01,
        safe_force_min=0.5,
        safe_force_max=3.5,
        friction_coeff=0.8,
        is_fragile=True,
        material="paper",
        position_hold_torque=5,
        position_hold_speed=5,
    )
    grasper._runtime.last_contact_snapshot = ContactSnapshot(
        joint_angles={JointId.THUMB_PIP: 0.12},
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
        torque=30,
        reason="force_threshold",
        timestamp_s=3.4,
    )

    created_threads = []

    class _FakeThread:
        def __init__(self, *, target, daemon):
            self.target = target
            self.daemon = daemon
            self.start_calls = 0
            created_threads.append(self)

        def start(self):
            self.start_calls += 1

        def is_alive(self):
            return False

    monkeypatch.setattr(runner_module.threading, "Thread", _FakeThread)

    grasper._start_adaptive_control()

    assert isinstance(grasper._hold_runner, AdaptiveHoldRunner)
    assert grasper._control_thread is created_threads[-1]
    assert created_threads[-1].target == grasper._hold_runner._run_loop
    assert created_threads[-1].start_calls == 1
    assert grasper._adaptive_hold_loop is grasper._hold_runner.hold_controller


def test_hold_runner_auto_release_uses_control_step_time(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        enable_visualization=False,
        release_hold_time_s=1.0,
    )
    grasper = AdaptiveGrasper(hand, cfg)
    grasper._runtime.running = True
    grasper._runtime.adaptive_hold_started_at = 0.0
    grasper._hold_runner.hold_controller = type(
        "_ContinueHoldLoop",
        (),
        {"run_step": lambda self, current_time: HoldStepResult(result=HoldResult.CONTINUE)},
    )()
    calls = []
    monkeypatch.setattr(
        grasper._release_controller,
        "release",
        lambda **kwargs: calls.append(kwargs) or True,
    )
    times = iter([0.5, 2.0])
    grasper._get_monotonic_time = lambda: next(times)
    grasper._hold_runner.get_monotonic_time = grasper._get_monotonic_time

    assert grasper._hold_runner.run_once() is True
    assert calls == []


def test_adaptive_control_loop_uses_latest_manager_clock(monkeypatch):
    grasper = AdaptiveGrasper(
        _MockHand(),
        AdaptiveGraspConfig(enable_visualization=False, release_hold_time_s=100.0),
    )
    grasper._running = True
    grasper._runtime.adaptive_hold_started_at = 0.0
    grasper._hold_runner.get_monotonic_time = lambda: 1.0
    grasper._get_monotonic_time = lambda: 42.0
    seen_step_times = []

    class _ErrorAfterStepHoldLoop:
        def run_step(self, current_time):
            seen_step_times.append(current_time)
            return HoldStepResult(result=HoldResult.ERROR)

    grasper._adaptive_hold_loop = _ErrorAfterStepHoldLoop()
    monkeypatch.setattr(
        grasper._sensor,
        "stop",
        lambda clear_joint_feedback=False: None,
    )

    grasper._adaptive_control_loop()

    assert seen_step_times == [42.0]


def test_perform_release_delegates_to_release_controller_with_runner_thread(monkeypatch):
    grasper = AdaptiveGrasper(_MockHand(), AdaptiveGraspConfig())

    class _RunnerThread:
        pass

    runner_thread = _RunnerThread()
    grasper._hold_runner._thread = runner_thread
    calls = []
    monkeypatch.setattr(
        grasper._release_controller,
        "release",
        lambda **kwargs: calls.append(kwargs) or True,
    )

    assert grasper._perform_release(wait_control_thread=True, release_wait_s=0.25) is True
    assert calls == [
        {
            "wait_control_thread": True,
            "release_wait_s": 0.25,
            "control_thread": runner_thread,
        }
    ]


def test_perform_release_honors_explicit_none_control_thread_override(monkeypatch):
    grasper = AdaptiveGrasper(_MockHand(), AdaptiveGraspConfig())
    grasper._hold_runner._thread = object()
    grasper._control_thread = None
    calls = []
    monkeypatch.setattr(
        grasper._release_controller,
        "release",
        lambda **kwargs: calls.append(kwargs) or True,
    )

    grasper._perform_release(wait_control_thread=True)

    assert grasper._control_thread is None
    assert calls == [
        {
            "wait_control_thread": True,
            "release_wait_s": None,
            "control_thread": None,
        }
    ]


def test_perform_release_prefers_control_thread_override(monkeypatch):
    grasper = AdaptiveGrasper(_MockHand(), AdaptiveGraspConfig())
    override_thread = object()
    grasper._control_thread = override_thread
    calls = []
    monkeypatch.setattr(
        grasper._release_controller,
        "release",
        lambda **kwargs: calls.append(kwargs) or True,
    )

    grasper._perform_release(wait_control_thread=False)

    assert calls == [
        {
            "wait_control_thread": False,
            "release_wait_s": None,
            "control_thread": override_thread,
        }
    ]


def test_release_succeeds_without_waiting_for_settle_feedback(monkeypatch):
    cfg = AdaptiveGraspConfig(
        release_timeout_s=0.2,
    )
    target = JointCommandBuilder(cfg, tuple()).open_pose()
    hand = _MockHand()
    g = AdaptiveGrasper(hand, cfg)
    g._running = True
    # 通过缓存提供关节反馈序列
    feedback_sequence = iter([
        [JointCommand(id=joint_id, angle=angle) for joint_id, angle in target.items()],
        [JointCommand(id=joint_id, angle=angle) for joint_id, angle in target.items()],
        [JointCommand(id=joint_id, angle=angle) for joint_id, angle in target.items()],
    ])
    g._sensor._latest_joint_feedback = next(feedback_sequence)

    def mock_joint_feedback(self):
        return next(feedback_sequence, self._latest_joint_feedback)

    monkeypatch.setattr(SensorClient, "joint_feedback", property(mock_joint_feedback))
    monkeypatch.setattr("adaptive_grasp.adaptive_grasp_manager.time.sleep", lambda *_: None)
    t = {"v": 0.0}
    g._get_monotonic_time = lambda: (t.__setitem__("v", t["v"] + 0.01) or t["v"])

    assert g.release() is True
    assert g.state == GraspState.COMPLETED


def test_release_does_not_check_whether_joints_are_settled(monkeypatch):
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    get_joints_called = [False]

    def fail_if_get_joints_called():
        get_joints_called[0] = True
        raise AssertionError("release should not check whether joints are settled")

    hand.get_joints = fail_if_get_joints_called
    monkeypatch.setattr("adaptive_grasp.adaptive_grasp_manager.time.sleep", lambda *_: None)

    assert g.release() is True
    assert g.state == GraspState.COMPLETED
    assert get_joints_called == [False]


def test_release_ignores_unsettled_feedback_after_open_command(monkeypatch):
    cfg = AdaptiveGraspConfig(
        release_timeout_s=0.02,
    )
    target = JointCommandBuilder(cfg, tuple()).open_pose()
    far = {joint_id: angle + math.radians(10.0) for joint_id, angle in target.items()}
    hand = _MockHand()
    g = AdaptiveGrasper(hand, cfg)
    g._running = True
    feedback_sequence = iter([
        [JointCommand(id=joint_id, angle=angle) for joint_id, angle in far.items()],
        [JointCommand(id=joint_id, angle=angle) for joint_id, angle in far.items()],
        [JointCommand(id=joint_id, angle=angle) for joint_id, angle in far.items()],
        [JointCommand(id=joint_id, angle=angle) for joint_id, angle in far.items()],
    ])
    g._sensor._latest_joint_feedback = next(feedback_sequence)

    def mock_joint_feedback(self):
        return next(feedback_sequence, self._latest_joint_feedback)

    monkeypatch.setattr(SensorClient, "joint_feedback", property(mock_joint_feedback))
    monkeypatch.setattr("adaptive_grasp.adaptive_grasp_manager.time.sleep", lambda *_: None)
    t = {"v": 0.0}
    g._get_monotonic_time = lambda: (t.__setitem__("v", t["v"] + 0.01) or t["v"])

    assert g.release() is True
    assert g.state == GraspState.COMPLETED


def test_release_does_not_require_fresh_hand_feedback_after_subscription_stops(monkeypatch):
    cfg = AdaptiveGraspConfig(
        release_timeout_s=0.2,
    )
    target = JointCommandBuilder(cfg, tuple()).open_pose()
    stale = {joint_id: angle + math.radians(15.0) for joint_id, angle in target.items()}
    hand = _MockHand()
    hand.get_joints = lambda: [
        JointCommand(id=joint_id, angle=angle)
        for joint_id, angle in target.items()
    ]
    g = AdaptiveGrasper(hand, cfg)
    g._running = True
    g._sensor._latest_joint_feedback = [
        JointCommand(id=joint_id, angle=angle)
        for joint_id, angle in stale.items()
    ]

    monkeypatch.setattr("adaptive_grasp.adaptive_grasp_manager.time.sleep", lambda *_: None)
    t = {"v": 0.0}
    g._get_monotonic_time = lambda: (t.__setitem__("v", t["v"] + 0.01) or t["v"])

    assert g.release() is True
    assert g.state == GraspState.COMPLETED


def test_full_grasp_state_transitions(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        enable_visualization=False,
        release_hold_time_s=3600.0,
        control_period_s=0.01,
    )
    grasper = AdaptiveGrasper(hand, cfg)

    monkeypatch.setattr("adaptive_grasp.adaptive_grasp_manager.time.sleep", lambda *_: None)
    monkeypatch.setattr("adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)
    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)
    monkeypatch.setattr(grasper._sensor, "reset", lambda: None)
    monkeypatch.setattr(grasper._sensor, "sum_active_finger_normal_force", lambda: 4.0)
    grasper._sensor._latest_tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FF: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    grasper._sensor._latest_joint_feedback = []

    assert grasper.grasp_core() is True
    assert grasper._grasp_sequence.hand is grasper._hand_port
    assert grasper.state == GraspState.ADAPTIVE_HOLD

    time.sleep(0.1)
    # Provide joint feedback matching open pose so release settles successfully
    open_pose = grasper._joint_builder.open_pose()
    grasper._sensor._latest_joint_feedback = [
        JointCommand(id=joint_id, angle=angle) for joint_id, angle in open_pose.items()
    ]
    grasper.release()
    assert grasper.state in (GraspState.COMPLETED, GraspState.RELEASE)


def test_perform_release_waits_for_control_thread(monkeypatch):
    """wait_control_thread=True should join the alive control thread."""
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    g.state = GraspState.ADAPTIVE_HOLD
    # Existing feedback is ignored by release; success depends on the open command.
    open_pose = g._joint_builder.open_pose()
    g._sensor._latest_joint_feedback = [
        JointCommand(id=joint_id, angle=angle) for joint_id, angle in open_pose.items()
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
    monkeypatch.setattr("adaptive_grasp.adaptive_grasp_manager.time.sleep", lambda *_: None)

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
    # Existing feedback is ignored by release; success depends on the open command.
    open_pose = g._joint_builder.open_pose()
    g._sensor._latest_joint_feedback = [
        JointCommand(id=joint_id, angle=angle) for joint_id, angle in open_pose.items()
    ]

    monkeypatch.setattr("adaptive_grasp.adaptive_grasp_manager.time.sleep", lambda *_: None)

    result = g._perform_release(wait_control_thread=False)
    assert result is True
    assert g.state == GraspState.COMPLETED
    assert g._running is False


def test_emergency_release_sends_open_command_without_waiting_for_control_thread(monkeypatch):
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    g.state = GraspState.ADAPTIVE_HOLD

    class _BlockingThread:
        def __init__(self):
            self.join_calls = 0

        def is_alive(self):
            return True

        def join(self, timeout=None):
            self.join_calls += 1
            raise AssertionError("emergency release should not wait for control thread")

    control_thread = _BlockingThread()
    g._control_thread = control_thread
    sleeps = []
    monkeypatch.setattr(
        "adaptive_grasp.adaptive_grasp_manager.time.sleep",
        lambda value: sleeps.append(value),
    )

    assert not hasattr(g, "release_fast")
    assert g.emergency_release(wait_s=0.123) is True
    assert control_thread.join_calls == 0
    assert sleeps == [0.123]
    assert hand.calls[-1]["mode"] == CtrlMode.POSITION
    assert g.state == GraspState.COMPLETED
    assert g._running is False


def test_cleanup_grasp_sets_stopped_state():
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g.state = GraspState.CLOSING_TO_CONTACT
    g._running = True

    g._cleanup_grasp(state=GraspState.STOPPED)

    assert g.state == GraspState.STOPPED
    assert g._running is False


def test_adaptive_control_loop_cleans_up_when_hold_step_errors(monkeypatch):
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    g.state = GraspState.ADAPTIVE_HOLD
    g._adaptive_hold_loop = type(
        "_ErrorHoldLoop",
        (),
        {"run_step": lambda self, current_time: HoldStepResult(result=HoldResult.ERROR)},
    )()
    stop_calls = []
    monkeypatch.setattr(g._sensor, "stop", lambda clear_joint_feedback=False: stop_calls.append(clear_joint_feedback))

    g._adaptive_control_loop()

    assert g.state == GraspState.ERROR
    assert g._running is False
    assert stop_calls == [False]


def test_adaptive_control_loop_catches_unexpected_hold_exceptions(monkeypatch):
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    g.state = GraspState.ADAPTIVE_HOLD

    class _RaisingHoldLoop:
        def run_step(self, current_time):
            raise RuntimeError("hold boom")

    g._adaptive_hold_loop = _RaisingHoldLoop()
    stop_calls = []
    monkeypatch.setattr(g._sensor, "stop", lambda clear_joint_feedback=False: stop_calls.append(clear_joint_feedback))

    g._adaptive_control_loop()

    assert g.state == GraspState.ERROR
    assert g._running is False
    assert stop_calls == [False]


def test_wait_for_visualizer_close_blocks_on_visualizer(monkeypatch):
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())

    events: list[str] = []

    class _FakeVisualizer:
        def wait_until_closed(self):
            events.append("wait")

    g._visualizer = _FakeVisualizer()
    g.wait_for_visualizer_close()
    assert events == ["wait"]


def test_release_does_not_release_original_visualizer(monkeypatch):
    hand = _MockHand()
    g = AdaptiveGrasper(hand, AdaptiveGraspConfig())
    g._running = True
    open_pose = g._joint_builder.open_pose()
    g._sensor._latest_joint_feedback = [
        JointCommand(id=joint_id, angle=angle) for joint_id, angle in open_pose.items()
    ]

    events: list[str] = []

    class _FakeVisualizer:
        def stop(self):
            events.append("stop")

        def detach_window(self):
            events.append("detach")

        def wait_until_closed(self):
            events.append("wait")

    g._visualizer = _FakeVisualizer()
    monkeypatch.setattr("adaptive_grasp.adaptive_grasp_manager.time.sleep", lambda *_: None)

    assert g.release() is True
    assert events == []


def test_adaptive_grasper_configures_subscription_periods_without_ghand_api():
    hand = _MockHandWithSubscriptionManager()
    cfg = AdaptiveGraspConfig(
        tactile_sensor_update_period_s=0.01,
        tactile_dispatch_period_s=0.015,
    )

    AdaptiveGrasper(hand, cfg)

    assert hand._sub_manager.calls == [
        {
            "recv_period_s": pytest.approx(0.01),
            "dispatch_period_s": pytest.approx(0.015),
        }
    ]


def test_adaptive_grasper_skips_subscription_period_config_when_unavailable():
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        tactile_sensor_update_period_s=0.01,
        tactile_dispatch_period_s=0.015,
    )

    AdaptiveGrasper(hand, cfg)

    assert not hasattr(hand, "_sub_manager")


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

    def make_joint(angle_deg: float):
        return SimpleNamespace(angle=angle_deg, speed=0, torque=0, state=0, error=0)

    tpdo = SimpleNamespace(
        tactile_state=SimpleNamespace(state=0b11111),
        thumb_tactile=make_tactile(0.2),
        ff_tactile=make_tactile(0.3),
        mf_tactile=make_tactile(0.5),
        rf_tactile=make_tactile(0.7),
        lf_tactile=make_tactile(0.9),
    )
    tpdo.joints = {
        JointId.THUMB_DIP: make_joint(10.0),
        JointId.THUMB_PIP: make_joint(20.0),
        JointId.THUMB_MCP: make_joint(30.0),
        JointId.THUMB_SWING: make_joint(40.0),
        JointId.THUMB_ROTATION: make_joint(50.0),
        JointId.FF_DIP: make_joint(60.0),
        JointId.FF_PIP: make_joint(70.0),
        JointId.FF_MCP: make_joint(80.0),
        JointId.FF_SWING: make_joint(90.0),
        JointId.MF_DIP: make_joint(100.0),
        JointId.MF_PIP: make_joint(110.0),
        JointId.MF_MCP: make_joint(120.0),
        JointId.RF_DIP: make_joint(130.0),
        JointId.RF_PIP: make_joint(140.0),
        JointId.RF_MCP: make_joint(150.0),
        JointId.LF_DIP: make_joint(160.0),
        JointId.LF_PIP: make_joint(170.0),
        JointId.LF_MCP: make_joint(180.0),
    }

    grasper._sensor._on_data(tpdo)

    assert grasper._sensor._latest_tactile_data is not None
    assert TactileSensorId.THUMB in grasper._sensor._latest_tactile_data
    assert TactileSensorId.FF in grasper._sensor._latest_tactile_data
    assert TactileSensorId.MF not in grasper._sensor._latest_tactile_data
    assert tactile_force_xyz(grasper._sensor._latest_tactile_data[TactileSensorId.THUMB])[2] == pytest.approx(0.2)
    assert tactile_force_xyz(grasper._sensor._latest_tactile_data[TactileSensorId.FF])[2] == pytest.approx(0.3)
    assert grasper._sensor._last_sample_time_s == 1.0

    assert grasper._sensor._latest_joint_feedback is not None
    joint_map = {j.id: j for j in grasper._sensor._latest_joint_feedback}
    assert JointId.THUMB_PIP in joint_map
    assert joint_map[JointId.THUMB_PIP].angle == pytest.approx(math.radians(20.0))
    assert JointId.LF_MCP in joint_map
    assert joint_map[JointId.LF_MCP].angle == pytest.approx(math.radians(180.0))

    tpdo.thumb_tactile = make_tactile(1.0)
    now["v"] = 2.0
    grasper._sensor._on_data(tpdo)
    assert tactile_force_xyz(grasper._sensor._latest_tactile_data[TactileSensorId.THUMB])[2] == pytest.approx(1.0)
    assert grasper._sensor._last_sample_time_s == 2.0


def test_adaptive_grasp_manager_accepts_none_config():
    """AdaptiveGrasper(config=None) should not crash。"""
    hand = _MockHand()
    grasper = AdaptiveGrasper(hand, config=None)
    assert grasper.config is not None
    assert grasper._sensor is not None


def test_adaptive_grasper_uses_injected_sensor_port():
    hand = _MockHand()
    sensor = type(
        "_InjectedSensor",
        (),
        {
            "start": lambda self: None,
            "stop": lambda self, clear_joint_feedback=False: None,
            "reset": lambda self: None,
            "tactile_data": property(lambda self: None),
            "joint_feedback": property(lambda self: None),
            "sample_time_s": property(lambda self: None),
            "data_age_s": lambda self, current_time: None,
            "sum_active_finger_normal_force": lambda self: 0.0,
            "active_finger_touch_flag": lambda self: {},
        },
    )()

    grasper = AdaptiveGrasper(hand, AdaptiveGraspConfig(), sensor=sensor)

    assert grasper._sensor is sensor
    assert grasper._hold_runner.sensor is sensor
    assert grasper._release_controller.sensor is sensor


def test_adaptive_grasper_passes_finger_touch_threshold_to_sensor():
    cfg = AdaptiveGraspConfig(finger_touch_threshold_n=0.25)
    grasper = AdaptiveGrasper(_MockHand(), cfg)

    assert grasper._sensor._finger_touch_threshold_n == pytest.approx(0.25)


def test_adaptive_grasper_constructor_does_not_zero_tactile():
    class HandThatRejectsTactileZero(_MockHand):
        def tactile_zero(self):
            raise AssertionError("demo should decide when to zero tactile sensors")

    grasper = AdaptiveGrasper(
        HandThatRejectsTactileZero(),
        AdaptiveGraspConfig(),
    )

    assert grasper.state == GraspState.IDLE


def test_grasp_core_sets_error_state_when_phase_fails(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig()
    grasper = AdaptiveGrasper(hand, cfg)

    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)

    from adaptive_grasp.grasp_sequence import PhaseResult

    def fail_phase_run(self, is_running):
        return PhaseResult(success=False, final_torque=0)

    monkeypatch.setattr(
        "adaptive_grasp.grasp_sequence.PhaseController.run",
        fail_phase_run,
    )

    assert grasper.grasp_core() is False
    assert grasper.state == GraspState.ERROR
    assert grasper._running is False


def test_grasp_core_releases_when_phase_requests_release(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig()
    grasper = AdaptiveGrasper(hand, cfg)

    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)
    release_calls = []
    monkeypatch.setattr(
        grasper,
        "_perform_release",
        lambda wait_control_thread: release_calls.append(wait_control_thread) or True,
    )

    from adaptive_grasp.grasp_sequence import PhaseResult

    def fail_phase_run(self, is_running):
        return PhaseResult(success=False, final_torque=0, should_release=True)

    monkeypatch.setattr(
        "adaptive_grasp.grasp_sequence.PhaseController.run",
        fail_phase_run,
    )

    assert grasper.grasp_core() is False
    assert release_calls == [False]


def test_grasp_core_stores_contact_snapshot_for_adaptive_hold(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig()
    grasper = AdaptiveGrasper(hand, cfg)
    closing_torque = 30

    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)
    monkeypatch.setattr("adaptive_grasp.adaptive_hold_runner.threading.Thread.start", lambda self: None)

    from adaptive_grasp.grasp_sequence import ContactSnapshot, PhaseResult

    snapshot = ContactSnapshot(
        joint_angles={JointId.THUMB_PIP: 0.12},
        finger_fz={TactileSensorId.THUMB: 1.2},
        total_fz=1.2,
        torque=closing_torque,
        reason="force_threshold",
        timestamp_s=3.4,
    )

    def successful_phase_run(self, is_running):
        return PhaseResult(
            success=True,
            final_torque=closing_torque,
            contact_snapshot=snapshot,
        )

    monkeypatch.setattr(
        "adaptive_grasp.grasp_sequence.PhaseController.run",
        successful_phase_run,
    )

    assert grasper.grasp_core() is True
    assert grasper.last_contact_snapshot is snapshot
    assert grasper._adaptive_hold_loop._contact_joint_angles == snapshot.joint_angles


def test_grasp_sequence_run_receives_only_is_running_callback(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(enable_visualization=False)
    grasper = AdaptiveGrasper(hand, cfg)
    closing_torque = 30

    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)
    monkeypatch.setattr(grasper._hold_runner, "start", lambda contact_snapshot: None)

    from adaptive_grasp.grasp_sequence import ContactSnapshot, PhaseResult

    snapshot = ContactSnapshot(
        joint_angles={JointId.THUMB_PIP: 0.12},
        finger_fz={TactileSensorId.THUMB: 1.2},
        total_fz=1.2,
        torque=closing_torque,
        reason="force_threshold",
        timestamp_s=3.4,
    )
    captured_is_running = []

    def successful_phase_run(self, is_running):
        captured_is_running.append(is_running)
        return PhaseResult(
            success=True,
            final_torque=closing_torque,
            contact_snapshot=snapshot,
        )

    monkeypatch.setattr(
        "adaptive_grasp.grasp_sequence.PhaseController.run",
        successful_phase_run,
    )

    assert grasper.grasp_core() is True
    assert len(captured_is_running) == 1
    assert captured_is_running[0]() is True


def test_torque_mode_creates_hold_planners_from_contact_snapshot(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        hold_command_mode="torque",
        active_fingers={TactileSensorId.THUMB},
        enable_visualization=False,
    )
    grasper = AdaptiveGrasper(hand, cfg)
    grasper._runtime.object_profile = ObjectProfile(
        name="paper_cup_test",
        weight_kg=0.01,
        safe_force_min=0.5,
        safe_force_max=3.5,
        friction_coeff=0.8,
        is_fragile=True,
        material="paper",
        position_hold_torque=5,
        position_hold_speed=5,
    )
    grasper._runtime.last_contact_snapshot = ContactSnapshot(
        joint_angles={JointId.THUMB_PIP: 0.12},
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
        torque=30,
        reason="force_threshold",
        timestamp_s=3.4,
    )
    monkeypatch.setattr(threading.Thread, "start", lambda self: None)

    grasper._start_adaptive_control()

    assert isinstance(grasper._adaptive_hold_loop._torque_hold_planner, TorqueHoldPlanner)
    assert isinstance(grasper._adaptive_hold_loop._force_reference_planner, ForceReferencePlanner)


def test_position_mode_creates_position_hold_planner_from_contact_snapshot(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        hold_command_mode="position",
        active_fingers={TactileSensorId.THUMB},
        enable_visualization=False,
    )
    grasper = AdaptiveGrasper(hand, cfg)
    grasper._runtime.object_profile = ObjectProfile(
        name="paper_cup_test",
        weight_kg=0.01,
        safe_force_min=0.5,
        safe_force_max=3.5,
        friction_coeff=0.8,
        is_fragile=True,
        material="paper",
        position_hold_torque=5,
        position_hold_speed=5,
    )
    grasper._runtime.last_contact_snapshot = ContactSnapshot(
        joint_angles={JointId.THUMB_PIP: 0.12},
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
        torque=30,
        reason="force_threshold",
        timestamp_s=3.4,
    )
    monkeypatch.setattr(threading.Thread, "start", lambda self: None)

    grasper._start_adaptive_control()

    assert isinstance(grasper._adaptive_hold_loop._position_hold_planner, PositionHoldPlanner)
    assert isinstance(grasper._adaptive_hold_loop._force_reference_planner, ForceReferencePlanner)


def test_full_grasp_lifecycle(monkeypatch):
    """Integration test: IDLE -> OPEN -> PRE_GRASP -> CLOSING -> ADAPTIVE_HOLD -> RELEASE -> COMPLETED。"""
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        closing_total_contact_threshold_n=0.5,
        enable_visualization=False,
        release_hold_time_s=3600.0,
        control_period_s=0.01,
        release_timeout_s=0.2,
    )
    grasper = AdaptiveGrasper(hand, cfg)

    monkeypatch.setattr("adaptive_grasp.adaptive_grasp_manager.time.sleep", lambda *_: None)
    monkeypatch.setattr("adaptive_grasp.grasp_sequence.time.sleep", lambda *_: None)
    monkeypatch.setattr(grasper, "_start_sensor_subscription", lambda: None)
    monkeypatch.setattr(grasper._sensor, "reset", lambda: None)
    monkeypatch.setattr(grasper._sensor, "sum_active_finger_normal_force", lambda: 4.0)

    # Provide tactile and joint feedback for the closing phase and adaptive hold
    grasper._sensor._latest_tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FF: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    grasper._sensor._latest_joint_feedback = []

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
        JointCommand(id=joint_id, angle=angle) for joint_id, angle in open_pose.items()
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
