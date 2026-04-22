# Adaptive Grasp V2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `controller.py` to integrate `tactility.py`, `force_planner.py`, and `safety.py` submodules, fix module naming mismatch, and make all tests pass.

**Architecture:** Keep the existing state machine in `controller.py` but delegate perception (tactile), control (force planning), and safety monitoring to focused submodules. Create a `tactile.py` compatibility shim so existing tests can import from the expected module path.

**Tech Stack:** Python 3.12, pytest, dataclasses

---

## File Map

| File | Responsibility |
|:---|:---|
| `src/xiaoyao/adaptive_grasp/tactile.py` | Compatibility shim — re-exports `TactileAnalyzer`, `TactileAnalysis`, `PerFingerAnalysis` from `tactility.py` |
| `src/xiaoyao/adaptive_grasp/controller.py` | State machine orchestrator. Integrates `TactileAnalyzer`, `ForcePlanner`, `SafetyMonitor`. No direct DexHand logic beyond move_joints calls. |
| `src/xiaoyao/adaptive_grasp/__init__.py` | Public exports for the package |
| `tests/adaptive_grasp/test_controller.py` | Updated integration tests for the refactored controller |

---

### Task 1: Create `tactile.py` compatibility shim

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/tactile.py`

- [ ] **Step 1: Write the shim**

```python
from .tactility import (
    TactileAnalyzer,
    TactileAnalysis,
    PerFingerAnalysis,
)

__all__ = [
    "TactileAnalyzer",
    "TactileAnalysis",
    "PerFingerAnalysis",
]
```

- [ ] **Step 2: Verify existing tests can now import**

Run: `python -m pytest tests/adaptive_grasp/test_tactile.py tests/adaptive_grasp/test_force_planner.py tests/adaptive_grasp/test_safety.py -v`

Expected: All tests in those three files PASS (test_controller.py may still fail if it imports controller internals).

- [ ] **Step 3: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/tactile.py
git commit -m "feat(adaptive_grasp): add tactile.py compatibility shim for tactility exports"
```

---

### Task 2: Update `__init__.py` public exports

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/__init__.py`

- [ ] **Step 1: Write the updated exports**

```python
from .states import GraspState
from .config import AdaptiveGraspConfig
from .controller import AdaptiveGrasper
from .tactility import TactileAnalyzer, TactileAnalysis, PerFingerAnalysis
from .force_planner import ObjectProfile, ObjectProfileRegistry, ForcePlanner, ForceDecision
from .safety import SafetyMonitor, SafetyStatus, SafetyReport

__all__ = [
    "GraspState",
    "AdaptiveGraspConfig",
    "AdaptiveGrasper",
    "TactileAnalyzer",
    "TactileAnalysis",
    "PerFingerAnalysis",
    "ObjectProfile",
    "ObjectProfileRegistry",
    "ForcePlanner",
    "ForceDecision",
    "SafetyMonitor",
    "SafetyStatus",
    "SafetyReport",
]
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from xiaoyao.adaptive_grasp import *; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/__init__.py
git commit -m "feat(adaptive_grasp): update __init__.py with V2.0 public exports"
```

---

### Task 3: Refactor `controller.py` to integrate submodules

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/controller.py`

**Background:** Current `controller.py` is V1.0. It embeds its own variance calculation, PID state, and torque adjustment. V2.0 moves all of that into `tactility.py`, `force_planner.py`, and `safety.py`. The controller becomes a thin orchestrator.

Key changes:
1. `__init__` instantiates `TactileAnalyzer`, `SafetyMonitor`, and optionally `ForcePlanner`
2. `_run_control_step` delegates to submodules in order: safety check → tactile analysis → force planning → move_joints
3. `_phase_closing` adds force calibration after initial contact (match `F_init` within ±2N)
4. `grasp` accepts an optional `object_profile: ObjectProfile | None`

- [ ] **Step 1: Write the failing integration test**

**Files:**
- Modify: `tests/adaptive_grasp/test_controller.py` (prepend new test)

```python
def test_controller_runs_full_state_machine_with_submodules(monkeypatch):
    """Smoke test: controller should use submodules and reach ADAPTIVE_HOLD."""
    from xiaoyao.adaptive_grasp import AdaptiveGrasper, AdaptiveGraspConfig, GraspState
    from xiaoyao.adaptive_grasp.force_planner import ObjectProfile

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

    # Patch sleep so test runs fast
    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)
    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.monotonic", lambda: 0.0)

    # Force immediate release by making _should_auto_release True after one step
    call_count = [0]
    orig_should_release = grasper._should_auto_release
    def fake_should_release():
        call_count[0] += 1
        return call_count[0] > 2
    monkeypatch.setattr(grasper, "_should_auto_release", fake_should_release)

    ok = grasper.grasp(object_profile=profile)
    assert ok is True
    assert grasper.state in (GraspState.ADAPTIVE_HOLDING, GraspState.COMPLETED, GraspState.RELEASING)
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `pytest tests/adaptive_grasp/test_controller.py::test_controller_runs_full_state_machine_with_submodules -v`

Expected: FAIL because `AdaptiveGrasper.__init__` doesn't accept `object_profile` and `_run_control_step` doesn't integrate submodules.

- [ ] **Step 3: Refactor controller.py**

Replace the entire `controller.py` with the V2.0 orchestrator. Keep existing public API (`grasp()`, `release()`, `stop()`, `get_state()`). Internal methods can change.

```python
import math
import threading
import time
from typing import Any, Mapping, Optional

from xiaoyao.dexhand import CtrlMode, DexHand, Joint, JointId, TactileSensorId

from .config import AdaptiveGraspConfig
from .states import GraspState
from .tactility import TactileAnalyzer
from .force_planner import ForcePlanner, ObjectProfile, ObjectProfileRegistry
from .safety import SafetyMonitor, SafetyStatus


class AdaptiveGrasper:
    _HOLD_CLOSURE_STEP_PER_TORQUE = math.radians(0.5)
    _HOLD_CLOSURE_MAX_DELTA = math.radians(20.0)
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
        self.current_torque = int(self._clamp_torque(self.config.base_torque))
        self._running = False
        self._control_thread: Optional[threading.Thread] = None
        self._adaptive_hold_started_at: Optional[float] = None
        self._get_monotonic_time = time.monotonic

        # Submodules
        self._tactile = TactileAnalyzer(self.config)
        self._safety = SafetyMonitor(self.config)
        self._force_planner: Optional[ForcePlanner] = None
        self._object_profile: Optional[ObjectProfile] = None

    def grasp(self, object_profile: Optional[ObjectProfile] = None) -> bool:
        try:
            self._running = True
            self._reset_runtime_state()
            self._object_profile = object_profile
            if object_profile is not None:
                self._force_planner = ForcePlanner(self.config, object_profile)
                self._tactile.set_friction_coeff(object_profile.friction_coeff)
            else:
                self._force_planner = ForcePlanner(self.config, None)
                self._tactile.set_friction_coeff(self.config.default_friction_coeff)

            if not self._phase_open():
                self._running = False
                return False
            if not self._phase_pre_grasp():
                self._running = False
                return False
            if not self._phase_closing():
                self._running = False
                return False

            self._start_adaptive_control()
            return True
        except Exception:
            self.state = GraspState.ERROR
            self._running = False
            return False

    def release(self) -> bool:
        return self._perform_release(join_control_thread=True)

    def stop(self) -> None:
        self._running = False
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)
        self.hand.stop()
        self.state = GraspState.STOPPED

    def get_state(self) -> GraspState:
        return self.state

    # ------------------------------------------------------------------
    # Phases
    # ------------------------------------------------------------------
    def _phase_open(self) -> bool:
        self.state = GraspState.OPENING
        joints = self._build_position_joints(self._get_open_pose(), speed=20, torque=20)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(2)
        return ok

    def _phase_pre_grasp(self) -> bool:
        self.state = GraspState.PRE_GRASPING
        joints = self._build_position_joints(self.config.pre_grasp_pose, speed=50, torque=50)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            time.sleep(5)
        return ok

    def _phase_closing(self) -> bool:
        self.state = GraspState.CLOSING_TO_CONTACT
        start = time.time()
        torque = int(self._clamp_torque(self.config.base_torque))
        self.current_torque = torque

        while self._running:
            if (time.time() - start) > self.config.phase_timeout:
                return False

            joints = self._build_torque_joints(self.current_torque)
            if not self.hand.move_joints(joints, mode=CtrlMode.TORQUE):
                return False

            tactile_data = self._safe_get_tactile_data()
            if tactile_data:
                total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
                if total_fz >= self.config.contact_threshold_z:
                    # Force calibration before entering ADAPTIVE_HOLD
                    self._calibrate_force(tactile_data)
                    return True

                # Safety: empty grasp check
                safety = self._safety.check(tactile_data, None, self.state)
                if safety.status == SafetyStatus.FAULT:
                    self.state = GraspState.ERROR
                    return False

            time.sleep(self.config.control_period_s)

        return False

    def _calibrate_force(self, tactile_data: dict) -> None:
        """Match total normal force to F_init within ±2N using 1-2 torque steps."""
        if self._force_planner is None:
            return
        F_init = self._force_planner.F_init
        if F_init <= 0:
            return
        for _ in range(2):
            total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
            if abs(total_fz - F_init) <= 2.0:
                break
            if total_fz < F_init:
                step = self.config.torque_adjust_step
                if self._force_planner.is_fragile_mode:
                    step = int(step * self.config.fragile_step_reduction)
                self.current_torque = int(self._clamp_torque(self.current_torque + step))
            else:
                step = self.config.torque_adjust_step
                if self._force_planner.is_fragile_mode:
                    step = int(step * self.config.fragile_step_reduction)
                self.current_torque = int(self._clamp_torque(self.current_torque - step))
            joints = self._build_torque_joints(self.current_torque)
            self.hand.move_joints(joints, mode=CtrlMode.TORQUE)
            time.sleep(self.config.control_period_s)
            tactile_data = self._safe_get_tactile_data() or tactile_data

    # ------------------------------------------------------------------
    # ADAPTIVE_HOLD
    # ------------------------------------------------------------------
    def _start_adaptive_control(self) -> None:
        self.state = GraspState.ADAPTIVE_HOLDING
        self._adaptive_hold_started_at = self._get_monotonic_time()
        # Set baseline angles from current joint feedback if available
        joints_feedback = self._safe_get_joints()
        if joints_feedback:
            baseline = {j.id: j.angle for j in joints_feedback}
        else:
            baseline = self._init_hold_joint_angles()
        if self._force_planner is not None:
            self._force_planner.set_baseline_angles(baseline)
        self._control_thread = threading.Thread(target=self._adaptive_control_loop, daemon=True)
        self._control_thread.start()

    def _adaptive_control_loop(self) -> None:
        while self._running:
            self._run_control_step()
            time.sleep(self.config.control_period_s)

    def _run_control_step(self) -> bool:
        if self._should_auto_release():
            return self._perform_release(join_control_thread=False)

        tactile_data = self._safe_get_tactile_data()
        joint_feedback = self._safe_get_joints()

        # 1) Safety check
        safety = self._safety.check(tactile_data, joint_feedback, self.state)
        if safety.status == SafetyStatus.FAULT:
            if self.config.enable_fault_release_fallback:
                return self._perform_release(join_control_thread=False)
            self.state = GraspState.ERROR
            self._running = False
            return False

        if tactile_data is None:
            return True  # WARN handled by safety, keep previous pose

        # 2) Tactile analysis
        analysis = self._tactile.update(tactile_data)

        # 3) Force planning
        current_angles = self._get_current_angles(joint_feedback)
        if self._force_planner is not None:
            decision = self._force_planner.compute(analysis, current_angles)
            next_angles = decision.target_angles
            next_torque = decision.next_torque
        else:
            # Fallback to V1.0-like behavior if no planner
            next_angles = current_angles
            next_torque = self.current_torque

        # 4) Execute
        joints = self._build_hold_position_joints(next_torque, next_angles)
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        return ok

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _safe_get_tactile_data(self):
        try:
            return self.hand.get_tactile_data()
        except Exception:
            return None

    def _safe_get_joints(self):
        get_joints = getattr(self.hand, "get_joints", None)
        if not callable(get_joints):
            return None
        try:
            return get_joints()
        except Exception:
            return None

    def _get_current_angles(self, joint_feedback: Optional[list]) -> dict[JointId, float]:
        if joint_feedback:
            return {j.id: j.angle for j in joint_feedback}
        return self._init_hold_joint_angles()

    def _build_torque_joints(self, torque: int) -> list[Joint]:
        return [Joint(id=joint_id, torque=torque) for joint_id in self._TORQUE_JOINTS]

    def _init_hold_joint_angles(self) -> dict[JointId, float]:
        return {
            joint_id: self.config.pre_grasp_pose.get(joint_id, 0.0)
            for joint_id in self._TORQUE_JOINTS
        }

    def _reset_runtime_state(self) -> None:
        self._tactile.reset()
        self._safety.reset()
        if self._force_planner is not None:
            self._force_planner.reset()
        self.current_torque = int(self._clamp_torque(self.config.base_torque))
        self._adaptive_hold_started_at = None

    def _build_position_joints(
        self,
        joint_angles: dict[JointId, float],
        speed: int = 100,
        torque: int = 100,
    ) -> list[Joint]:
        joints: list[Joint] = []
        for joint_id, angle in joint_angles.items():
            joints.append(Joint(id=joint_id, angle=angle, speed=speed, torque=torque))
        return joints

    def _build_hold_position_joints(
        self,
        torque_value: Optional[int] = None,
        hold_joint_angles: Optional[Mapping[JointId, float]] = None,
    ) -> list[Joint]:
        if torque_value is None:
            torque_value = self.current_torque
        limited_torque = int(
            self._clip(
                value=abs(self._clamp_torque(torque_value)),
                lower=0.0,
                upper=float(self.config.position_torque_limit),
            )
        )
        hold_joint_angles = hold_joint_angles or self._init_hold_joint_angles()
        joints: list[Joint] = []
        for joint_id in self._TORQUE_JOINTS:
            joints.append(
                Joint(
                    id=joint_id,
                    angle=hold_joint_angles.get(joint_id, 0.0),
                    speed=int(self.config.position_speed_limit),
                    torque=limited_torque,
                )
            )
        return joints

    def _should_auto_release(self) -> bool:
        if self._adaptive_hold_started_at is None:
            return False
        elapsed = self._get_monotonic_time() - self._adaptive_hold_started_at
        return elapsed >= self.config.release_hold_time_s

    def _perform_release(self, join_control_thread: bool) -> bool:
        self.state = GraspState.RELEASING
        self._running = False
        self._adaptive_hold_started_at = None

        control_thread = self._control_thread
        if (
            join_control_thread
            and control_thread
            and control_thread.is_alive()
            and control_thread is not threading.current_thread()
        ):
            control_thread.join(timeout=1.0)

        joints = self._build_position_joints(
            self._get_open_pose(),
            speed=self.config.release_open_speed,
            torque=self.config.release_open_torque,
        )
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if not ok:
            self.state = GraspState.ERROR
            return False

        target_pose = self._get_open_pose()
        settled_cycles = 0
        start = self._get_monotonic_time()
        feedback_supported = callable(getattr(self.hand, "get_joints", None))
        if feedback_supported:
            while (self._get_monotonic_time() - start) < self.config.release_timeout_s:
                joints_feedback = self._safe_get_joints()
                if joints_feedback is None:
                    break
                actual = {joint.id: joint.angle for joint in joints_feedback}
                is_settled = all(
                    abs(actual.get(joint_id, target_angle) - target_angle) <= self.config.theta_err_th
                    for joint_id, target_angle in target_pose.items()
                )
                if is_settled:
                    settled_cycles += 1
                    if settled_cycles >= self.config.release_check_cycles:
                        self.state = GraspState.COMPLETED
                        return True
                else:
                    settled_cycles = 0
                time.sleep(self.config.control_period_s)
            self.state = GraspState.ERROR
            return False

        self.state = GraspState.COMPLETED if ok else GraspState.ERROR
        return ok

    def _clip(self, value: float, lower: float, upper: float) -> float:
        value_f = float(value)
        lower_f = float(lower)
        upper_f = float(upper)
        if upper_f < lower_f:
            upper_f = lower_f
        return max(lower_f, min(upper_f, value_f))

    def _clamp_torque(self, value: float) -> float:
        lower = -100.0
        upper = self._clip(value=float(self.config.max_torque), lower=lower, upper=100.0)
        return self._clip(value=value, lower=lower, upper=upper)

    def _get_open_pose(self) -> dict[JointId, float]:
        return {
            JointId.THUMB_PIP: math.radians(0),
            JointId.THUMB_MCP: math.radians(0),
            JointId.THUMB_SWING: math.radians(0),
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
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `pytest tests/adaptive_grasp/test_controller.py::test_controller_runs_full_state_machine_with_submodules -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/controller.py tests/adaptive_grasp/test_controller.py
git commit -m "refactor(controller): integrate tactile, force_planner, safety submodules for V2.0"
```

---

### Task 4: Full test regression

- [ ] **Step 1: Run the full adaptive_grasp test suite**

Run: `python -m pytest tests/adaptive_grasp/ -v`

Expected: All tests PASS. If any fail, diagnose and fix.

Common issues to watch for:
- `test_controller.py` V1.0 tests that relied on internal `_calculate_variance`, `_compute_control_u`, etc. Those methods no longer exist on the controller. Either update the tests to test the submodules directly, or remove them if equivalent coverage exists in `test_tactile.py` / `test_force_planner.py`.

- [ ] **Step 2: Commit fixes if any**

```bash
git add -A
git commit -m "test(adaptive_grasp): fix controller tests for V2.0 submodule integration"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Modular architecture (tactile/force_planner/safety) → Task 3
- [x] `tactile.py` compatibility shim → Task 1
- [x] ObjectProfile / ObjectProfileRegistry → already implemented in force_planner.py
- [x] Force calibration in CLOSING → Task 3, `_calibrate_force`
- [x] PID error on normal force (`F_n,ref - F_n,k`) → already in force_planner.py
- [x] Slip debounce (`slip_count`, `max_slip_count`) → already in tactility.py
- [x] Fragile mode limits → already in force_planner.py
- [x] Safety monitor (sensor fault, empty grasp, object dropped) → already in safety.py
- [x] Timeout release → preserved from V1.0 in Task 3

**Placeholder scan:** None. Every step has complete code.

**Type consistency:**
- `AdaptiveGrasper.grasp()` signature updated to accept `object_profile: Optional[ObjectProfile]` — matches design doc
- `TactileAnalyzer.update()` returns `TactileAnalysis` — preserved via shim
- `ForcePlanner.compute()` accepts `TactileAnalysis` and `dict[JointId, float]` — matches existing force_planner.py
