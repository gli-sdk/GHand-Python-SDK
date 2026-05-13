# AdaptiveGrasper Port Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `AdaptiveGrasper` 拆成 facade + runtime + release/hold runner，并引入命令端口和传感器帧来源接口，为未来 MuJoCo 后端预留边界。

**Architecture:** `AdaptiveGrasper` 保持现有 SDK API，内部改为组合 `HandCommandPort`、`SensorFrameSource`、`AdaptiveGraspRuntime`、`ReleaseController` 和 `AdaptiveHoldRunner`。第一轮只做薄端口抽象，不实现完整 MuJoCo 后端，不改变控制算法。

**Tech Stack:** Python dataclasses, typing Protocol, pytest, existing `xiaoyao.adaptive_grasp` modules.

---

## 硬约束

- `src` 下只允许修改 `src/xiaoyao/adaptive_grasp/**`。
- 禁止修改 `src/xiaoyao/` 下除 `adaptive_grasp` 以外的任何文件，例如 `src/xiaoyao/__init__.py`、`src/xiaoyao/dexhand.py`、`src/xiaoyao/data.py`。
- 不要修改用户已有的未提交改动：当前已知 `examples/2x.adaptive_grasp_demo.py` 是 dirty 文件，除非用户另行要求，不碰它。
- 所有新增实现文件放在 `src/xiaoyao/adaptive_grasp/`。
- 测试可以修改 `tests/adaptive_grasp/**`。

每个实现任务提交前运行：

```powershell
git diff --name-only
```

期望：如出现 `src/xiaoyao/` 路径，只能是 `src/xiaoyao/adaptive_grasp/...`。

## 文件结构

- Create: `src/xiaoyao/adaptive_grasp/ports.py`
  - 定义 `HandCommandPort`、`SubscriptionPeriodConfigurator`、`SensorFrameSource` Protocol。
- Create: `src/xiaoyao/adaptive_grasp/hand_adapter.py`
  - 定义 `DexHandCommandPort` 和 `ensure_hand_command_port()`。
  - 封装 `hand._sub_manager.configure_periods()`。
- Create: `src/xiaoyao/adaptive_grasp/runtime.py`
  - 定义 `AdaptiveGraspRuntime`，集中保存 state/running/current_torque/object_profile/last telemetry。
- Create: `src/xiaoyao/adaptive_grasp/components.py`
  - 定义 `AdaptiveGraspComponents` 和 `build_adaptive_grasp_components()`。
- Create: `src/xiaoyao/adaptive_grasp/release_controller.py`
  - 定义 `ReleaseController`，集中释放动作和控制线程 join 规则。
- Create: `src/xiaoyao/adaptive_grasp/adaptive_hold_runner.py`
  - 定义 `AdaptiveHoldRunner`，集中 hold loop 线程、planner 创建、telemetry 记录、hold result 处理。
- Modify: `src/xiaoyao/adaptive_grasp/sensor.py`
  - 类型从具体 `DexHand` 放宽到支持 `subscribe()`/`unsubscribe()` 的对象。
- Modify: `src/xiaoyao/adaptive_grasp/grasp_sequence.py`
  - 将 `hand: DexHand` 类型改为 `HandCommandPort`，`sensor: SensorClient` 类型改为 `SensorFrameSource`。
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_hold_loop.py`
  - 将 `hand: DexHand` 类型改为 `HandCommandPort`，`sensor: SensorClient` 类型改为 `SensorFrameSource`。
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py`
  - 改为 facade，组合 runtime/components/release/hold runner。
  - 保留 `_sensor`、`_joint_builder`、`_visualizer`、`_control_thread`、`_adaptive_hold_loop` 等兼容属性，降低现有测试和用户调试代码破坏面。
- Modify: `src/xiaoyao/adaptive_grasp/__init__.py`
  - 可选择性导出新端口类型；不要修改 `src/xiaoyao/__init__.py`。
- Test: `tests/adaptive_grasp/test_hand_adapter.py`
- Test: `tests/adaptive_grasp/test_runtime.py`
- Test: `tests/adaptive_grasp/test_release_controller.py`
- Test: `tests/adaptive_grasp/test_adaptive_hold_runner.py`
- Modify: `tests/adaptive_grasp/test_adaptive_grasp_manager.py`
  - 只做必要兼容调整，保留对外行为断言。

## Task 1: Hand command port 和硬件适配层

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/ports.py`
- Create: `src/xiaoyao/adaptive_grasp/hand_adapter.py`
- Test: `tests/adaptive_grasp/test_hand_adapter.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/adaptive_grasp/test_hand_adapter.py`：

```python
import pytest

from xiaoyao.adaptive_grasp.hand_adapter import (
    DexHandCommandPort,
    ensure_hand_command_port,
)
from xiaoyao.dexhand import CtrlMode, Joint, JointId


class _FakeSubscriptionManager:
    def __init__(self):
        self.calls = []

    def configure_periods(self, *, recv_period_s, dispatch_period_s):
        self.calls.append(
            {
                "recv_period_s": recv_period_s,
                "dispatch_period_s": dispatch_period_s,
            }
        )


class _FakeDexHand:
    def __init__(self):
        self.calls = []
        self.stopped = False
        self._sub_manager = _FakeSubscriptionManager()

    def move_joints(self, joints, mode=None):
        self.calls.append({"joints": list(joints), "mode": mode})
        return True

    def stop(self):
        self.stopped = True


class _PortLike:
    def move_joints(self, joints, mode=None):
        return True

    def stop(self):
        return None


def test_dex_hand_command_port_delegates_move_and_stop():
    hand = _FakeDexHand()
    port = DexHandCommandPort(hand)
    joints = [Joint(id=JointId.THUMB_PIP, angle=0.1)]

    assert port.move_joints(joints, mode=CtrlMode.POSITION) is True
    port.stop()

    assert hand.calls == [{"joints": joints, "mode": CtrlMode.POSITION}]
    assert hand.stopped is True


def test_dex_hand_command_port_configures_subscription_periods():
    hand = _FakeDexHand()
    port = DexHandCommandPort(hand)

    port.configure_subscription_periods(recv_period_s=0.01, dispatch_period_s=0.02)

    assert hand._sub_manager.calls == [
        {
            "recv_period_s": pytest.approx(0.01),
            "dispatch_period_s": pytest.approx(0.02),
        }
    ]


def test_dex_hand_command_port_skips_missing_subscription_manager():
    hand = _PortLike()
    port = DexHandCommandPort(hand)

    port.configure_subscription_periods(recv_period_s=0.01, dispatch_period_s=0.02)


def test_ensure_hand_command_port_keeps_existing_port_like_object():
    port = _PortLike()

    assert ensure_hand_command_port(port) is port


def test_ensure_hand_command_port_wraps_dex_hand_like_object():
    hand = _FakeDexHand()

    port = ensure_hand_command_port(hand)

    assert isinstance(port, DexHandCommandPort)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_hand_adapter.py -v
```

Expected: FAIL，提示 `xiaoyao.adaptive_grasp.hand_adapter` 不存在。

- [ ] **Step 3: 实现端口和适配器**

`src/xiaoyao/adaptive_grasp/ports.py`：

```python
from typing import Any, Optional, Protocol

from xiaoyao.dexhand import CtrlMode, Joint, TactileSensorId


class HandCommandPort(Protocol):
    def move_joints(self, joints: list[Joint], mode: CtrlMode) -> bool:
        ...

    def stop(self) -> None:
        ...


class SubscriptionPeriodConfigurator(Protocol):
    def configure_subscription_periods(
        self,
        *,
        recv_period_s: float,
        dispatch_period_s: float,
    ) -> None:
        ...


class SensorFrameSource(Protocol):
    def start(self) -> None:
        ...

    def stop(self, clear_joint_feedback: bool = False) -> None:
        ...

    def reset(self) -> None:
        ...

    @property
    def tactile_data(self) -> Optional[dict[TactileSensorId, Any]]:
        ...

    @property
    def joint_feedback(self) -> Optional[list[Joint]]:
        ...

    @property
    def sample_time_s(self) -> Optional[float]:
        ...

    def data_age_s(self, current_time: float) -> Optional[float]:
        ...

    def sum_active_finger_normal_force(self) -> float:
        ...

    def active_finger_touch_flag(self) -> dict[TactileSensorId, bool]:
        ...
```

`src/xiaoyao/adaptive_grasp/hand_adapter.py`：

```python
from typing import Any

from xiaoyao.dexhand import CtrlMode, Joint

from .ports import HandCommandPort


class DexHandCommandPort:
    def __init__(self, hand: Any):
        self.hand = hand

    def move_joints(self, joints: list[Joint], mode: CtrlMode) -> bool:
        return self.hand.move_joints(joints, mode=mode)

    def stop(self) -> None:
        self.hand.stop()

    def configure_subscription_periods(
        self,
        *,
        recv_period_s: float,
        dispatch_period_s: float,
    ) -> None:
        sub_manager = getattr(self.hand, "_sub_manager", None)
        configure_periods = getattr(sub_manager, "configure_periods", None)
        if configure_periods is None:
            return
        configure_periods(
            recv_period_s=recv_period_s,
            dispatch_period_s=dispatch_period_s,
        )


def ensure_hand_command_port(hand: Any) -> HandCommandPort:
    if isinstance(hand, DexHandCommandPort):
        return hand
    if hasattr(hand, "move_joints") and hasattr(hand, "stop") and not hasattr(hand, "subscribe"):
        return hand
    return DexHandCommandPort(hand)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_hand_adapter.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

Run:

```powershell
git diff --name-only
git add src/xiaoyao/adaptive_grasp/ports.py src/xiaoyao/adaptive_grasp/hand_adapter.py tests/adaptive_grasp/test_hand_adapter.py
git commit -m "feat: add adaptive grasp hand ports"
```

Expected: diff 中 `src` 路径只包含 `src/xiaoyao/adaptive_grasp/...`。

## Task 2: Runtime 状态对象

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/runtime.py`
- Test: `tests/adaptive_grasp/test_runtime.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/adaptive_grasp/test_runtime.py`：

```python
from types import SimpleNamespace

import pytest

from xiaoyao.adaptive_grasp.adaptive_hold_loop import HoldResult, HoldStepResult
from xiaoyao.adaptive_grasp.runtime import AdaptiveGraspRuntime
from xiaoyao.adaptive_grasp.states import GraspState
from xiaoyao.adaptive_grasp.torque_hold_planner import TorqueHoldDecision
from xiaoyao.dexhand import TactileSensorId


class _FakeSensor:
    tactile_data = {TactileSensorId.THUMB: object()}

    def data_age_s(self, current_time):
        return current_time - 1.0


def test_runtime_reset_for_grasp_clears_transient_state():
    runtime = AdaptiveGraspRuntime()
    runtime.state = GraspState.ERROR
    runtime.running = True
    runtime.current_torque = 42
    runtime.adaptive_hold_started_at = 1.0
    runtime.last_tactile_analysis = object()
    runtime.last_safety_report = object()
    runtime.last_force_decisions = {}
    runtime.last_tactile_data_age_s = 0.5

    runtime.reset_for_grasp()

    assert runtime.state == GraspState.IDLE
    assert runtime.running is True
    assert runtime.current_torque == 0
    assert runtime.adaptive_hold_started_at is None
    assert runtime.last_tactile_analysis is None
    assert runtime.last_safety_report is None
    assert runtime.last_force_decisions is None
    assert runtime.last_tactile_data_age_s is None


def test_runtime_records_control_timing_and_hold_step():
    runtime = AdaptiveGraspRuntime()
    decision = TorqueHoldDecision(
        finger_torques={TactileSensorId.THUMB: 6.0},
        force_refs={TactileSensorId.THUMB: 0.5},
        contact_ratios={TactileSensorId.THUMB: 1.0},
        F_ref_total=0.5,
    )
    step = HoldStepResult(
        result=HoldResult.CONTINUE,
        tactile_analysis=SimpleNamespace(total_fz=1.2),
        safety_report=SimpleNamespace(status="ok"),
        torque_hold_decision=decision,
        current_torque=7,
    )

    runtime.update_control_cycle_timing(1.0, control_period_s=0.02)
    runtime.record_hold_step(step, _FakeSensor(), step_start=1.0)
    runtime.update_control_cycle_timing(1.03, control_period_s=0.02)

    assert runtime.last_tactile_analysis.total_fz == pytest.approx(1.2)
    assert runtime.last_safety_report.status == "ok"
    assert runtime.last_torque_hold_decision is decision
    assert runtime.current_torque == 7
    assert runtime.last_tactile_data_age_s == pytest.approx(0.0)
    assert runtime.last_control_cycle_s == pytest.approx(0.03)
    assert runtime.last_control_cycle_jitter_s == pytest.approx(0.01)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_runtime.py -v
```

Expected: FAIL，提示 `runtime` 模块不存在。

- [ ] **Step 3: 实现 runtime**

`src/xiaoyao/adaptive_grasp/runtime.py`：

```python
from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import TactileSensorId

from .adaptive_hold_loop import HoldStepResult
from .grasp_sequence import ContactSnapshot
from .object_profile import ObjectProfile
from .ports import SensorFrameSource
from .position_hold_planner import ForceDecision
from .safety import SafetyReport
from .states import GraspState
from .tactility import TactileAnalysis
from .torque_hold_planner import TorqueHoldDecision


@dataclass
class AdaptiveGraspRuntime:
    state: GraspState = GraspState.IDLE
    running: bool = False
    current_torque: int = 0
    object_profile: Optional[ObjectProfile] = None
    adaptive_hold_started_at: Optional[float] = None
    last_contact_snapshot: Optional[ContactSnapshot] = None
    last_tactile_analysis: Optional[TactileAnalysis] = None
    last_safety_report: Optional[SafetyReport] = None
    last_force_decisions: Optional[dict[TactileSensorId, ForceDecision]] = None
    last_torque_hold_decision: Optional[TorqueHoldDecision] = None
    last_tactile_data_age_s: Optional[float] = None
    last_control_step_start_s: Optional[float] = None
    last_control_cycle_s: Optional[float] = None
    last_control_cycle_jitter_s: Optional[float] = None

    def reset_for_grasp(self) -> None:
        self.running = True
        self.state = GraspState.IDLE
        self.current_torque = 0
        self.object_profile = None
        self.adaptive_hold_started_at = None
        self.last_contact_snapshot = None
        self.last_tactile_analysis = None
        self.last_safety_report = None
        self.last_force_decisions = None
        self.last_torque_hold_decision = None
        self.last_tactile_data_age_s = None
        self.last_control_step_start_s = None
        self.last_control_cycle_s = None
        self.last_control_cycle_jitter_s = None

    def update_control_cycle_timing(
        self,
        step_start: float,
        *,
        control_period_s: float,
    ) -> None:
        if self.last_control_step_start_s is not None:
            control_cycle_s = step_start - self.last_control_step_start_s
            self.last_control_cycle_s = control_cycle_s
            self.last_control_cycle_jitter_s = control_cycle_s - control_period_s
        self.last_control_step_start_s = step_start

    def record_hold_step(
        self,
        step: HoldStepResult,
        sensor: SensorFrameSource,
        step_start: float,
    ) -> None:
        self.last_tactile_analysis = step.tactile_analysis
        self.last_safety_report = step.safety_report
        self.last_force_decisions = step.force_decisions
        self.last_torque_hold_decision = step.torque_hold_decision
        if step.current_torque is not None:
            self.current_torque = step.current_torque

        self.last_tactile_data_age_s = (
            sensor.data_age_s(step_start)
            if sensor.tactile_data is not None
            else None
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_runtime.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

Run:

```powershell
git diff --name-only
git add src/xiaoyao/adaptive_grasp/runtime.py tests/adaptive_grasp/test_runtime.py
git commit -m "feat: add adaptive grasp runtime state"
```

## Task 3: Components 构造器

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/components.py`
- Test: `tests/adaptive_grasp/test_components.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/adaptive_grasp/test_components.py`：

```python
from xiaoyao.adaptive_grasp.components import build_adaptive_grasp_components
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.hold_planner_factory import HoldPlannerFactory
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.adaptive_grasp.safety import SafetyMonitor
from xiaoyao.adaptive_grasp.sensor import SensorClient
from xiaoyao.adaptive_grasp.tactility import TactileAnalyzer


class _FakeHand:
    def subscribe(self, callback):
        return 1

    def unsubscribe(self, sub_id):
        return None


def test_build_components_creates_default_runtime_dependencies():
    cfg = AdaptiveGraspConfig(enable_visualization=False)

    components = build_adaptive_grasp_components(
        hand=_FakeHand(),
        config=cfg,
        get_monotonic_time=lambda: 1.0,
    )

    assert isinstance(components.sensor, SensorClient)
    assert isinstance(components.tactile, TactileAnalyzer)
    assert isinstance(components.safety, SafetyMonitor)
    assert isinstance(components.joint_builder, JointCommandBuilder)
    assert isinstance(components.hold_planner_factory, HoldPlannerFactory)
    assert components.visualizer is None
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_components.py -v
```

Expected: FAIL，提示 `components` 模块不存在。

- [ ] **Step 3: 实现 components**

`src/xiaoyao/adaptive_grasp/components.py`：

```python
from dataclasses import dataclass
from typing import Any, Callable, Optional

from xiaoyao.dexhand import TactileSensorId

from .config import AdaptiveGraspConfig
from .hold_planner_factory import HoldPlannerFactory
from .joint_builder import JointCommandBuilder, TORQUE_CONTROL_JOINTS
from .ports import SensorFrameSource
from .safety import SafetyMonitor
from .sensor import SensorClient
from .tactility import TactileAnalyzer
from .utils import JOINT_TO_FINGER
from .visualization import TactileVisualizer


@dataclass
class AdaptiveGraspComponents:
    sensor: SensorFrameSource
    tactile: TactileAnalyzer
    safety: SafetyMonitor
    joint_builder: JointCommandBuilder
    hold_planner_factory: HoldPlannerFactory
    visualizer: Optional[TactileVisualizer]


def _active_torque_joints(config: AdaptiveGraspConfig):
    return tuple(
        joint
        for joint in TORQUE_CONTROL_JOINTS
        if JOINT_TO_FINGER.get(joint) in config.active_fingers
    )


def build_adaptive_grasp_components(
    *,
    hand: Any,
    config: AdaptiveGraspConfig,
    get_monotonic_time: Callable[[], float],
    sensor: Optional[SensorFrameSource] = None,
) -> AdaptiveGraspComponents:
    active_fingers: set[TactileSensorId] = set(config.active_fingers)
    sensor_source = sensor or SensorClient(
        hand,
        active_fingers=active_fingers,
        finger_touch_threshold_n=config.finger_touch_threshold_n,
        get_monotonic_time=get_monotonic_time,
    )
    visualizer = (
        TactileVisualizer(
            active_fingers=active_fingers,
            backend=config.visualization_backend,
        )
        if config.enable_visualization
        else None
    )
    return AdaptiveGraspComponents(
        sensor=sensor_source,
        tactile=TactileAnalyzer(config),
        safety=SafetyMonitor(config),
        joint_builder=JointCommandBuilder(config, _active_torque_joints(config)),
        hold_planner_factory=HoldPlannerFactory(config),
        visualizer=visualizer,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_components.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

Run:

```powershell
git diff --name-only
git add src/xiaoyao/adaptive_grasp/components.py tests/adaptive_grasp/test_components.py
git commit -m "feat: add adaptive grasp component builder"
```

## Task 4: ReleaseController

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/release_controller.py`
- Test: `tests/adaptive_grasp/test_release_controller.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/adaptive_grasp/test_release_controller.py`：

```python
import threading
import time

from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.adaptive_grasp.release_controller import ReleaseController
from xiaoyao.adaptive_grasp.runtime import AdaptiveGraspRuntime
from xiaoyao.adaptive_grasp.states import GraspState
from xiaoyao.dexhand import CtrlMode


class _FakeHandPort:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def move_joints(self, joints, mode=None):
        self.calls.append({"joints": list(joints), "mode": mode})
        return self.ok

    def stop(self):
        return None


class _FakeSensor:
    def __init__(self):
        self.stop_calls = []

    def stop(self, clear_joint_feedback=False):
        self.stop_calls.append(clear_joint_feedback)


def _controller(ok=True):
    cfg = AdaptiveGraspConfig(enable_visualization=False)
    runtime = AdaptiveGraspRuntime(
        state=GraspState.ADAPTIVE_HOLD,
        running=True,
    )
    hand = _FakeHandPort(ok=ok)
    sensor = _FakeSensor()
    joint_builder = JointCommandBuilder(cfg, tuple())
    return (
        ReleaseController(
            hand=hand,
            sensor=sensor,
            joint_builder=joint_builder,
            runtime=runtime,
            config=cfg,
            sleep=lambda _: None,
        ),
        runtime,
        hand,
        sensor,
    )


def test_release_sends_open_pose_and_completes():
    controller, runtime, hand, sensor = _controller()

    assert controller.release(wait_control_thread=False, release_wait_s=0.1) is True

    assert runtime.running is False
    assert runtime.state == GraspState.COMPLETED
    assert sensor.stop_calls == [False]
    assert hand.calls[-1]["mode"] == CtrlMode.POSITION


def test_release_sets_error_when_open_command_fails():
    controller, runtime, hand, sensor = _controller(ok=False)

    assert controller.release(wait_control_thread=False) is False

    assert runtime.state == GraspState.ERROR


def test_release_waits_for_control_thread_when_requested():
    controller, runtime, hand, sensor = _controller()
    joined = [False]

    def loop():
        while not joined[0]:
            time.sleep(0.001)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    original_join = thread.join

    def tracking_join(timeout=None):
        joined[0] = True
        original_join(timeout=timeout)

    thread.join = tracking_join

    assert controller.release(wait_control_thread=True, control_thread=thread) is True
    assert joined[0] is True


def test_fast_release_does_not_wait_for_control_thread():
    controller, runtime, hand, sensor = _controller()

    class _BlockingThread:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            raise AssertionError("fast release should not wait")

    assert controller.release(
        wait_control_thread=False,
        release_wait_s=0.1,
        control_thread=_BlockingThread(),
    ) is True
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_release_controller.py -v
```

Expected: FAIL，提示 `release_controller` 模块不存在。

- [ ] **Step 3: 实现 ReleaseController**

`src/xiaoyao/adaptive_grasp/release_controller.py`：

```python
import logging
import threading
import time
from typing import Callable, Optional

from xiaoyao.dexhand import CtrlMode

from .config import AdaptiveGraspConfig
from .joint_builder import JointCommandBuilder
from .ports import HandCommandPort, SensorFrameSource
from .runtime import AdaptiveGraspRuntime
from .states import GraspState

_logger = logging.getLogger("xiaoyao.adaptive_grasp.release_controller")


class ReleaseController:
    def __init__(
        self,
        *,
        hand: HandCommandPort,
        sensor: SensorFrameSource,
        joint_builder: JointCommandBuilder,
        runtime: AdaptiveGraspRuntime,
        config: AdaptiveGraspConfig,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._hand = hand
        self._sensor = sensor
        self._joint_builder = joint_builder
        self._runtime = runtime
        self._config = config
        self._sleep = sleep

    def release(
        self,
        *,
        wait_control_thread: bool,
        release_wait_s: Optional[float] = None,
        control_thread: Optional[threading.Thread] = None,
    ) -> bool:
        self._runtime.state = GraspState.RELEASE
        self._runtime.running = False
        self._runtime.adaptive_hold_started_at = None
        self._sensor.stop(clear_joint_feedback=False)

        if self._should_join(wait_control_thread, control_thread):
            control_thread.join(timeout=2.0)

        joints = self._joint_builder.position_command(
            self._joint_builder.open_pose(),
            speed=self._config.release_open_speed,
            torque=self._config.release_open_torque,
        )
        ok = self._hand.move_joints(joints, mode=CtrlMode.POSITION)
        self._sleep(
            self._config.release_timeout_s
            if release_wait_s is None
            else release_wait_s
        )
        if not ok:
            _logger.error("RELEASE phase: move_joints failed")
            self._runtime.state = GraspState.ERROR
            return False

        self._runtime.state = GraspState.COMPLETED
        return True

    @staticmethod
    def _should_join(
        wait_control_thread: bool,
        control_thread: Optional[threading.Thread],
    ) -> bool:
        return (
            wait_control_thread
            and control_thread is not None
            and control_thread.is_alive()
            and control_thread is not threading.current_thread()
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_release_controller.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

Run:

```powershell
git diff --name-only
git add src/xiaoyao/adaptive_grasp/release_controller.py tests/adaptive_grasp/test_release_controller.py
git commit -m "feat: add adaptive grasp release controller"
```

## Task 5: 类型端口接入 PhaseController 和 HoldController

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/sensor.py`
- Modify: `src/xiaoyao/adaptive_grasp/grasp_sequence.py`
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_hold_loop.py`
- Test: existing `tests/adaptive_grasp/test_grasp_sequence.py`
- Test: existing `tests/adaptive_grasp/test_adaptive_hold_loop.py`

- [ ] **Step 1: 写或确认现有测试覆盖 fake hand**

现有测试已经使用 fake hand 的 `move_joints()` 构造 `PhaseController` 和 `HoldController`。本任务不需要新增行为测试，只需要确保类型变更后仍通过。

- [ ] **Step 2: 运行相关测试基线**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_grasp_sequence.py tests/adaptive_grasp/test_adaptive_hold_loop.py -v
```

Expected: 当前应 PASS。

- [ ] **Step 3: 修改类型依赖**

在 `sensor.py` 中：

- 保留 `Joint`, `JointId`, `State`, `ErrorCode`, `TactileInfo`, `TactileSensorId` imports。
- 移除仅用于类型的 `DexHand` import 或改成 `Any`/Protocol。
- `SensorClient.__init__(hand: DexHand, ...)` 改成 `hand: Any`。

在 `grasp_sequence.py` 中：

- 从 `xiaoyao.dexhand` import 中移除 `DexHand`。
- 增加 `from .ports import HandCommandPort, SensorFrameSource`。
- `PhaseController.__init__(hand: DexHand, sensor: SensorClient, ...)` 改成 `hand: HandCommandPort, sensor: SensorFrameSource`。

在 `adaptive_hold_loop.py` 中：

- 从 `xiaoyao.dexhand` import 中移除 `DexHand`。
- 增加 `from .ports import HandCommandPort, SensorFrameSource`。
- `HoldController.__init__(hand: DexHand, sensor: SensorClient, ...)` 改成 `hand: HandCommandPort, sensor: SensorFrameSource`。

- [ ] **Step 4: 运行相关测试确认通过**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_grasp_sequence.py tests/adaptive_grasp/test_adaptive_hold_loop.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

Run:

```powershell
git diff --name-only
git add src/xiaoyao/adaptive_grasp/sensor.py src/xiaoyao/adaptive_grasp/grasp_sequence.py src/xiaoyao/adaptive_grasp/adaptive_hold_loop.py
git commit -m "refactor: depend on adaptive grasp ports"
```

## Task 6: AdaptiveHoldRunner

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/adaptive_hold_runner.py`
- Test: `tests/adaptive_grasp/test_adaptive_hold_runner.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/adaptive_grasp/test_adaptive_hold_runner.py`，使用 fake hold controller factory 避免启动真实控制算法：

```python
from xiaoyao.adaptive_grasp.adaptive_hold_loop import HoldResult, HoldStepResult
from xiaoyao.adaptive_grasp.adaptive_hold_runner import AdaptiveHoldRunner
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.grasp_sequence import ContactSnapshot
from xiaoyao.adaptive_grasp.runtime import AdaptiveGraspRuntime
from xiaoyao.adaptive_grasp.states import GraspState
from xiaoyao.dexhand import JointId, TactileSensorId


class _FakeSensor:
    tactile_data = None

    def data_age_s(self, current_time):
        return None

    def stop(self, clear_joint_feedback=False):
        self.stopped = clear_joint_feedback


class _FakeReleaseController:
    def __init__(self):
        self.calls = []

    def release(self, **kwargs):
        self.calls.append(kwargs)
        return True


class _FakeHoldController:
    def __init__(self, results):
        self.results = list(results)

    def run_step(self, current_time):
        return self.results.pop(0)


def _snapshot():
    return ContactSnapshot(
        joint_angles={JointId.THUMB_PIP: 0.1},
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
        torque=5,
        reason="test",
        timestamp_s=1.0,
    )


def test_hold_runner_records_error_result_without_thread():
    runtime = AdaptiveGraspRuntime(running=True)
    sensor = _FakeSensor()
    release = _FakeReleaseController()
    controller = _FakeHoldController([HoldStepResult(result=HoldResult.ERROR)])
    runner = AdaptiveHoldRunner(
        runtime=runtime,
        sensor=sensor,
        release_controller=release,
        config=AdaptiveGraspConfig(enable_visualization=False),
        hold_controller_factory=lambda contact_snapshot: controller,
        get_monotonic_time=lambda: 1.0,
        sleep=lambda _: None,
    )

    runner.start(_snapshot(), start_thread=False)
    runner.run_once()

    assert runtime.state == GraspState.ERROR
    assert runtime.running is False
    assert release.calls == []


def test_hold_runner_releases_on_fault_release_without_thread():
    runtime = AdaptiveGraspRuntime(running=True)
    release = _FakeReleaseController()
    controller = _FakeHoldController([HoldStepResult(result=HoldResult.FAULT_RELEASE)])
    runner = AdaptiveHoldRunner(
        runtime=runtime,
        sensor=_FakeSensor(),
        release_controller=release,
        config=AdaptiveGraspConfig(enable_visualization=False),
        hold_controller_factory=lambda contact_snapshot: controller,
        get_monotonic_time=lambda: 1.0,
        sleep=lambda _: None,
    )

    runner.start(_snapshot(), start_thread=False)
    runner.run_once()

    assert release.calls == [{"wait_control_thread": False, "control_thread": None}]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_adaptive_hold_runner.py -v
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 3: 实现 AdaptiveHoldRunner**

实现要点：

- 构造函数接收 runtime、sensor、release_controller、config。
- 生产路径还接收 hand、safety、tactile、visualizer、joint_builder、hold_planner_factory、current torque 所需依赖，或接收 `hold_controller_factory`。
- 为了测试简洁，支持注入 `hold_controller_factory`。
- `start(contact_snapshot, start_thread=True)` 创建 hold controller，设置状态和开始时间。
- `run_once()` 执行一个周期：更新时间、判断 auto release、调用 `run_step()`、记录 telemetry、处理结果。
- `_run_loop()` while runtime.running 调用 `run_once()` 并 sleep。
- `thread` property 返回线程。

关键代码结构：

```python
class AdaptiveHoldRunner:
    def start(self, contact_snapshot, *, start_thread=True) -> None:
        self._hold_controller = self._hold_controller_factory(contact_snapshot)
        self._runtime.state = GraspState.ADAPTIVE_HOLD
        self._runtime.adaptive_hold_started_at = self._get_monotonic_time()
        if start_thread:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def run_once(self) -> bool:
        step_start = self._get_monotonic_time()
        self._runtime.update_control_cycle_timing(
            step_start,
            control_period_s=self._config.control_period_s,
        )
        if self._should_auto_release(step_start):
            self._release_controller.release(
                wait_control_thread=False,
                control_thread=self._thread,
            )
            return False
        step = self._hold_controller.run_step(step_start)
        self._runtime.record_hold_step(step, self._sensor, step_start)
        return not self._handle_result(step.result)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_adaptive_hold_runner.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

Run:

```powershell
git diff --name-only
git add src/xiaoyao/adaptive_grasp/adaptive_hold_runner.py tests/adaptive_grasp/test_adaptive_hold_runner.py
git commit -m "feat: add adaptive hold runner"
```

## Task 7: 改造 AdaptiveGrasper 为 facade

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py`
- Modify: `tests/adaptive_grasp/test_adaptive_grasp_manager.py`

- [ ] **Step 1: 运行 manager 测试基线**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_adaptive_grasp_manager.py -v
```

Expected: 当前应 PASS。如果不通过，先记录当前失败，不要在本任务中顺手修无关问题。

- [ ] **Step 2: 修改 AdaptiveGrasper 构造**

在 `AdaptiveGrasper.__init__` 中：

- `self.hand = hand` 保留为原始 hand，兼容外部调试。
- 新增 `self._hand_port = ensure_hand_command_port(hand)`。
- 新增 `self._runtime = AdaptiveGraspRuntime()`。
- 使用 `build_adaptive_grasp_components(hand=hand, config=self.config, get_monotonic_time=self._get_monotonic_time)`。
- 保留兼容属性：
  - `self._sensor = self._components.sensor`
  - `self._tactile = self._components.tactile`
  - `self._safety = self._components.safety`
  - `self._joint_builder = self._components.joint_builder`
  - `self._hold_planner_factory = self._components.hold_planner_factory`
  - `self._visualizer = self._components.visualizer`
- 创建 `ReleaseController`。
- 创建 `AdaptiveHoldRunner`。
- `_configure_subscription_periods()` 改为调用 hand port 的 `configure_subscription_periods()`，如果存在。

保留 `state` 和 `_running` 兼容属性的方式：

```python
@property
def state(self) -> GraspState:
    return self._runtime.state

@state.setter
def state(self, value: GraspState) -> None:
    self._runtime.state = value

@property
def _running(self) -> bool:
    return self._runtime.running

@_running.setter
def _running(self, value: bool) -> None:
    self._runtime.running = value
```

同理保留 `current_torque` property，转发 runtime。

- [ ] **Step 3: 修改 grasp_core 和 runtime reset**

- `_prepare_grasp_runtime()` 调用：
  - `self._runtime.reset_for_grasp()`
  - `self._tactile.reset()`
  - `self._safety.reset()`
  - `self._sensor.reset()`
  - 设置 `self._runtime.object_profile`
  - 设置 friction coeff
  - start sensor
- `_run_grasp_sequence()` 继续创建 `PhaseController(self._hand_port, self._sensor, ...)`。
- phase 成功后：
  - `self.current_torque = result.final_torque`
  - `self._runtime.last_contact_snapshot = result.contact_snapshot`
  - `self._hold_runner.start(result.contact_snapshot)`
- phase 失败 release 时调用 `self._release_controller.release(wait_control_thread=False, control_thread=self._hold_runner.thread)`。

- [ ] **Step 4: 修改 release/stop/telemetry 转发**

- `release()` 调用 release controller，传 `control_thread=self._hold_runner.thread`。
- `release_fast()` 同上，但 `wait_control_thread=False`。
- `stop()`：
  - runtime.running = False
  - sensor.stop()
  - hold_runner.stop()
  - finalize visualizer
  - hand_port.stop()
  - runtime.state = STOPPED
- `last_*` properties 全部转发 runtime。
- `_control_thread` property 返回 `self._hold_runner.thread`，setter 保留兼容测试；若测试直接设置 `_control_thread`，需要让 release 使用该 override。可用 `_control_thread_override` 简化兼容。

- [ ] **Step 5: 更新或保留兼容私有方法**

为了降低测试迁移量，保留以下私有方法作为薄 wrapper：

- `_perform_release()` 调 release controller。
- `_adaptive_control_loop()` 调 hold runner 的 loop 或保留兼容路径。
- `_record_hold_step()` 调 runtime。
- `_update_control_cycle_timing()` 调 runtime。
- `_handle_hold_result()` 调 hold runner 或 release controller。
- `_start_sensor_subscription()` / `_stop_sensor_subscription()` 继续调用 sensor。
- `_reset_runtime_state()` 调 runtime/components reset。

- [ ] **Step 6: 运行 manager 测试**

Run:

```powershell
python -m pytest tests/adaptive_grasp/test_adaptive_grasp_manager.py -v
```

Expected: PASS。若失败，优先通过兼容 wrapper 修复，不改变对外行为。

- [ ] **Step 7: 运行 adaptive_grasp 全量测试**

Run:

```powershell
python -m pytest tests/adaptive_grasp -v
```

Expected: PASS。

- [ ] **Step 8: 提交**

Run:

```powershell
git diff --name-only
git add src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py tests/adaptive_grasp/test_adaptive_grasp_manager.py
git commit -m "refactor: split adaptive grasper facade runtime"
```

## Task 8: 可选导出和最终兼容验证

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/__init__.py`
- Test: existing tests

- [ ] **Step 1: 判断是否需要导出新类型**

如果外部用户需要构建 MuJoCo adapter，可从包内直接 import 端口类型更方便。只允许修改：

`src/xiaoyao/adaptive_grasp/__init__.py`

禁止修改：

`src/xiaoyao/__init__.py`

- [ ] **Step 2: 更新 `adaptive_grasp/__init__.py`**

可选新增：

```python
from .ports import HandCommandPort, SensorFrameSource
from .hand_adapter import DexHandCommandPort, ensure_hand_command_port
```

并加入 `__all__`。

- [ ] **Step 3: 运行导入测试**

Run:

```powershell
python -m pytest tests/adaptive_grasp -v
```

Expected: PASS。

- [ ] **Step 4: 运行示例测试**

Run:

```powershell
python -m pytest tests/examples/test_2x_adaptive_grasp_demo.py -v
```

Expected: PASS。

- [ ] **Step 5: 文件边界校验**

Run:

```powershell
git diff --name-only HEAD
```

Expected:

- 允许：`src/xiaoyao/adaptive_grasp/...`
- 允许：`tests/adaptive_grasp/...`
- 允许：`docs/superpowers/plans/...`
- 禁止：`src/xiaoyao/__init__.py` 或其他 `src/xiaoyao/*.py`
- 不应包含：`examples/2x.adaptive_grasp_demo.py`，除非用户明确要求

- [ ] **Step 6: 提交**

Run:

```powershell
git add src/xiaoyao/adaptive_grasp/__init__.py
git commit -m "feat: export adaptive grasp ports"
```

如果没有修改 `__init__.py`，跳过提交。

## Task 9: 最终验证

**Files:**
- No code changes unless tests reveal a scoped issue.

- [ ] **Step 1: 运行核心测试**

Run:

```powershell
python -m pytest tests/adaptive_grasp -v
```

Expected: PASS。

- [ ] **Step 2: 运行示例测试**

Run:

```powershell
python -m pytest tests/examples/test_2x_adaptive_grasp_demo.py -v
```

Expected: PASS。

- [ ] **Step 3: 检查工作区和禁止路径**

Run:

```powershell
git status --short
git diff --name-only HEAD
```

Expected:

- 未提交或已提交的改动不能包含 `src/xiaoyao/` 下除 `src/xiaoyao/adaptive_grasp/**` 外的路径。
- 不要覆盖用户已有的 `examples/2x.adaptive_grasp_demo.py` 改动。

- [ ] **Step 4: 如果测试通过，提交剩余必要修复**

Run:

```powershell
git add <only scoped files>
git commit -m "test: verify adaptive grasper port refactor"
```

如果没有剩余改动，跳过提交。

