import threading

from adaptive_grasp.config import AdaptiveGraspConfig
from adaptive_grasp.joint_builder import JointCommandBuilder
from adaptive_grasp.release_controller import ReleaseController
from adaptive_grasp.runtime import AdaptiveGraspRuntime
from adaptive_grasp.runtime import GraspState
from ghand import CtrlMode, JointId


class _HandStub:
    def __init__(self, move_result=True):
        self.move_result = move_result
        self.calls = []

    def move_joints(self, joints, mode):
        self.calls.append({"joints": joints, "mode": mode})
        return self.move_result

    def stop(self):
        pass


class _SensorStub:
    def __init__(self):
        self.stop_calls = []

    def stop(self, clear_joint_feedback=False):
        self.stop_calls.append(clear_joint_feedback)


class _SleepRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, duration):
        self.calls.append(duration)


class _ThreadStub:
    def __init__(self, alive=True):
        self.alive = alive
        self.join_calls = []

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_calls.append(timeout)


def _controller(move_result=True, config=None):
    cfg = config or AdaptiveGraspConfig(enable_visualization=False)
    runtime = AdaptiveGraspRuntime(
        state=GraspState.ADAPTIVE_HOLD,
        running=True,
        adaptive_hold_started_at=12.0,
    )
    hand = _HandStub(move_result=move_result)
    sensor = _SensorStub()
    sleep = _SleepRecorder()
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = ReleaseController(
        hand=hand,
        sensor=sensor,
        joint_builder=joint_builder,
        runtime=runtime,
        config=cfg,
        sleep=sleep,
    )
    return controller, hand, sensor, joint_builder, runtime, cfg, sleep


def test_release_sends_open_pose_stops_sensor_and_completes():
    controller, hand, sensor, joint_builder, runtime, cfg, sleep = _controller()

    result = controller.release(wait_control_thread=False)

    assert result is True
    assert sensor.stop_calls == [False]
    assert runtime.running is False
    assert runtime.adaptive_hold_started_at is None
    assert runtime.state == GraspState.COMPLETED
    assert len(hand.calls) == 1
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    assert hand.calls[0]["joints"] == joint_builder.position_command(
        joint_builder.open_pose(),
        speed=cfg.release_open_speed,
        torque=cfg.release_open_torque,
    )
    assert sleep.calls == [cfg.release_timeout_s]


def test_release_sets_error_and_returns_false_when_move_joints_fails():
    controller, _hand, _sensor, _joint_builder, runtime, _cfg, _sleep = _controller(
        move_result=False,
    )

    result = controller.release(wait_control_thread=False)

    assert result is False
    assert runtime.state == GraspState.ERROR


def test_release_joins_alive_control_thread_when_requested():
    controller, _hand, _sensor, _joint_builder, _runtime, _cfg, _sleep = _controller()
    control_thread = _ThreadStub(alive=True)

    controller.release(wait_control_thread=True, control_thread=control_thread)

    assert control_thread.join_calls == [2.0]


def test_release_does_not_join_when_wait_control_thread_is_false():
    controller, _hand, _sensor, _joint_builder, _runtime, _cfg, _sleep = _controller()
    control_thread = _ThreadStub(alive=True)

    controller.release(wait_control_thread=False, control_thread=control_thread)

    assert control_thread.join_calls == []


def test_release_ignores_control_thread_without_thread_api():
    controller, hand, _sensor, _joint_builder, runtime, _cfg, _sleep = _controller()

    result = controller.release(wait_control_thread=True, control_thread=object())

    assert result is True
    assert runtime.state == GraspState.COMPLETED
    assert len(hand.calls) == 1


def test_release_does_not_join_current_thread():
    controller, _hand, _sensor, _joint_builder, _runtime, _cfg, _sleep = _controller()
    current_thread = threading.current_thread()

    controller.release(wait_control_thread=True, control_thread=current_thread)


def test_release_wait_s_overrides_sleep_duration():
    controller, _hand, _sensor, _joint_builder, _runtime, _cfg, sleep = _controller()

    controller.release(wait_control_thread=False, release_wait_s=0.25)

    assert sleep.calls == [0.25]
