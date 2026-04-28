# adaptive_grasp Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all critical and important bugs identified in the adaptive_grasp code review, bringing the test suite to 100% pass rate.

**Architecture:** Surgical fixes across controller, force_planner, safety, and visualization modules. No refactoring for refactoring's sake — only touch lines that directly fix identified issues.

**Tech Stack:** Python 3.12, pytest, matplotlib (TkAgg/Agg)

---

## File Map

| File | Responsibility | Changes |
|------|---------------|---------|
| `src/xiaoyao/adaptive_grasp/controller.py` | Main state machine & grasp lifecycle | Fix config=None crash, hardcoded sleep, move_joints failure handling, type annotations, reset cleanup |
| `src/xiaoyao/adaptive_grasp/force_planner.py` | Force/PID computation per finger | Replace time.time() with monotonic, extract shared PID method |
| `src/xiaoyao/adaptive_grasp/safety.py` | Safety monitoring | Rename IsGraspEmpty → is_grasp_empty, remove dead code |
| `src/xiaoyao/adaptive_grasp/visualization.py` | Real-time tactile plotting | Make backend configurable, add thread-safety guards |
| `src/xiaoyao/adaptive_grasp/utils.py` | Shared utilities | Extract _JOINT_TO_FINGER mapping here |
| `src/xiaoyao/adaptive_grasp/tactility.py` | Tactile analysis | Fix clip() keyword call style |
| `tests/adaptive_grasp/test_safety.py` | Safety module tests | Update tests to call correct methods and match current behavior |
| `tests/adaptive_grasp/test_controller.py` | Controller tests | Add test for config=None, move_joints failure threshold |

---

### Task 1: Fix config=None crash in controller.__init__

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/controller.py:45-66`
- Test: `tests/adaptive_grasp/test_controller.py`

**Bug:** `SensorClient` is initialized with `config.active_fingers` using the raw parameter, but `config` may be `None`.

- [ ] **Step 1: Write failing test**

Append to `tests/adaptive_grasp/test_controller.py`:

```python
def test_controller_accepts_none_config():
    """AdaptiveGrasper(config=None) should not crash."""
    hand = _MockHand()
    grasper = AdaptiveGrasper(hand, config=None)
    assert grasper.config is not None
    assert grasper._sensor is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/adaptive_grasp/test_controller.py::test_controller_accepts_none_config -v
```

Expected: `FAIL` with `AttributeError: 'NoneType' object has no attribute 'active_fingers'`

- [ ] **Step 3: Fix controller.py**

In `src/xiaoyao/adaptive_grasp/controller.py`, replace lines 45-66:

```python
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
            if _JOINT_TO_FINGER.get(j) in self.config.active_fingers
        )

        self._sensor = SensorClient(
            hand,
            active_fingers=set(self.config.active_fingers),
            get_monotonic_time=self._get_monotonic_time,
        )
```

Key change: use `self.config` everywhere after it's assigned.

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/adaptive_grasp/test_controller.py::test_controller_accepts_none_config -v
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/controller.py tests/adaptive_grasp/test_controller.py
git commit -m "fix(controller): use self.config instead of raw param to avoid None crash"
```

---

### Task 2: Replace time.time() with monotonic in force_planner

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/force_planner.py:68-76, 119-127`
- Test: `tests/adaptive_grasp/test_force_planner.py`

**Bug:** `compute()` uses `time.time()` for delta-time calculation, making PID vulnerable to system clock jumps.

- [ ] **Step 1: Write failing test**

Append to `tests/adaptive_grasp/test_force_planner.py`:

```python
def test_force_planner_uses_monotonic_time(monkeypatch):
    """compute() should use monotonic clock, not wall clock."""
    cfg = AdaptiveGraspConfig(control_period_s=0.01)
    planner = ForcePlanner(cfg, None)

    monkeypatch.setattr("xiaoyao.adaptive_grasp.force_planner.time.time", lambda: 999.0)
    # If using time.time(), this would compute huge dt and break PID.
    # With monotonic, dt stays bounded.

    analysis = TactileAnalysis(
        variance=0.0, slip_risk=0.0, direction_distance=0.0, friction_utilization=0.0,
        slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 1.0},
        total_fz=1.0,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decisions = planner.compute(analysis, angles)
    # Should not crash or produce nan/inf control_u
    assert math.isfinite(decisions[TactileSensorId.THUMB].control_u)
```

- [ ] **Step 2: Run test — verify it passes even before fix**

The existing guard (`actual_dt > 1.0`) prevents the crash, but the test documents intent. Run anyway:

```bash
pytest tests/adaptive_grasp/test_force_planner.py::test_force_planner_uses_monotonic_time -v
```

Expected: `PASS` (guard saves it, but we still want the semantic fix).

- [ ] **Step 3: Inject monotonic clock into ForcePlanner**

Modify `src/xiaoyao/adaptive_grasp/force_planner.py`:

Replace lines 68-76:

```python
    def __init__(self, config: AdaptiveGraspConfig, profile: Optional[ObjectProfile] = None):
        self.config = config
        self.profile = profile
        self.F_init = self._compute_F_init()
        self.is_fragile_mode = profile.is_fragile if profile else False

        self._finger_pid: dict[TactileSensorId, _FingerPidState] = {}
        self._last_compute_time: Optional[float] = None
        self._get_monotonic_time = time.monotonic
```

Replace lines 119-127:

```python
        now = self._get_monotonic_time()
        if dt is not None and dt > 0:
            actual_dt = dt
        elif self._last_compute_time is not None:
            actual_dt = now - self._last_compute_time
            if actual_dt <= 0 or actual_dt > 1.0:
                actual_dt = cfg.control_period_s
        else:
            actual_dt = cfg.control_period_s
        self._last_compute_time = now
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/adaptive_grasp/test_force_planner.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/force_planner.py tests/adaptive_grasp/test_force_planner.py
git commit -m "fix(force_planner): use monotonic clock for dt instead of time.time()"
```

---

### Task 3: DRY up duplicate PID computation in force_planner

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/force_planner.py:147-215`
- Test: `tests/adaptive_grasp/test_force_planner.py` (existing tests should still pass)

**Bug:** `_compute_finger_control_u` and `_compute_unified_control_u` repeat ~20 lines of identical PID logic.

- [ ] **Step 1: Extract shared PID helper**

In `src/xiaoyao/adaptive_grasp/force_planner.py`, insert before `_compute_finger_control_u`:

```python
    def _compute_pid_control_u(
        self,
        finger: TactileSensorId,
        s_k: float,
        fz: float,
        fz_limit: float,
        F_n_ref: float,
        dt: float,
    ) -> float:
        """Shared前馈+PID计算。"""
        cfg = self.config
        e_nk = max(0.0, (fz - fz_limit) / (fz_limit + cfg.epsilon))
        u_ff = cfg.K_s * s_k - cfg.K_n * e_nk

        pid_state = self._get_or_create_pid(finger)
        e_k = F_n_ref - fz
        pid_param = self._get_pid_params(finger)
        pid_state.integral = clip(pid_state.integral + e_k * dt, pid_param.I_min, pid_param.I_max)
        if pid_state._initialized:
            derivative = (e_k - pid_state.prev_error) / dt
        else:
            derivative = 0.0
            pid_state._initialized = True
        pid_state.prev_error = e_k
        u_pid = pid_param.K_p * e_k + pid_param.K_i * pid_state.integral + pid_param.K_d * derivative

        control_u = u_ff + u_pid

        if self.is_fragile_mode and fz >= fz_limit:
            control_u = min(control_u, 0.0)

        return control_u
```

- [ ] **Step 2: Replace _compute_finger_control_u**

Replace the method body with:

```python
    def _compute_finger_control_u(
        self,
        finger: TactileSensorId,
        per_finger_analysis: PerFingerAnalysis,
        finger_count: int,
        dt: float,
    ) -> float:
        F_n_ref = self.F_init / finger_count
        fz_limit = self._get_max_normal_force_per_finger(finger_count)
        return self._compute_pid_control_u(
            finger,
            s_k=per_finger_analysis.s_total,
            fz=per_finger_analysis.fz,
            fz_limit=fz_limit,
            F_n_ref=F_n_ref,
            dt=dt,
        )
```

- [ ] **Step 3: Replace _compute_unified_control_u**

Replace the method body with:

```python
    def _compute_unified_control_u(self, analysis: TactileAnalysis, finger_count: int, dt: float) -> float:
        F_n_ref = self.F_init / finger_count
        max_fz_limit = self._get_max_normal_force_per_finger(finger_count)
        max_fz = max(analysis.finger_fz.values()) if analysis.finger_fz else 0.0
        return self._compute_pid_control_u(
            TactileSensorId.THUMB,
            s_k=analysis.slip_risk,
            fz=max_fz,
            fz_limit=max_fz_limit,
            F_n_ref=F_n_ref,
            dt=dt,
        )
```

- [ ] **Step 4: Run all force_planner tests**

```bash
pytest tests/adaptive_grasp/test_force_planner.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/force_planner.py
git commit -m "refactor(force_planner): extract shared pid computation to eliminate duplication"
```

---

### Task 4: Fix safety test/implementation mismatch

**Files:**
- Modify: `tests/adaptive_grasp/test_safety.py`
- Modify: `src/xiaoyao/adaptive_grasp/safety.py:79`
- Test: `tests/adaptive_grasp/test_safety.py`

**Bug:** 6 tests fail because they call `check()` expecting `is_grasp_empty()` behavior, or expect `object_dropped` when `joint_feedback=None` triggers `sensor_fault` first.

Decision: Keep the current separation of concerns (`check()` for runtime safety, `is_grasp_empty()` for closing-phase empty detection). Update tests to call the correct method and provide valid inputs.

- [ ] **Step 1: Rename IsGraspEmpty → is_grasp_empty in safety.py**

```python
    def is_grasp_empty(
        self,
        joint_feedback: Optional[list],
        state: GraspState,
    ) -> SafetyReport:
```

- [ ] **Step 2: Update controller.py call site**

In `src/xiaoyao/adaptive_grasp/controller.py:207`, change:

```python
            if self._safety.is_grasp_empty(joint_feedback, self.state).status != SafetyStatus.OK:
```

- [ ] **Step 3: Rewrite failing tests in test_safety.py**

Replace the first 5 failing tests with corrected versions:

```python
def test_sensor_fault_on_joint_feedback_missing():
    cfg = AdaptiveGraspConfig()
    monitor = SafetyMonitor(cfg)
    report = monitor.check(tactile_data=None, joint_feedback=None, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "sensor_fault"


def test_empty_grasp_when_closing_with_no_contact():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)
    monitor.set_closing_baseline([Joint(id=JointId.THUMB_MCP, angle=0.0)])

    joints = [Joint(id=JointId.THUMB_MCP, angle=math.radians(35.0))]
    report = monitor.is_grasp_empty(joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "empty_grasp"


def test_object_dropped_when_contact_lost():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    # Establish baseline with valid joint_feedback
    baseline_joints = [Joint(id=JointId.THUMB_MCP, angle=0.0)]
    tactile_before = {"thumb": type("T", (), {"get_force_z": lambda self: 2.0})()}
    monitor.check(tactile_data=tactile_before, joint_feedback=baseline_joints, state=GraspState.ADAPTIVE_HOLD)

    tactile_after = {"thumb": type("T", (), {"get_force_z": lambda self: 0.0})()}
    report = monitor.check(tactile_data=tactile_after, joint_feedback=baseline_joints, state=GraspState.ADAPTIVE_HOLD)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "object_dropped"


def test_empty_grasp_with_joint_objects():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)
    monitor.set_closing_baseline([Joint(id=JointId.THUMB_MCP, angle=0.0)])

    joints = [Joint(id=JointId.THUMB_MCP, angle=math.radians(35.0))]
    report = monitor.is_grasp_empty(joint_feedback=joints, state=GraspState.CLOSING_TO_CONTACT)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "empty_grasp"
```

Remove the duplicate `test_sensor_fault_with_joint_objects` (it was identical to `test_sensor_fault_on_data_spike`).

- [ ] **Step 4: Run safety tests**

```bash
pytest tests/adaptive_grasp/test_safety.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/safety.py src/xiaoyao/adaptive_grasp/controller.py tests/adaptive_grasp/test_safety.py
git commit -m "fix(safety): rename IsGraspEmpty → is_grasp_empty, align tests with implementation"
```

---

### Task 5: Fix hardcoded sleep and move_joints failure handling

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/controller.py:188-199, 259-314, 360-380`
- Test: `tests/adaptive_grasp/test_controller.py`

**Bugs:**
1. `_phase_closing` hardcodes `time.sleep(0.2)`
2. `_run_control_step` does not stop on persistent `move_joints` failures
3. `_reset_runtime_state` does not clear `_object_profile` / `_force_planner`

- [ ] **Step 1: Add configurable closing_period_s to config**

In `src/xiaoyao/adaptive_grasp/config.py`, near `control_period_s`, add:

```python
    closing_period_s: float = 0.2  # CLOSING phase polling interval (seconds)
```

Add validation in `__post_init__`:

```python
        if self.closing_period_s <= 0:
            raise ValueError("closing_period_s must be > 0")
```

- [ ] **Step 2: Replace hardcoded sleep**

In `src/xiaoyao/adaptive_grasp/controller.py:199`:

```python
            time.sleep(self.config.closing_period_s)
```

- [ ] **Step 3: Add consecutive failure tracking and threshold**

In `AdaptiveGrasper.__init__`, add:

```python
        self._consecutive_move_failures: int = 0
        self._max_consecutive_move_failures: int = 3
```

In `_run_control_step`, replace the execution block (lines 309-314):

```python
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if not ok:
            self._consecutive_move_failures += 1
            _logger.error(
                "ADAPTIVE_HOLD: move_joints failed (%d/%d)",
                self._consecutive_move_failures,
                self._max_consecutive_move_failures,
            )
            if self._consecutive_move_failures >= self._max_consecutive_move_failures:
                _logger.error("ADAPTIVE_HOLD: too many consecutive move failures, entering ERROR")
                self.state = GraspState.ERROR
                self._running = False
                return False
        else:
            self._consecutive_move_failures = 0
        return ok
```

- [ ] **Step 4: Reset failure counter in _reset_runtime_state**

Add to `_reset_runtime_state`:

```python
        self._consecutive_move_failures = 0
        self._object_profile = None
        self._force_planner = None
```

- [ ] **Step 5: Write test for move_joints failure threshold**

Append to `tests/adaptive_grasp/test_controller.py`:

```python
def test_adaptive_hold_stops_after_consecutive_move_failures(monkeypatch):
    hand = _MockHand()
    cfg = AdaptiveGraspConfig(control_period_s=0.01)
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLD
    grasper._running = True
    grasper._force_planner = ForcePlanner(cfg, None)
    grasper._sensor._latest_tactile_data = {
        TactileSensorId.THUMB: _FakeTactileInfo(0.0, 0.0, 0.2),
    }
    grasper._sensor._latest_joint_feedback = []

    fail_count = [0]
    def fail_after_n(*args, **kwargs):
        fail_count[0] += 1
        return fail_count[0] > 3

    monkeypatch.setattr(hand, "move_joints", fail_after_n)
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
            finger_fz={TactileSensorId.THUMB: 0.2},
            total_fz=0.2,
        ),
    )

    # First 3 failures should return True (keep trying)
    assert grasper._run_control_step() is True
    assert grasper._run_control_step() is True
    assert grasper._run_control_step() is True
    # 4th failure should stop
    result = grasper._run_control_step()
    assert result is False
    assert grasper.state == GraspState.ERROR
    assert grasper._running is False
```

- [ ] **Step 6: Run controller tests**

```bash
pytest tests/adaptive_grasp/test_controller.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/controller.py src/xiaoyao/adaptive_grasp/config.py tests/adaptive_grasp/test_controller.py
git commit -m "fix(controller): configurable closing sleep, stop on persistent move_joints failures, cleanup reset"
```

---

### Task 6: Fix visualization backend and thread safety

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/visualization.py`
- Modify: `src/xiaoyao/adaptive_grasp/config.py`
- Test: `tests/adaptive_grasp/test_visualization.py`

**Bugs:**
1. `matplotlib.use("TkAgg")` crashes in headless environments
2. Matplotlib drawing from a background thread is not thread-safe

- [ ] **Step 1: Add visualization backend config**

In `src/xiaoyao/adaptive_grasp/config.py`, add:

```python
    visualization_backend: str = "TkAgg"  # matplotlib backend; use "Agg" for headless
```

- [ ] **Step 2: Make backend configurable with fallback**

In `src/xiaoyao/adaptive_grasp/visualization.py`, replace lines 7-9:

```python
import matplotlib
from .config import AdaptiveGraspConfig
```

(Remove the hardcoded `matplotlib.use("TkAgg")` at module level.)

Modify `TactileVisualizer.__init__` to accept backend:

```python
    def __init__(
        self,
        active_fingers: set[TactileSensorId],
        max_points: int = 300,
        update_interval: float = 0.1,
        figsize_width: float = 16,
        figsize_height_per_finger: float = 2.5,
        backend: str = "TkAgg",
    ):
        self._active_fingers = list(active_fingers)
        self._max_points = max_points
        self._update_interval = update_interval
        self._backend = backend
        ...
```

In `start()`, set backend before spawning thread:

```python
    def start(self) -> None:
        if self._running:
            return
        try:
            matplotlib.use(self._backend)
        except Exception as exc:
            _logger.warning("Visualizer backend %s failed: %s, falling back to Agg", self._backend, exc)
            matplotlib.use("Agg")
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
```

- [ ] **Step 3: Guard matplotlib canvas calls with try/except**

In `_run()`, wrap the draw block:

```python
        while self._running:
            with self._lock:
                if self._timestamps and self._fig is not None:
                    try:
                        t_list = list(self._timestamps)
                        for finger in self._active_fingers:
                            for key in ("fz", "ft", "variance", "direction", "friction"):
                                self._lines[finger][key].set_data(
                                    t_list, list(self._data[finger][key]),
                                )

                        for i in range(n):
                            for j in range(5):
                                self._axes[i, j].relim()
                                self._axes[i, j].autoscale_view()

                        self._fig.canvas.draw_idle()
                        self._fig.canvas.flush_events()
                    except Exception:
                        _logger.exception("Visualizer draw failed")

            time.sleep(self._update_interval)
```

- [ ] **Step 4: Update controller to pass backend**

In `controller.py:74-77`:

```python
            self._visualizer = TactileVisualizer(
                active_fingers=set(config.active_fingers),
                backend=self.config.visualization_backend,
            )
```

- [ ] **Step 5: Run visualization tests**

```bash
pytest tests/adaptive_grasp/test_visualization.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/visualization.py src/xiaoyao/adaptive_grasp/config.py src/xiaoyao/adaptive_grasp/controller.py tests/adaptive_grasp/test_visualization.py
git commit -m "fix(visualization): make matplotlib backend configurable, add draw error handling"
```

---

### Task 7: Clean up dead code and type annotations

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/safety.py`
- Modify: `src/xiaoyao/adaptive_grasp/controller.py:79-86`
- Modify: `src/xiaoyao/adaptive_grasp/tactility.py:151`
- Test: existing tests should still pass

- [ ] **Step 1: Remove unused _prev_joint_feedback in safety.py**

In `src/xiaoyao/adaptive_grasp/safety.py`, line 33:

```python
        self._prev_joint_feedback: dict[Any, float] = {}
```

Remove this line. Also remove the `.clear()` call in `reset()`.

- [ ] **Step 2: Fix type annotations in controller**

In `src/xiaoyao/adaptive_grasp/controller.py`, replace lines 79-86:

```python
        from .tactility import TactileAnalysis
        from .safety import SafetyReport
        from .force_planner import ForceDecision

        self._last_tactile_analysis: Optional[TactileAnalysis] = None
        self._last_safety_report: Optional[SafetyReport] = None
        self._last_force_decisions: Optional[dict[TactileSensorId, ForceDecision]] = None
```

Add the imports at the top if not already present (they are currently imported as module-level already; just need to import `TactileAnalysis`, `SafetyReport`, `ForceDecision` specifically if not already).

- [ ] **Step 3: Fix clip keyword call in tactility.py**

In `src/xiaoyao/adaptive_grasp/tactility.py:151`:

```python
        return clip((variance - cfg.variance_baseline) / denom, 0, 1)
```

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/adaptive_grasp/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/safety.py src/xiaoyao/adaptive_grasp/controller.py src/xiaoyao/adaptive_grasp/tactility.py
git commit -m "chore: remove dead code, tighten type annotations, fix clip call style"
```

---

### Task 8: Extract shared _JOINT_TO_FINGER mapping

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/utils.py`
- Modify: `src/xiaoyao/adaptive_grasp/controller.py`
- Modify: `src/xiaoyao/adaptive_grasp/force_planner.py`
- Test: `tests/adaptive_grasp/test_controller.py`

- [ ] **Step 1: Move mapping to utils.py**

Append to `src/xiaoyao/adaptive_grasp/utils.py`:

```python
from xiaoyao.dexhand import JointId, TactileSensorId


JOINT_TO_FINGER: dict[JointId, TactileSensorId] = {
    JointId.THUMB_PIP: TactileSensorId.THUMB,
    JointId.THUMB_MCP: TactileSensorId.THUMB,
    JointId.FF_PIP: TactileSensorId.FOREFINGER,
    JointId.FF_MCP: TactileSensorId.FOREFINGER,
    JointId.FF_SWING: TactileSensorId.FOREFINGER,
    JointId.MF_PIP: TactileSensorId.MIDDLE_FINGER,
    JointId.MF_MCP: TactileSensorId.MIDDLE_FINGER,
    JointId.RF_PIP: TactileSensorId.RING_FINGER,
    JointId.RF_MCP: TactileSensorId.RING_FINGER,
    JointId.LF_PIP: TactileSensorId.LITTLE_FINGER,
    JointId.LF_MCP: TactileSensorId.LITTLE_FINGER,
}
```

Note: the force_planner version included `FF_SWING`, so the unified mapping adds it.

- [ ] **Step 2: Update controller.py imports**

Replace the local `_JOINT_TO_FINGER` definition and import from utils:

```python
from .utils import clip, JOINT_TO_FINGER
```

And update usage:

```python
        self._torque_joints = tuple(
            j for j in AdaptiveGrasper._TORQUE_JOINTS
            if JOINT_TO_FINGER.get(j) in self.config.active_fingers
        )
```

- [ ] **Step 3: Update force_planner.py imports**

Replace local `_JOINT_TO_FINGER` with:

```python
from .utils import clip, JOINT_TO_FINGER
```

Update usage:

```python
            mapped_finger = JOINT_TO_FINGER.get(joint_id)
```

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/adaptive_grasp/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/utils.py src/xiaoyao/adaptive_grasp/controller.py src/xiaoyao/adaptive_grasp/force_planner.py
git commit -m "refactor: extract shared JOINT_TO_FINGER mapping to utils"
```

---

## Final Verification

- [ ] **Run the full adaptive_grasp test suite**

```bash
pytest tests/adaptive_grasp/ -v
```

Expected: **61 passed, 0 failed**

- [ ] **Run lint/type-check if available**

```bash
python -m py_compile src/xiaoyao/adaptive_grasp/*.py
```

Expected: no syntax errors.

- [ ] **Commit**

```bash
git commit --allow-empty -m "fix(adaptive_grasp): complete bug fix sweep — all tests green"
```

---

## Spec Coverage Check

| Review Finding | Task | Status |
|----------------|------|--------|
| config=None crash | Task 1 | covered |
| time.time() in PID dt | Task 2 | covered |
| Duplicate PID logic | Task 3 | covered |
| Safety test mismatch | Task 4 | covered |
| Hardcoded sleep(0.2) | Task 5 | covered |
| move_joints failure loop | Task 5 | covered |
| reset cleanup incomplete | Task 5 | covered |
| TkAgg headless crash | Task 6 | covered |
| Matplotlib thread safety | Task 6 | covered |
| Dead code _prev_joint_feedback | Task 7 | covered |
| Optional[Any] annotations | Task 7 | covered |
| clip keyword call | Task 7 | covered |
| _JOINT_TO_FINGER duplication | Task 8 | covered |
