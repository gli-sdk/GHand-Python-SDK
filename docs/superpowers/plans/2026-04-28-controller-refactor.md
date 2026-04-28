# Controller 重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `controller.py`（558 行）拆分为 `AdaptiveGrasper` 协调器 + `JointCommandBuilder` + `PhaseController` + `HoldController`，降低单次阅读的认知负荷。

**Architecture:** 按运行时生命周期拆分：顺序阶段（OPEN→PRE_GRASP→CLOSING）由 `PhaseController` 负责，后台自适应保持由 `HoldController` 负责单步逻辑，`AdaptiveGrasper` 保留线程管理和公共 API。关节指令构建提取为无状态的 `JointCommandBuilder`。

**Tech Stack:** Python 3.11, pytest, 现有 DexHand / SensorClient / SafetyMonitor 等子模块

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/xiaoyao/adaptive_grasp/joint_builder.py` | 创建 | 纯函数式关节指令组装 |
| `src/xiaoyao/adaptive_grasp/phase_controller.py` | 创建 | 顺序阶段执行 + 力校准 |
| `src/xiaoyao/adaptive_grasp/hold_controller.py` | 创建 | ADAPTIVE_HOLD 单步控制逻辑 |
| `src/xiaoyao/adaptive_grasp/controller.py` | 修改 | 瘦身，退化为协调器 |
| `tests/adaptive_grasp/test_joint_builder.py` | 创建 | JointCommandBuilder 测试 |
| `tests/adaptive_grasp/test_phase_controller.py` | 创建 | PhaseController 测试 |
| `tests/adaptive_grasp/test_hold_controller.py` | 创建 | HoldController 测试 |
| `tests/adaptive_grasp/test_controller.py` | 修改 | 保留集成测试，迁移已拆分的单元测试 |

---

## Task 1: JointCommandBuilder

**Files:**
- Create: `tests/adaptive_grasp/test_joint_builder.py`
- Create: `src/xiaoyao/adaptive_grasp/joint_builder.py`

- [ ] **Step 1: Write failing tests**

创建 `tests/adaptive_grasp/test_joint_builder.py`：

```python
import math
import pytest
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.dexhand import JointId


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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/adaptive_grasp/test_joint_builder.py -v`

Expected: `ModuleNotFoundError: No module named 'xiaoyao.adaptive_grasp.joint_builder'`

- [ ] **Step 3: Implement JointCommandBuilder**

创建 `src/xiaoyao/adaptive_grasp/joint_builder.py`：

```python
import math
from typing import Mapping, Optional

from xiaoyao.dexhand import Joint, JointId
from .config import AdaptiveGraspConfig
from .utils import clip


class JointCommandBuilder:
    _TORQUE_JOINTS = (
        JointId.THUMB_PIP, JointId.THUMB_MCP,
        JointId.FF_PIP, JointId.FF_MCP,
        JointId.MF_PIP, JointId.MF_MCP,
        JointId.RF_PIP, JointId.RF_MCP,
        JointId.LF_PIP, JointId.LF_MCP,
    )

    def __init__(self, config: AdaptiveGraspConfig, torque_joints: tuple[JointId, ...]):
        self._config = config
        self._torque_joints = torque_joints

    def open_pose(self) -> dict[JointId, float]:
        return {
            JointId.THUMB_PIP: math.radians(0),
            JointId.THUMB_MCP: math.radians(0),
            JointId.THUMB_SWING: math.radians(20),
            JointId.THUMB_ROTATION: math.radians(0),
            JointId.FF_PIP: math.radians(0),
            JointId.FF_MCP: math.radians(0),
            JointId.FF_SWING: math.radians(0),
            JointId.MF_PIP: math.radians(0),
            JointId.MF_MCP: math.radians(0),
            JointId.RF_PIP: math.radians(0),
            JointId.RF_MCP: math.radians(0),
            JointId.LF_PIP: math.radians(0),
            JointId.LF_MCP: math.radians(0),
        }

    def init_hold_angles(self) -> dict[JointId, float]:
        return {
            joint_id: self._config.pre_grasp_pose.get(joint_id, 0.0)
            for joint_id in self._torque_joints
        }

    def position_command(self, angles: dict[JointId, float], speed: int, torque: int) -> list[Joint]:
        return [
            Joint(id=joint_id, angle=angle, speed=speed, torque=torque)
            for joint_id, angle in angles.items()
        ]

    def torque_command(self, torque: int) -> list[Joint]:
        active = set(self._torque_joints)
        joints = [
            Joint(id=joint_id, torque=torque)
            if joint_id in active
            else Joint(id=joint_id, angle=0.0, speed=0, torque=0)
            for joint_id in JointCommandBuilder._TORQUE_JOINTS
        ]
        joints += [
            Joint(id=JointId.THUMB_ROTATION, angle=0.0, speed=0, torque=5),
            Joint(id=JointId.THUMB_SWING, angle=0.0, speed=0, torque=5),
        ]
        return joints

    def hold_position_command(self, torque: int, angles: Optional[Mapping[JointId, float]] = None) -> list[Joint]:
        limited_torque = int(clip(abs(torque), 0.0, float(self._config.position_torque_limit)))
        hold_angles = angles or self.init_hold_angles()
        return [
            Joint(
                id=joint_id,
                angle=hold_angles.get(joint_id, 0.0),
                speed=int(self._config.position_speed_limit),
                torque=limited_torque,
            )
            for joint_id in self._torque_joints
        ]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/adaptive_grasp/test_joint_builder.py -v`

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add tests/adaptive_grasp/test_joint_builder.py src/xiaoyao/adaptive_grasp/joint_builder.py
git commit -m "feat(adaptive_grasp): extract JointCommandBuilder from controller"
```

---

## Task 2: PhaseController 框架与简单阶段

**Files:**
- Create: `tests/adaptive_grasp/test_phase_controller.py`
- Create: `src/xiaoyao/adaptive_grasp/phase_controller.py`

- [ ] **Step 1: Write failing tests**

创建 `tests/adaptive_grasp/test_phase_controller.py`：

```python
import time
from unittest.mock import MagicMock
import pytest
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig, GraspState
from xiaoyao.adaptive_grasp.phase_controller import PhaseController, PhaseResult
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.dexhand import CtrlMode, JointId


class _MockHand:
    def __init__(self):
        self.calls = []

    def move_joints(self, joints, mode=None):
        self.calls.append({"mode": mode, "joints": list(joints)})
        return True

    def stop(self):
        return None


def test_phase_open_and_pre_grasp(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(pre_grasp_preset="two_finger_pinch")
    sensor = MagicMock()
    safety = MagicMock()
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=lambda s: None,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.phase_controller.time.sleep", lambda *_: None)

    result = controller.run(force_planner=None, is_running=lambda: True)

    assert isinstance(result, PhaseResult)
    assert result.success is True
    assert len(hand.calls) == 2
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    assert hand.calls[1]["mode"] == CtrlMode.POSITION
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/adaptive_grasp/test_phase_controller.py::test_phase_open_and_pre_grasp -v`

Expected: `ModuleNotFoundError: No module named 'xiaoyao.adaptive_grasp.phase_controller'`

- [ ] **Step 3: Implement PhaseController 框架**

创建 `src/xiaoyao/adaptive_grasp/phase_controller.py`，先实现 OPEN 和 PRE_GRASP：

```python
import logging
import time
from typing import Any, Callable, Optional

from xiaoyao.dexhand import CtrlMode, DexHand, Joint, JointId
from .config import AdaptiveGraspConfig
from .states import GraspState
from .sensor import SensorClient
from .safety import SafetyMonitor
from .force_planner import ForcePlanner
from .joint_builder import JointCommandBuilder
from .utils import clip

_logger = logging.getLogger("xiaoyao.adaptive_grasp.phase_controller")


class PhaseResult:
    def __init__(self, success: bool, final_torque: int):
        self.success = success
        self.final_torque = final_torque


class PhaseController:
    def __init__(
        self,
        hand: DexHand,
        sensor: SensorClient,
        safety: SafetyMonitor,
        joint_builder: JointCommandBuilder,
        config: AdaptiveGraspConfig,
        get_time: Callable[[], float],
        on_state_change: Callable[[GraspState], None],
    ):
        self.hand = hand
        self._sensor = sensor
        self._safety = safety
        self._joint_builder = joint_builder
        self.config = config
        self._get_monotonic_time = get_time
        self._on_state_change = on_state_change
        self.current_torque = int(clip(config.base_torque, -100.0, config.max_torque))

    def run(self, force_planner: Optional[ForcePlanner], is_running: Callable[[], bool]) -> PhaseResult:
        for phase_method, name in (
            (self._phase_open, "OPEN"),
            (self._phase_pre_grasp, "PRE_GRASP"),
        ):
            if not is_running():
                return PhaseResult(success=False, final_torque=self.current_torque)
            if not phase_method():
                _logger.error("%s phase failed", name)
                return PhaseResult(success=False, final_torque=self.current_torque)
        # CLOSING 将在 Task 3 实现
        return PhaseResult(success=True, final_torque=self.current_torque)

    def _set_state(self, state: GraspState) -> None:
        self._on_state_change(state)

    def _execute_position_phase(self, state: GraspState, pose: dict[JointId, float], sleep_s: float) -> bool:
        self._set_state(state)
        joints = self._joint_builder.position_command(pose, speed=50, torque=50)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(sleep_s)
        return ok

    def _phase_open(self) -> bool:
        return self._execute_position_phase(
            GraspState.OPEN, self._joint_builder.open_pose(), sleep_s=3,
        )

    def _phase_pre_grasp(self) -> bool:
        return self._execute_position_phase(
            GraspState.PRE_GRASP, self.config.pre_grasp_pose, sleep_s=5,
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/adaptive_grasp/test_phase_controller.py::test_phase_open_and_pre_grasp -v`

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add tests/adaptive_grasp/test_phase_controller.py src/xiaoyao/adaptive_grasp/phase_controller.py
git commit -m "feat(adaptive_grasp): extract PhaseController framework with OPEN/PRE_GRASP"
```

---

## Task 3: PhaseController CLOSING 阶段

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/phase_controller.py`
- Modify: `tests/adaptive_grasp/test_phase_controller.py`

- [ ] **Step 1: Write failing tests**

在 `tests/adaptive_grasp/test_phase_controller.py` 末尾追加：

```python
from xiaoyao.dexhand import Joint, TactileSensorId


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


def test_phase_closing_contact_by_force(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        contact_threshold_z=0.5,
        phase_timeout=10.0,
        control_period_s=0.001,
    )
    sensor = MagicMock()
    safety = MagicMock()
    safety.is_grasp_empty.return_value = MagicMock(status=MagicMock(return_value="OK"))
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    states = []
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=states.append,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.phase_controller.time.sleep", lambda *_: None)

    sensor.tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    sensor.joint_feedback = []
    sensor.sum_active_finger_normal_force.return_value = 4.0

    result = controller.run(force_planner=None, is_running=lambda: True)

    assert result.success is True
    assert GraspState.CLOSING_TO_CONTACT in states
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/adaptive_grasp/test_phase_controller.py::test_phase_closing_contact_by_force -v`

Expected: `AssertionError` because `_phase_closing` not implemented yet

- [ ] **Step 3: Implement _phase_closing**

在 `src/xiaoyao/adaptive_grasp/phase_controller.py` 的 `PhaseController` 类中，修改 `run` 方法并添加 `_phase_closing` 和相关辅助方法：

```python
    def run(self, force_planner: Optional[ForcePlanner], is_running: Callable[[], bool]) -> PhaseResult:
        for phase_method, name in (
            (self._phase_open, "OPEN"),
            (self._phase_pre_grasp, "PRE_GRASP"),
            (self._phase_closing, "CLOSING"),
        ):
            if not is_running():
                return PhaseResult(success=False, final_torque=self.current_torque)
            if not phase_method(force_planner, is_running):
                _logger.error("%s phase failed", name)
                return PhaseResult(success=False, final_torque=self.current_torque)
        return PhaseResult(success=True, final_torque=self.current_torque)

    def _phase_closing(self, force_planner: Optional[ForcePlanner], is_running: Callable[[], bool]) -> bool:
        self._set_state(GraspState.CLOSING_TO_CONTACT)
        start = self._get_monotonic_time()
        self.current_torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque))

        if joints_feedback := self._sensor.joint_feedback:
            self._safety.set_closing_baseline(joints_feedback)

        stall_counter = 0
        prev_angles: dict[JointId, float] = {}

        while is_running():
            if (self._get_monotonic_time() - start) > self.config.phase_timeout:
                _logger.error("CLOSING phase timeout")
                return False

            self.hand.move_joints(self._joint_builder.torque_command(self.current_torque), mode=CtrlMode.TORQUE)
            time.sleep(self.config.closing_period_s)

            tactile_data = self._sensor.tactile_data
            joint_feedback = self._sensor.joint_feedback
            if tactile_data is None or joint_feedback is None:
                _logger.error("CLOSING phase: failed to get %s", "tactile data" if tactile_data is None else "joint feedback")
                return False

            if self._safety.is_grasp_empty(joint_feedback, GraspState.CLOSING_TO_CONTACT).status != "OK":
                _logger.error("CLOSING phase: Grasp Empty")
                self._set_state(GraspState.ERROR)
                return False

            if self._sensor.sum_active_finger_normal_force() >= self.config.contact_threshold_z:
                self._calibrate_force(force_planner)
                time.sleep(self.config.control_period_s)
                return True

            current_angles = {j.id: j.angle for j in joint_feedback}
            if self._is_joints_stalled(prev_angles, current_angles):
                stall_counter += 1
                _logger.debug("CLOSING: joint stall detected (%d/%d)", stall_counter, self.config.closing_stall_cycles)
                if stall_counter >= self.config.closing_stall_cycles:
                    _logger.info("CLOSING: torque-stall contact confirmed")
                    self._calibrate_force(force_planner)
                    time.sleep(self.config.control_period_s)
                    return True
            else:
                stall_counter = 0
            prev_angles = current_angles

        return False

    def _is_joints_stalled(self, prev: dict[JointId, float], current: dict[JointId, float]) -> bool:
        if not prev or not current:
            return False
        for joint_id in self._joint_builder._torque_joints:
            delta = abs(current.get(joint_id, 0.0) - prev.get(joint_id, 0.0))
            if delta > self.config.closing_stall_angle_threshold:
                return False
        return True
```

注意：`_calibrate_force` 在 Task 4 中实现，这里先放一个空方法：

```python
    def _calibrate_force(self, force_planner: Optional[Any]) -> None:
        pass  # 将在 Task 4 实现
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/adaptive_grasp/test_phase_controller.py::test_phase_closing_contact_by_force -v`

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add tests/adaptive_grasp/test_phase_controller.py src/xiaoyao/adaptive_grasp/phase_controller.py
git commit -m "feat(adaptive_grasp): add CLOSING phase to PhaseController"
```

---

## Task 4: PhaseController 力校准

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/phase_controller.py`
- Modify: `tests/adaptive_grasp/test_phase_controller.py`

- [ ] **Step 1: Write failing tests**

在 `tests/adaptive_grasp/test_phase_controller.py` 末尾追加：

```python
from xiaoyao.adaptive_grasp.force_planner import ForcePlanner


def test_calibrate_force_increases_torque_when_below_target(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        pre_grasp_preset="two_finger_pinch",
        torque_adjust_step=5,
        base_holding_force=6.0,
    )
    sensor = MagicMock()
    safety = MagicMock()
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = PhaseController(
        hand, sensor, safety, joint_builder, cfg, time.monotonic,
        on_state_change=lambda s: None,
    )
    monkeypatch.setattr("xiaoyao.adaptive_grasp.phase_controller.time.sleep", lambda *_: None)

    sensor.sum_active_finger_normal_force.return_value = 1.0  # below target
    controller.current_torque = 10
    force_planner = ForcePlanner(cfg, None)

    controller._calibrate_force(force_planner)

    assert controller.current_torque > 10
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/adaptive_grasp/test_phase_controller.py::test_calibrate_force_increases_torque_when_below_target -v`

Expected: FAIL because `_calibrate_force` is a no-op

- [ ] **Step 3: Implement _calibrate_force**

替换 `src/xiaoyao/adaptive_grasp/phase_controller.py` 中的 `_calibrate_force` 空方法：

```python
    def _calibrate_force(self, force_planner: Optional[ForcePlanner]) -> None:
        if force_planner is None:
            return
        F_init = force_planner.F_init
        if F_init <= 0:
            return
        tolerance = getattr(self.config, 'force_calibrate_tolerance', 1.0)
        for _ in range(5):
            total_fz = self._sensor.sum_active_finger_normal_force()
            if abs(total_fz - F_init) <= tolerance:
                break
            step = self.config.torque_adjust_step
            if force_planner.is_fragile_mode:
                step = int(step * self.config.fragile_step_reduction)
            if total_fz < F_init:
                self.current_torque = int(clip(self.current_torque + step, -100.0, self.config.max_torque))
            else:
                self.current_torque = int(clip(self.current_torque - step, -100.0, self.config.max_torque))
            joints = self._joint_builder.torque_command(self.current_torque)
            if not self.hand.move_joints(joints, mode=CtrlMode.TORQUE):
                _logger.error("FORCE_CALIBRATION: move_joints failed")
                break
            time.sleep(self.config.control_period_s)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/adaptive_grasp/test_phase_controller.py::test_calibrate_force_increases_torque_when_below_target -v`

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add tests/adaptive_grasp/test_phase_controller.py src/xiaoyao/adaptive_grasp/phase_controller.py
git commit -m "feat(adaptive_grasp): add force calibration to PhaseController"
```

---

## Task 5: HoldController 框架

**Files:**
- Create: `tests/adaptive_grasp/test_hold_controller.py`
- Create: `src/xiaoyao/adaptive_grasp/hold_controller.py`

- [ ] **Step 1: Write failing tests**

创建 `tests/adaptive_grasp/test_hold_controller.py`：

```python
import time
from unittest.mock import MagicMock
import pytest
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig, GraspState
from xiaoyao.adaptive_grasp.hold_controller import HoldController, HoldResult, HoldStepResult
from xiaoyao.adaptive_grasp.joint_builder import JointCommandBuilder
from xiaoyao.adaptive_grasp.tactility import TactileAnalysis
from xiaoyao.adaptive_grasp.safety import SafetyReport, SafetyStatus
from xiaoyao.dexhand import CtrlMode, JointId, TactileSensorId


class _MockHand:
    def __init__(self):
        self.calls = []

    def move_joints(self, joints, mode=None):
        self.calls.append({"mode": mode, "joints": list(joints)})
        return True


def test_hold_step_sends_position_payload_with_config_limits(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(
        position_speed_limit=17,
        position_torque_limit=29,
        variance_threshold=0.1,
        max_normal_force_per_finger=1.0,
    )
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.5, slip_risk=1.0, direction_distance=0.0,
        friction_utilization=0.0, slip_confirmed=True,
        finger_fz={}, total_fz=0.4,
    )
    force_planner = MagicMock()
    force_planner.compute.return_value = {}
    visualizer = None
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP, JointId.FF_PIP))
    controller = HoldController(
        hand, sensor, safety, tactile, force_planner, visualizer,
        joint_builder, cfg, current_torque=10, get_time=time.monotonic,
    )

    result = controller.run_step(current_time=0.0)

    assert result.result == HoldResult.CONTINUE
    assert len(hand.calls) == 1
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
    for joint in hand.calls[0]["joints"]:
        assert joint.speed == cfg.position_speed_limit
        assert 0 <= joint.torque <= cfg.position_torque_limit
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/adaptive_grasp/test_hold_controller.py::test_hold_step_sends_position_payload_with_config_limits -v`

Expected: `ModuleNotFoundError: No module named 'xiaoyao.adaptive_grasp.hold_controller'`

- [ ] **Step 3: Implement HoldController**

创建 `src/xiaoyao/adaptive_grasp/hold_controller.py`：

```python
import logging
from enum import auto, Enum
from dataclasses import dataclass
from typing import Any, Callable, Optional

from xiaoyao.dexhand import CtrlMode, DexHand, JointId
from .config import AdaptiveGraspConfig
from .sensor import SensorClient
from .safety import SafetyMonitor, SafetyStatus
from .tactility import TactileAnalyzer, TactileAnalysis
from .force_planner import ForcePlanner, ForceDecision
from .visualization import TactileVisualizer
from .joint_builder import JointCommandBuilder

_logger = logging.getLogger("xiaoyao.adaptive_grasp.hold_controller")


class HoldResult(Enum):
    CONTINUE = auto()
    AUTO_RELEASE = auto()
    FAULT_RELEASE = auto()
    ERROR = auto()


@dataclass
class HoldStepResult:
    result: HoldResult
    tactile_analysis: Optional[TactileAnalysis] = None
    safety_report: Optional[Any] = None
    force_decisions: Optional[dict] = None


class HoldController:
    def __init__(
        self,
        hand: DexHand,
        sensor: SensorClient,
        safety: SafetyMonitor,
        tactile: TactileAnalyzer,
        force_planner: Optional[ForcePlanner],
        visualizer: Optional[TactileVisualizer],
        joint_builder: JointCommandBuilder,
        config: AdaptiveGraspConfig,
        current_torque: int,
        get_time: Callable[[], float],
    ):
        self.hand = hand
        self._sensor = sensor
        self._safety = safety
        self._tactile = tactile
        self._force_planner = force_planner
        self._visualizer = visualizer
        self._joint_builder = joint_builder
        self.config = config
        self._current_torque = current_torque
        self._get_monotonic_time = get_time
        self._consecutive_move_failures = 0
        self._max_consecutive_move_failures = 3

    def run_step(self, current_time: float) -> HoldStepResult:
        tactile_data = self._sensor.tactile_data
        joint_feedback = self._sensor.joint_feedback

        # 1) 安全检查
        safety = self._safety.check(tactile_data, joint_feedback, GraspState.ADAPTIVE_HOLD)
        if safety.status == SafetyStatus.FAULT:
            if self.config.enable_fault_release_fallback:
                return HoldStepResult(result=HoldResult.FAULT_RELEASE, safety_report=safety)
            return HoldStepResult(result=HoldResult.ERROR, safety_report=safety)

        if tactile_data is None:
            return HoldStepResult(result=HoldResult.CONTINUE, safety_report=safety)

        # 2) 触觉分析
        analysis = self._tactile.update(tactile_data)

        # 3) 力规划
        current_angles = self._get_current_angles(joint_feedback)
        if self._visualizer is not None and tactile_data is not None:
            self._visualizer.update(tactile_data, analysis, joint_angles=current_angles, timestamp=current_time)

        if self._force_planner is not None:
            decisions = self._force_planner.compute(analysis, current_angles)
            next_angles = dict(current_angles)
            for decision in decisions.values():
                next_angles.update(decision.target_angles)
            next_torque = next(iter(decisions.values())).next_torque if decisions else self._current_torque
        else:
            next_angles = current_angles
            next_torque = self._current_torque

        # 4) 执行
        joints = self._joint_builder.hold_position_command(next_torque, next_angles)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if not ok:
            self._consecutive_move_failures += 1
            _logger.error(
                "ADAPTIVE_HOLD: move_joints failed (%d/%d)",
                self._consecutive_move_failures,
                self._max_consecutive_move_failures,
            )
            if self._consecutive_move_failures >= self._max_consecutive_move_failures:
                return HoldStepResult(result=HoldResult.ERROR, tactile_analysis=analysis, safety_report=safety)
        else:
            self._consecutive_move_failures = 0

        return HoldStepResult(
            result=HoldResult.CONTINUE,
            tactile_analysis=analysis,
            safety_report=safety,
            force_decisions=decisions if self._force_planner else None,
        )

    def _get_current_angles(self, joint_feedback: Optional[list]) -> dict[JointId, float]:
        if joint_feedback:
            return {j.id: j.angle for j in joint_feedback}
        return self._joint_builder.init_hold_angles()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/adaptive_grasp/test_hold_controller.py::test_hold_step_sends_position_payload_with_config_limits -v`

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add tests/adaptive_grasp/test_hold_controller.py src/xiaoyao/adaptive_grasp/hold_controller.py
git commit -m "feat(adaptive_grasp): extract HoldController from controller"
```

---

## Task 6: HoldController 安全检查和自动释放

**Files:**
- Modify: `tests/adaptive_grasp/test_hold_controller.py`
- Modify: `src/xiaoyao/adaptive_grasp/hold_controller.py`

- [ ] **Step 1: Write failing tests**

在 `tests/adaptive_grasp/test_hold_controller.py` 末尾追加：

```python
def test_hold_step_fault_triggers_release(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(enable_fault_release_fallback=True)
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.FAULT)
    tactile = MagicMock()
    force_planner = None
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, force_planner, None,
        joint_builder, cfg, current_torque=10, get_time=time.monotonic,
    )

    result = controller.run_step(current_time=0.0)

    assert result.result == HoldResult.FAULT_RELEASE


def test_hold_step_fault_without_fallback_triggers_error(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(enable_fault_release_fallback=False)
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.FAULT)
    tactile = MagicMock()
    force_planner = None
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, force_planner, None,
        joint_builder, cfg, current_torque=10, get_time=time.monotonic,
    )

    result = controller.run_step(current_time=0.0)

    assert result.result == HoldResult.ERROR


def test_hold_step_error_after_consecutive_failures(monkeypatch):
    hand = _MockHand()
    hand.move_joints = lambda *args, **kwargs: False
    cfg = AdaptiveGraspConfig(control_period_s=0.01)
    sensor = MagicMock()
    safety = MagicMock()
    safety.check.return_value = SafetyReport(SafetyStatus.OK)
    tactile = MagicMock()
    tactile.update.return_value = TactileAnalysis(
        variance=0.0, slip_risk=0.0, direction_distance=0.0,
        friction_utilization=0.0, slip_confirmed=False,
        finger_fz={}, total_fz=0.0,
    )
    force_planner = None
    joint_builder = JointCommandBuilder(cfg, (JointId.THUMB_PIP,))
    controller = HoldController(
        hand, sensor, safety, tactile, force_planner, None,
        joint_builder, cfg, current_torque=10, get_time=time.monotonic,
    )

    assert controller.run_step(0.0).result == HoldResult.CONTINUE
    assert controller.run_step(0.0).result == HoldResult.CONTINUE
    assert controller.run_step(0.0).result == HoldResult.ERROR
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/adaptive_grasp/test_hold_controller.py -v`

Expected: 3 passed for new tests (fault + no fallback + consecutive failures) — assuming implementation from Task 5 already handles these paths

如果失败，修复 `hold_controller.py` 中对应逻辑。

- [ ] **Step 3: 确认/修复实现**

Task 5 的实现已经包含了 safety fault 和 consecutive failures 的处理，所以这一步主要是验证。如果有 bug，修复。

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/adaptive_grasp/test_hold_controller.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/adaptive_grasp/test_hold_controller.py src/xiaoyao/adaptive_grasp/hold_controller.py
git commit -m "test(adaptive_grasp): add safety and failure tests for HoldController"
```

---

## Task 7: AdaptiveGrasper 重构（使用新子模块）

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/controller.py`
- Modify: `tests/adaptive_grasp/test_controller.py`

- [ ] **Step 1: 重构 controller.py**

重写 `src/xiaoyao/adaptive_grasp/controller.py`。保留公共 API，内部使用 `JointCommandBuilder`、`PhaseController`、`HoldController`。

```python
import logging
import math
import threading
import time
from typing import Any, Callable, Optional

from xiaoyao.dexhand import CtrlMode, DexHand, Joint, JointId, TactileSensorId
from .sensor import SensorClient

from .config import AdaptiveGraspConfig
from .states import GraspState
from .tactility import TactileAnalyzer, TactileAnalysis
from .object_profile import ObjectProfile, ObjectProfileRegistry
from .force_planner import ForcePlanner, ForceDecision
from .safety import SafetyMonitor, SafetyStatus, SafetyReport
from .visualization import TactileVisualizer
from .utils import clip, JOINT_TO_FINGER
from .joint_builder import JointCommandBuilder
from .phase_controller import PhaseController, PhaseResult
from .hold_controller import HoldController, HoldResult, HoldStepResult

_logger = logging.getLogger("xiaoyao.adaptive_grasp.controller")


class AdaptiveGrasper:
    _TORQUE_JOINTS = (
        JointId.THUMB_PIP, JointId.THUMB_MCP,
        JointId.FF_PIP, JointId.FF_MCP,
        JointId.MF_PIP, JointId.MF_MCP,
        JointId.RF_PIP, JointId.RF_MCP,
        JointId.LF_PIP, JointId.LF_MCP,
    )

    def __init__(self, hand: DexHand, config: Optional[AdaptiveGraspConfig] = None):
        self.hand = hand
        self.config = config or AdaptiveGraspConfig()
        self.state = GraspState.IDLE
        self.current_torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque))
        self._running = False
        self._control_thread: Optional[threading.Thread] = None
        self._adaptive_hold_started_at: Optional[float] = None
        self._get_monotonic_time = time.monotonic

        self._torque_joints = tuple(
            j for j in AdaptiveGrasper._TORQUE_JOINTS
            if JOINT_TO_FINGER.get(j) in self.config.active_fingers
        )

        self._sensor = SensorClient(
            hand,
            active_fingers=set(self.config.active_fingers),
            get_monotonic_time=self._get_monotonic_time,
        )

        self._tactile = TactileAnalyzer(self.config)
        self._safety = SafetyMonitor(self.config)
        self._force_planner: Optional[ForcePlanner] = None
        self._object_profile: Optional[ObjectProfile] = None
        self._visualizer: Optional[TactileVisualizer] = None
        if self.config.enable_visualization:
            self._visualizer = TactileVisualizer(
                active_fingers=set(self.config.active_fingers),
                backend=self.config.visualization_backend,
            )

        self._joint_builder = JointCommandBuilder(self.config, self._torque_joints)
        self._phase_controller: Optional[PhaseController] = None
        self._hold_controller: Optional[HoldController] = None

        self._last_tactile_analysis: Optional[TactileAnalysis] = None
        self._last_safety_report: Optional[SafetyReport] = None
        self._last_force_decisions: Optional[dict[TactileSensorId, ForceDecision]] = None
        self._last_tactile_data_age_s: Optional[float] = None
        self._last_control_step_start_s: Optional[float] = None
        self._last_control_cycle_s: Optional[float] = None
        self._last_control_cycle_jitter_s: Optional[float] = None

    def grasp_core(self, object_profile: Optional[ObjectProfile] = None) -> bool:
        try:
            self._running = True
            self._reset_runtime_state()
            self._object_profile = object_profile or ObjectProfileRegistry.get(self.config.default_object)
            self._force_planner = ForcePlanner(self.config, self._object_profile)
            self._tactile.set_friction_coeff(
                self._object_profile.friction_coeff if self._object_profile else self.config.default_friction_coeff,
            )
            self._start_sensor_subscription()

            self._phase_controller = PhaseController(
                self.hand, self._sensor, self._safety, self._joint_builder,
                self.config, self._get_monotonic_time, on_state_change=self._set_state,
            )
            result = self._phase_controller.run(self._force_planner, lambda: self._running)
            if not result.success:
                self._cleanup_grasp()
                return False
            self.current_torque = result.final_torque

            self._start_adaptive_control()
            return True
        except KeyboardInterrupt:
            self._cleanup_grasp(state=GraspState.STOPPED)
            raise
        except Exception:
            _logger.exception("grasp_core exception")
            self._cleanup_grasp(state=GraspState.ERROR)
            return False

    def _set_state(self, state: GraspState) -> None:
        self.state = state

    def _cleanup_grasp(self, state: GraspState = GraspState.STOPPED) -> None:
        self._running = False
        self._stop_sensor_subscription()
        if state != GraspState.STOPPED:
            self.state = state

    def release(self) -> bool:
        return self._perform_release(wait_control_thread=True)

    def stop(self) -> None:
        self._running = False
        self._stop_sensor_subscription()
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)
        if self._visualizer is not None:
            self._visualizer.stop()
        self.hand.stop()
        self.state = GraspState.STOPPED

    def stop_visualizer(self) -> None:
        if self._visualizer is not None:
            self._visualizer.stop()

    def get_state(self) -> GraspState:
        return self.state

    @property
    def last_tactile_analysis(self) -> Optional[TactileAnalysis]:
        return self._last_tactile_analysis

    @property
    def last_safety_report(self) -> Optional[SafetyReport]:
        return self._last_safety_report

    @property
    def last_force_decisions(self) -> Optional[dict[TactileSensorId, ForceDecision]]:
        return self._last_force_decisions

    @property
    def last_tactile_data_age_s(self) -> Optional[float]:
        return self._last_tactile_data_age_s

    @property
    def last_control_cycle_s(self) -> Optional[float]:
        return self._last_control_cycle_s

    @property
    def last_control_cycle_jitter_s(self) -> Optional[float]:
        return self._last_control_cycle_jitter_s

    def _start_adaptive_control(self) -> None:
        self.state = GraspState.ADAPTIVE_HOLD
        self._adaptive_hold_started_at = self._get_monotonic_time()
        self._hold_controller = HoldController(
            self.hand, self._sensor, self._safety, self._tactile,
            self._force_planner, self._visualizer, self._joint_builder,
            self.config, self.current_torque, self._get_monotonic_time,
        )
        self._control_thread = threading.Thread(target=self._adaptive_control_loop, daemon=True)
        self._control_thread.start()
        if self._visualizer is not None:
            self._visualizer.start()

    def _adaptive_control_loop(self) -> None:
        while self._running:
            step_start = self._get_monotonic_time()
            if self._last_control_step_start_s is not None:
                control_cycle_s = step_start - self._last_control_step_start_s
                self._last_control_cycle_s = control_cycle_s
                self._last_control_cycle_jitter_s = control_cycle_s - self.config.control_period_s
            self._last_control_step_start_s = step_start

            if self._should_auto_release():
                self._perform_release(wait_control_thread=False)
                break

            step = self._hold_controller.run_step(step_start)
            self._last_tactile_analysis = step.tactile_analysis
            self._last_safety_report = step.safety_report
            self._last_force_decisions = step.force_decisions

            tactile_data = self._sensor.tactile_data
            self._last_tactile_data_age_s = self._sensor.data_age_s(step_start) if tactile_data is not None else None

            if step.result == HoldResult.AUTO_RELEASE:
                self._perform_release(wait_control_thread=False)
                break
            elif step.result == HoldResult.FAULT_RELEASE:
                self._perform_release(wait_control_thread=False)
                break
            elif step.result == HoldResult.ERROR:
                self.state = GraspState.ERROR
                self._running = False
                break

            time.sleep(self.config.control_period_s)

    def _should_auto_release(self) -> bool:
        if self._adaptive_hold_started_at is None:
            return False
        elapsed = self._get_monotonic_time() - self._adaptive_hold_started_at
        return elapsed >= self.config.release_hold_time_s

    def _perform_release(self, wait_control_thread: bool) -> bool:
        self.state = GraspState.RELEASE
        self._running = False
        self._adaptive_hold_started_at = None
        self._stop_sensor_subscription()

        control_thread = self._control_thread
        if (
            wait_control_thread
            and control_thread
            and control_thread.is_alive()
            and control_thread is not threading.current_thread()
        ):
            control_thread.join(timeout=2.0)

        joints = self._joint_builder.position_command(
            self._joint_builder.open_pose(),
            speed=self.config.release_open_speed,
            torque=self.config.release_open_torque,
        )
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if not ok:
            _logger.error("RELEASE phase: move_joints failed")
            self.state = GraspState.ERROR
            return False

        target_pose = self._joint_builder.open_pose()
        feedback_supported = callable(getattr(self.hand, "get_joints", None))
        if feedback_supported:
            if self._wait_joints_settled(
                target_pose,
                self.config.theta_err_th,
                self.config.release_check_cycles,
                self.config.release_timeout_s,
            ):
                self.state = GraspState.COMPLETED
                return True
            self.state = GraspState.ERROR
            return False
        self.state = GraspState.COMPLETED if ok else GraspState.ERROR
        return ok

    def _wait_joints_settled(
        self,
        target_pose: dict[JointId, float],
        theta_err_th: float,
        check_cycles: int,
        timeout_s: float,
    ) -> bool:
        settled_cycles = 0
        start = self._get_monotonic_time()
        while (self._get_monotonic_time() - start) < timeout_s:
            joints_feedback = self._sensor.joint_feedback
            if joints_feedback is None:
                _logger.error("Joint feedback lost during settle wait")
                return False
            actual = {j.id: j.angle for j in joints_feedback}
            is_settled = all(
                joint_id in actual and abs(actual[joint_id] - target_angle) <= theta_err_th
                for joint_id, target_angle in target_pose.items()
            )
            if is_settled:
                settled_cycles += 1
                if settled_cycles >= check_cycles:
                    return True
            else:
                settled_cycles = 0
            time.sleep(self.config.control_period_s)
        _logger.error("Joint settle wait timeout")
        return False

    def _start_sensor_subscription(self) -> None:
        self._sensor.start()

    def _stop_sensor_subscription(self) -> None:
        self._sensor.stop(clear_joint_feedback=False)

    def _reset_runtime_state(self) -> None:
        self._tactile.reset()
        self._safety.reset()
        if self._force_planner is not None:
            self._force_planner.reset()
        self.current_torque = int(clip(self.config.base_torque, -100.0, self.config.max_torque))
        self._adaptive_hold_started_at = None
        self._last_tactile_analysis = None
        self._last_safety_report = None
        self._last_force_decisions = None
        self._last_tactile_data_age_s = None
        self._last_control_step_start_s = None
        self._last_control_cycle_s = None
        self._last_control_cycle_jitter_s = None
        self._object_profile = None
        self._force_planner = None
        self._phase_controller = None
        self._hold_controller = None
        self._sensor.reset()
```

- [ ] **Step 2: 迁移并更新集成测试**

修改 `tests/adaptive_grasp/test_controller.py`：

1. 删除所有直接测试 `_run_control_step`、`_phase_closing`、`_calibrate_force`、`_build_torque_joints` 的测试（这些已在对应模块的测试文件中覆盖）
2. 保留并更新集成测试（`test_release_waits_until_joints_settled`、`test_perform_release_waits_for_control_thread`、`test_perform_release_from_control_thread_does_not_deadlock`、`test_full_grasp_state_transitions`、`test_full_grasp_lifecycle`、`test_controller_accepts_none_config`、`test_sensor_subscription_callback_updates_cache`）
3. 对于 monkeypatch 内部方法的集成测试，改为 monkeypatch sensor 缓存

关键改动示例（以 `test_full_grasp_state_transitions` 为例）：

```python
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
    monkeypatch.setattr(grasper._sensor, "sum_active_finger_normal_force", lambda: 4.0)
    # 直接修改 sensor 缓存，替代原来 monkeypatch _safe_get_tactile_data
    grasper._sensor._latest_tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 2.0),
        TactileSensorId.FOREFINGER: _FakeTactileInfo(0.0, 0.0, 2.0),
    }
    grasper._sensor._latest_joint_feedback = []

    assert grasper.grasp_core() is True
    assert grasper.state == GraspState.ADAPTIVE_HOLD

    time.sleep(0.1)
    grasper.release()
    assert grasper.state in (GraspState.COMPLETED, GraspState.RELEASE)
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/adaptive_grasp/ -v`

Expected: 所有测试通过（controller + joint_builder + phase_controller + hold_controller + 其他模块的现有测试）

- [ ] **Step 4: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/controller.py tests/adaptive_grasp/test_controller.py
git commit -m "refactor(adaptive_grasp): slim down AdaptiveGrasper using new submodules"
```

---

## Self-Review

**1. Spec coverage:**
- [x] 模块拆分（JointCommandBuilder / PhaseController / HoldController）→ Task 1/2/3/4/5/6
- [x] 公共 API 不变 → Task 7 保留原有方法签名
- [x] HoldController 不管理线程 → Task 5/6 中 HoldController 只有 `run_step`
- [x] PhaseController 返回 `PhaseResult` → Task 2/3/4
- [x] HoldController 返回 `HoldStepResult` → Task 5/6
- [x] 状态属性归属明确 → Task 7 中 AdaptiveGrasper 同步 `_last_*`
- [x] 测试迁移 → Task 7 Step 2

**2. Placeholder scan:**
- [x] 无 TBD/TODO
- [x] 所有测试包含完整代码
- [x] 所有实现包含完整代码
- [x] 无 "Similar to Task N" 引用

**3. Type consistency:**
- [x] `PhaseResult` 在 Task 2 定义，Task 3/4/7 使用一致
- [x] `HoldResult` / `HoldStepResult` 在 Task 5 定义，Task 6/7 使用一致
- [x] `JointCommandBuilder` 方法名在 Task 1 定义，后续 task 使用一致

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-28-controller-refactor.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints for review

Which approach?
