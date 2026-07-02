from adaptive_grasp.adaptive_hold_loop import HoldResult, HoldStepResult
from adaptive_grasp.adaptive_hold_runner import AdaptiveHoldRunner
from adaptive_grasp.config import AdaptiveGraspConfig
from adaptive_grasp.grasp_sequence import ContactSnapshot
from adaptive_grasp.runtime import AdaptiveGraspRuntime
from adaptive_grasp.runtime import GraspState
from ghand import JointId, TactileSensorId


class _FakeSensor:
    tactile_data = {"thumb": object()}

    def __init__(self):
        self.stop_calls = []

    def data_age_s(self, current_time):
        return current_time + 0.25

    def stop(self, clear_joint_feedback=False):
        self.stop_calls.append(clear_joint_feedback)


class _FakeReleaseController:
    def __init__(self):
        self.calls = []

    def release(self, **kwargs):
        self.calls.append(kwargs)
        return True


class _FakeHoldController:
    def __init__(self, results):
        self.results = list(results)
        self.step_times = []

    def run_step(self, current_time):
        self.step_times.append(current_time)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class _Clock:
    def __init__(self, *times):
        self.times = list(times)

    def __call__(self):
        return self.times.pop(0)


def _snapshot():
    return ContactSnapshot(
        joint_angles={JointId.THUMB_PIP: 0.1},
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
        torque=5,
        reason="test",
        timestamp_s=1.0,
    )


def _runner(results, *, runtime=None, config=None, clock=None, start_thread=False):
    runtime = runtime or AdaptiveGraspRuntime(running=True)
    config = config or AdaptiveGraspConfig(enable_visualization=False)
    sensor = _FakeSensor()
    release = _FakeReleaseController()
    hold = _FakeHoldController(results)
    runner = AdaptiveHoldRunner(
        runtime=runtime,
        sensor=sensor,
        release_controller=release,
        config=config,
        hold_controller_factory=lambda snapshot: hold,
        get_monotonic_time=clock or _Clock(10.0, 10.02, 10.04),
        sleep=lambda duration: None,
    )
    runner.start(_snapshot(), start_thread=start_thread)
    return runner, runtime, sensor, release, hold


def test_start_without_thread_initializes_adaptive_hold_state():
    runner, runtime, _sensor, _release, _hold = _runner(
        [HoldStepResult(result=HoldResult.CONTINUE)],
        runtime=AdaptiveGraspRuntime(running=False),
        clock=_Clock(12.5),
    )

    assert runtime.state == GraspState.ADAPTIVE_HOLD
    assert runtime.running is True
    assert runtime.adaptive_hold_started_at == 12.5
    assert runner.thread is None


def test_hold_controller_property_exposes_compatibility_controller_slot():
    runner, _runtime, _sensor, _release, hold = _runner(
        [HoldStepResult(result=HoldResult.CONTINUE)],
    )
    replacement = _FakeHoldController([HoldStepResult(result=HoldResult.ERROR)])

    assert runner.hold_controller is hold

    runner.hold_controller = replacement

    assert runner.hold_controller is replacement


def test_run_once_error_sets_runtime_error_stops_sensor_without_release():
    runner, runtime, sensor, release, _hold = _runner(
        [HoldStepResult(result=HoldResult.ERROR)],
    )

    keep_running = runner.run_once()

    assert keep_running is False
    assert runtime.state == GraspState.ERROR
    assert runtime.running is False
    assert sensor.stop_calls == [False]
    assert release.calls == []


def test_run_loop_exception_sets_runtime_error_stops_sensor_without_release():
    runner, runtime, sensor, release, _hold = _runner(
        [RuntimeError("hold failed")],
    )

    runner._run_loop()

    assert runtime.state == GraspState.ERROR
    assert runtime.running is False
    assert sensor.stop_calls == [False]
    assert release.calls == []


def test_run_once_fault_release_calls_release_and_stops():
    runner, _runtime, _sensor, release, _hold = _runner(
        [HoldStepResult(result=HoldResult.FAULT_RELEASE)],
    )

    keep_running = runner.run_once()

    assert keep_running is False
    assert release.calls == [
        {"wait_control_thread": False, "control_thread": None},
    ]


def test_run_once_auto_release_result_calls_release_and_stops():
    runner, _runtime, _sensor, release, _hold = _runner(
        [HoldStepResult(result=HoldResult.AUTO_RELEASE)],
    )

    keep_running = runner.run_once()

    assert keep_running is False
    assert release.calls == [
        {"wait_control_thread": False, "control_thread": None},
    ]


def test_run_once_auto_release_timeout_calls_release_before_hold_step():
    config = AdaptiveGraspConfig(
        enable_visualization=False,
        release_hold_time_s=1.0,
    )
    runner, _runtime, _sensor, release, hold = _runner(
        [HoldStepResult(result=HoldResult.CONTINUE)],
        config=config,
        clock=_Clock(10.0, 11.0),
    )

    keep_running = runner.run_once()

    assert keep_running is False
    assert hold.step_times == []
    assert release.calls == [
        {"wait_control_thread": False, "control_thread": None},
    ]


def test_run_once_continue_records_step_outputs_and_timing():
    tactile_analysis = object()
    safety_report = object()
    force_decisions = {"thumb": object()}
    torque_hold_decision = object()
    step = HoldStepResult(
        result=HoldResult.CONTINUE,
        tactile_analysis=tactile_analysis,
        safety_report=safety_report,
        force_decisions=force_decisions,
        torque_hold_decision=torque_hold_decision,
        current_torque=7,
    )
    runner, runtime, _sensor, release, hold = _runner(
        [step],
        clock=_Clock(10.0, 10.02),
    )

    keep_running = runner.run_once()

    assert keep_running is True
    assert hold.step_times == [10.02]
    assert release.calls == []
    assert runtime.last_control_step_start_s == 10.02
    assert runtime.last_tactile_analysis is tactile_analysis
    assert runtime.last_safety_report is safety_report
    assert runtime.last_force_decisions is force_decisions
    assert runtime.last_torque_hold_decision is torque_hold_decision
    assert runtime.current_torque == 7
    assert runtime.last_tactile_data_age_s == 10.27


def test_start_with_thread_creates_daemon_thread(monkeypatch):
    import adaptive_grasp.adaptive_hold_runner as runner_module

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
    runner, _runtime, _sensor, _release, _hold = _runner(
        [HoldStepResult(result=HoldResult.CONTINUE)],
        start_thread=True,
    )

    assert runner.thread is created_threads[-1]
    assert created_threads[-1].target == runner._run_loop
    assert created_threads[-1].daemon is True
    assert created_threads[-1].start_calls == 1
