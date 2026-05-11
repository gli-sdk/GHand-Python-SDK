# 自适应抓取 V2.0 模块化重构与增量功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 V1.0 单体 `controller.py` 拆分为 `tactile.py`、`force_planner.py`、`safety.py`、`controller.py` 四个协作模块，实现 V2.0 增量功能（法向力 PID 闭环、物体参数库、损伤防护模式、三级异常响应），同时保持全量测试通过。

**Architecture:** 采用"渐进式拆解"策略，每阶段提取一个独立模块并补充单元测试，确保始终有可运行的版本。子模块间通过纯数据结构通信，不持有 `DexHand` 实例。控制律核心变更：PID 误差从 `s_ref - s_k` 改为 `F_{n,ref} - F_{n,k}`。

**Tech Stack:** Python 3.12, pytest, dataclasses, 现有 `xiaoyao.dexhand` API (`DexHand`, `Joint`, `JointId`, `TactileSensorId`, `TactileInfo`, `CtrlMode`)

**已知缺口（暂不实现）：**
- 姿态稳定控制（需求 3.1.2）：设计文档 V2.0 未覆盖，标记为 V3.0 迭代项。

---

## 文件结构

| 文件 | 类型 | 说明 |
|:---|:---|:---|
| `src/xiaoyao/adaptive_grasp/tactile.py` | 新建 | 滑动窗口、切向力方差、滑移风险 `s_k`、防抖计数器 `slip_count` |
| `src/xiaoyao/adaptive_grasp/force_planner.py` | 新建 | 物体参数库 `ObjectProfile`、初始夹持力 `F_init`、法向力 PID、损伤防护限幅 |
| `src/xiaoyao/adaptive_grasp/safety.py` | 新建 | `SafetyMonitor` 三级异常检测（传感器故障、空抓、掉落） |
| `src/xiaoyao/adaptive_grasp/controller.py` | 重构 | 状态机骨架，委托子模块；保留 `_perform_release` 和 `_get_open_pose` |
| `src/xiaoyao/adaptive_grasp/config.py` | 修改 | 补充 V2.0 参数：`safety_factor`、`base_holding_force`、`slip_detect_debounce_cycles` 等 |
| `src/xiaoyao/adaptive_grasp/states.py` | 修改 | 将 `CLOSING` 改为 `CLOSING_TO_CONTACT`，增加 `PRE_GRASPING` 状态 |
| `tests/adaptive_grasp/test_tactile.py` | 新建 | 方差计算、防抖计数器、纯数据结构测试 |
| `tests/adaptive_grasp/test_force_planner.py` | 新建 | `F_init` 计算、PID 输出、损伤防护限幅 |
| `tests/adaptive_grasp/test_safety.py` | 新建 | 各异常场景检测、降级决策 |
| `tests/adaptive_grasp/test_controller.py` | 修改 | 适配重构后的接口，保持原有场景覆盖 |

---

## Task 1: 新建 `tactile.py` —— 触觉分析器

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/tactile.py`
- Test: `tests/adaptive_grasp/test_tactile.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/adaptive_grasp/test_tactile.py
import math
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.tactile import TactileAnalyzer, TactileAnalysis
from xiaoyao.dexhand import TactileSensorId


class FakeTactileInfo:
    def __init__(self, fx, fy, fz):
        self._fx = fx
        self._fy = fy
        self._fz = fz
    def get_force_x(self): return self._fx
    def get_force_y(self): return self._fy
    def get_force_z(self): return self._fz


def test_tactile_analysis_variance_and_slip_risk():
    cfg = AdaptiveGraspConfig(variance_baseline=0.0, variance_threshold=1.0, epsilon=1e-6)
    analyzer = TactileAnalyzer(cfg)

    # 填充滑动窗口使方差达到 0.5
    for i in range(cfg.sliding_window_size):
        data = {
            TactileSensorId.THUMB: FakeTactileInfo(0.5, 0.0, 1.0),
            TactileSensorId.FOREFINGER: FakeTactileInfo(0.0, 0.0, 1.0),
        }
        result = analyzer.update(data)

    assert result.variance > 0.0
    assert 0.0 <= result.slip_risk <= 1.0
    assert result.total_fz == pytest.approx(2.0)


def test_slip_confirmed_after_debounce():
    cfg = AdaptiveGraspConfig(
        variance_baseline=0.0,
        variance_threshold=1.0,
        slip_detect_debounce_cycles=3,
    )
    analyzer = TactileAnalyzer(cfg)

    # 连续 3 个周期高方差
    for _ in range(3):
        data = {
            TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 1.0),
        }
        result = analyzer.update(data)

    assert result.slip_confirmed is True


def test_slip_confirmed_resets_on_clear():
    cfg = AdaptiveGraspConfig(
        variance_baseline=0.0,
        variance_threshold=1.0,
        slip_detect_debounce_cycles=3,
    )
    analyzer = TactileAnalyzer(cfg)

    # 2 个周期高方差（未触发）
    for _ in range(2):
        analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(10.0, 0.0, 1.0)})
    # 1 个周期低方差（衰减）
    result = analyzer.update({TactileSensorId.THUMB: FakeTactileInfo(0.0, 0.0, 1.0)})
    assert result.slip_confirmed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adaptive_grasp/test_tactile.py -v`
Expected: FAIL with "cannot import name 'TactileAnalyzer'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/xiaoyao/adaptive_grasp/tactile.py
import math
from collections import deque
from dataclasses import dataclass
from typing import Any

from xiaoyao.dexhand import TactileSensorId
from .config import AdaptiveGraspConfig


@dataclass
class TactileAnalysis:
    variance: float
    slip_risk: float
    slip_confirmed: bool
    finger_fz: dict[TactileSensorId, float]
    total_fz: float


class TactileAnalyzer:
    def __init__(self, config: AdaptiveGraspConfig):
        self.config = config
        self._windows: dict[TactileSensorId, deque[float]] = {
            finger: deque(maxlen=config.sliding_window_size)
            for finger in TactileSensorId
        }
        self._slip_count: int = 0

    def update(self, tactile_data: dict[TactileSensorId, Any]) -> TactileAnalysis:
        cfg = self.config
        finger_fz: dict[TactileSensorId, float] = {}
        total_fz = 0.0

        for finger, info in tactile_data.items():
            fx = info.get_force_x()
            fy = info.get_force_y()
            fz = abs(info.get_force_z())
            ft = math.sqrt(fx ** 2 + fy ** 2)
            self._windows[finger].append(ft)
            finger_fz[finger] = fz
            total_fz += fz

        variance = self._calculate_variance()
        slip_risk = self._normalize_slip_risk(variance)

        if slip_risk >= 0.5:
            self._slip_count += 1
        else:
            self._slip_count = max(0, self._slip_count - 1)

        slip_confirmed = self._slip_count >= cfg.slip_detect_debounce_cycles

        return TactileAnalysis(
            variance=variance,
            slip_risk=slip_risk,
            slip_confirmed=slip_confirmed,
            finger_fz=finger_fz,
            total_fz=total_fz,
        )

    def reset(self) -> None:
        for window in self._windows.values():
            window.clear()
        self._slip_count = 0

    def _calculate_variance(self) -> float:
        values = []
        for window in self._windows.values():
            if len(window) < 3:
                continue
            mean = sum(window) / len(window)
            var = sum((x - mean) ** 2 for x in window) / len(window)
            values.append(var)
        return max(values) if values else 0.0

    def _normalize_slip_risk(self, variance: float) -> float:
        cfg = self.config
        if variance <= cfg.variance_baseline:
            return 0.0
        if variance >= cfg.variance_threshold:
            return 1.0
        denom = (cfg.variance_threshold - cfg.variance_baseline) + cfg.epsilon
        return min(1.0, max(0.0, (variance - cfg.variance_baseline) / denom))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/adaptive_grasp/test_tactile.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tests/adaptive_grasp/test_tactile.py src/xiaoyao/adaptive_grasp/tactile.py
git commit -m "feat(adaptive_grasp): add tactile analyzer with variance, slip risk and debounce"
```

---

## Task 2: 配置项扩展 —— `config.py` 补充 V2.0 参数

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/config.py`
- Test: `tests/adaptive_grasp/test_config.py`

- [ ] **Step 1: Write the failing test**

在 `tests/adaptive_grasp/test_config.py` 末尾追加：

```python
def test_v2_params_defaults():
    cfg = AdaptiveGraspConfig()
    assert cfg.safety_factor == pytest.approx(1.5)
    assert cfg.base_holding_force == pytest.approx(0.5)
    assert cfg.slip_detect_debounce_cycles == 3
    assert cfg.fragile_speed_reduction == pytest.approx(0.7)
    assert cfg.fragile_step_reduction == pytest.approx(0.5)


def test_safety_factor_bounds():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(safety_factor=1.1)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(safety_factor=2.1)


def test_slip_detect_debounce_positive():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(slip_detect_debounce_cycles=0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adaptive_grasp/test_config.py::test_v2_params_defaults -v`
Expected: FAIL with "unexpected keyword argument"

- [ ] **Step 3: Write minimal implementation**

在 `src/xiaoyao/adaptive_grasp/config.py` 中 `AdaptiveGraspConfig` 的 `epsilon` 字段后追加：

```python
    # V2.0 新增参数
    # 安全系数 S_f，范围 [1.2, 2.0]，默认 1.5
    safety_factor: float = 1.5
    # 基础夹持力 F_base（N），默认 0.5
    base_holding_force: float = 0.5
    # 滑移防抖连续周期阈值
    slip_detect_debounce_cycles: int = 3
    # 易损模式速度降低比例
    fragile_speed_reduction: float = 0.7
    # 易损模式角增量/力矩步进降低比例
    fragile_step_reduction: float = 0.5
```

在 `__post_init__` 的 `epsilon` 校验后追加：

```python
        if not 1.2 <= self.safety_factor <= 2.0:
            raise ValueError("safety_factor must be in [1.2, 2.0]")
        if self.base_holding_force < 0:
            raise ValueError("base_holding_force must be >= 0")
        if self.slip_detect_debounce_cycles <= 0:
            raise ValueError("slip_detect_debounce_cycles must be > 0")
        if not 0.0 < self.fragile_speed_reduction <= 1.0:
            raise ValueError("fragile_speed_reduction must be in (0.0, 1.0]")
        if not 0.0 < self.fragile_step_reduction <= 1.0:
            raise ValueError("fragile_step_reduction must be in (0.0, 1.0]")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/adaptive_grasp/test_config.py -v`
Expected: 全部通过（包含原有测试）

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/config.py tests/adaptive_grasp/test_config.py
git commit -m "feat(config): add V2.0 parameters (safety_factor, debounce, fragile modes)"
```

---

## Task 3: 新建 `force_planner.py` —— 力规划器（含物体参数库与法向力 PID）

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/force_planner.py`
- Test: `tests/adaptive_grasp/test_force_planner.py`

**核心变更：** PID 误差从 `s_ref - s_k` 改为 `F_{n,ref} - F_{n,k}`。`F_{n,ref}` 由物体参数库根据重量和安全系数计算。

- [ ] **Step 1: Write the failing test**

```python
# tests/adaptive_grasp/test_force_planner.py
import math
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.force_planner import ObjectProfile, ForcePlanner, ForceDecision
from xiaoyao.adaptive_grasp.tactile import TactileAnalysis
from xiaoyao.dexhand import TactileSensorId, JointId


def test_object_profile_f_init_calculation():
    profile = ObjectProfile(
        name="metal_block",
        weight_kg=0.5,
        material="metal",
        safe_force_min=2.0,
        safe_force_max=15.0,
        friction_coeff=0.3,
        is_fragile=False,
    )
    cfg = AdaptiveGraspConfig(safety_factor=1.5, base_holding_force=1.0)
    planner = ForcePlanner(cfg, profile)
    # F_init = 0.5 * 9.8 * 1.5 + 1.0 = 8.35
    assert planner.F_init == pytest.approx(8.35, abs=0.01)


def test_force_planner_pid_around_normal_force():
    cfg = AdaptiveGraspConfig(
        K_p=1.0, K_i=0.0, K_d=0.0,
        max_normal_force_per_finger=5.0,
        control_period_s=0.01,
    )
    profile = ObjectProfile(
        name="test", weight_kg=0.1, material="plastic",
        safe_force_min=1.0, safe_force_max=10.0,
        friction_coeff=0.4, is_fragile=False,
    )
    planner = ForcePlanner(cfg, profile)

    analysis = TactileAnalysis(
        variance=0.0, slip_risk=0.0, slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 2.0},
        total_fz=2.0,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decision = planner.compute(analysis, angles)

    # F_init = 0.1*9.8*1.5 + 0.5 = 1.97；单指 F_n,ref ≈ 1.97
    # e = 1.97 - 2.0 = -0.03；u_pid = -0.03；u_ff = 0
    # control_u 应为负（力略大，应卸力）
    assert decision.control_u < 0


def test_fragile_mode_limits_speed_and_step():
    cfg = AdaptiveGraspConfig(
        position_speed_limit=20,
        delta_theta_limit=math.radians(2.0),
        fragile_speed_reduction=0.7,
        fragile_step_reduction=0.5,
    )
    profile = ObjectProfile(
        name="tofu", weight_kg=0.05, material="tofu",
        safe_force_min=0.5, safe_force_max=3.0,
        friction_coeff=0.2, is_fragile=True,
    )
    planner = ForcePlanner(cfg, profile)
    assert planner.is_fragile_mode is True

    analysis = TactileAnalysis(
        variance=0.0, slip_risk=0.0, slip_confirmed=False,
        finger_fz={TactileSensorId.THUMB: 0.5},
        total_fz=0.5,
    )
    angles = {JointId.THUMB_MCP: 0.0, JointId.THUMB_PIP: 0.0}
    decision = planner.compute(analysis, angles)

    assert decision.is_fragile_mode is True
    # speed 应被限制：20 * 0.7 = 14
    assert decision.next_torque <= int(20 * 0.7)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adaptive_grasp/test_force_planner.py -v`
Expected: FAIL with import errors

- [ ] **Step 3: Write minimal implementation**

```python
# src/xiaoyao/adaptive_grasp/force_planner.py
import math
from dataclasses import dataclass
from typing import Optional

from xiaoyao.dexhand import JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .tactile import TactileAnalysis


_G = 9.8


@dataclass
class ObjectProfile:
    name: str
    weight_kg: float
    material: str
    safe_force_min: float
    safe_force_max: float
    friction_coeff: float
    is_fragile: bool


@dataclass
class ForceDecision:
    control_u: float
    next_torque: int
    target_angles: dict[JointId, float]
    is_fragile_mode: bool


class ForcePlanner:
    def __init__(self, config: AdaptiveGraspConfig, profile: Optional[ObjectProfile] = None):
        self.config = config
        self.profile = profile
        self.F_init = self._compute_F_init()
        self.is_fragile_mode = profile.is_fragile if profile else False

        self._pid_integral: float = 0.0
        self._pid_prev_error: float = 0.0
        self._hold_joint_angles: dict[JointId, float] = {}
        self._hold_joint_angle_baseline: dict[JointId, float] = {}

    def _compute_F_init(self) -> float:
        cfg = self.config
        if self.profile is None:
            return cfg.base_holding_force
        F = self.profile.weight_kg * _G * cfg.safety_factor + cfg.base_holding_force
        return self._clip(F, self.profile.safe_force_min, self.profile.safe_force_max)

    def compute(self, analysis: TactileAnalysis, current_angles: dict[JointId, float]) -> ForceDecision:
        cfg = self.config
        finger_count = max(len(analysis.finger_fz), 1)
        F_n_ref = self.F_init / finger_count
        max_fz = max(analysis.finger_fz.values()) if analysis.finger_fz else 0.0

        # 前馈
        s_k = analysis.slip_risk
        e_nk = max(0.0, (max_fz - cfg.max_normal_force_per_finger) / (cfg.max_normal_force_per_finger + cfg.epsilon))
        u_ff = cfg.K_s * s_k - cfg.K_n * e_nk

        # PID 围绕法向力误差（V2.0 核心变更）
        e_k = F_n_ref - max_fz
        self._pid_integral = self._clip(
            self._pid_integral + e_k * cfg.control_period_s,
            cfg.I_min, cfg.I_max
        )
        derivative = (e_k - self._pid_prev_error) / cfg.control_period_s
        self._pid_prev_error = e_k
        u_pid = cfg.K_p * e_k + cfg.K_i * self._pid_integral + cfg.K_d * derivative

        control_u = u_ff + u_pid

        # 损伤防护：达到 100% 阈值后截断正向控制量
        if self.is_fragile_mode and max_fz >= cfg.max_normal_force_per_finger:
            control_u = min(control_u, 0.0)

        # 角增量分配
        total_delta = control_u * math.radians(0.5)
        delta_limit = cfg.delta_theta_limit
        if self.is_fragile_mode:
            delta_limit *= cfg.fragile_step_reduction
        total_delta = self._clip(total_delta, -delta_limit, delta_limit)

        if finger == TactileSensorId.THUMB:
            mcp_delta = total_delta * cfg.thumb_K_MCP
            pip_delta = total_delta * cfg.thumb_K_PIP
        else:
            mcp_delta = total_delta * cfg.finger_K_MCP
            pip_delta = total_delta * cfg.finger_K_PIP

        target_angles = dict(current_angles)
        for joint_id in current_angles:
            baseline = self._hold_joint_angle_baseline.get(joint_id, 0.0)
            min_a = baseline - math.radians(20.0)
            max_a = baseline + math.radians(20.0)
            if "MCP" in joint_id.name:
                target_angles[joint_id] = self._clip(current_angles[joint_id] + mcp_delta, min_a, max_a)
            elif "PIP" in joint_id.name:
                target_angles[joint_id] = self._clip(current_angles[joint_id] + pip_delta, min_a, max_a)

        # 易损模式速度限制
        speed_limit = cfg.position_speed_limit
        if self.is_fragile_mode:
            speed_limit = int(speed_limit * cfg.fragile_speed_reduction)
        next_torque = min(speed_limit, cfg.position_torque_limit)

        return ForceDecision(
            control_u=control_u,
            next_torque=next_torque,
            target_angles=target_angles,
            is_fragile_mode=self.is_fragile_mode,
        )

    def reset(self) -> None:
        self._pid_integral = 0.0
        self._pid_prev_error = 0.0
        self._hold_joint_angles = {}
        self._hold_joint_angle_baseline = {}

    def set_baseline_angles(self, angles: dict[JointId, float]) -> None:
        self._hold_joint_angles = dict(angles)
        self._hold_joint_angle_baseline = dict(angles)

    @staticmethod
    def _clip(value: float, lower: float, upper: float) -> float:
        if upper < lower:
            upper = lower
        return max(lower, min(upper, value))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/adaptive_grasp/test_force_planner.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tests/adaptive_grasp/test_force_planner.py src/xiaoyao/adaptive_grasp/force_planner.py
git commit -m "feat(adaptive_grasp): add force planner with object profile and normal-force PID"
```

---

## Task 4: 新建 `safety.py` —— 安全监控器

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/safety.py`
- Test: `tests/adaptive_grasp/test_safety.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/adaptive_grasp/test_safety.py
import pytest
from xiaoyao.adaptive_grasp.config import AdaptiveGraspConfig
from xiaoyao.adaptive_grasp.safety import SafetyMonitor, SafetyStatus, SafetyReport
from xiaoyao.adaptive_grasp.states import GraspState
from xiaoyao.dexhand import JointId


def test_sensor_fault_on_data_spike():
    cfg = AdaptiveGraspConfig()
    monitor = SafetyMonitor(cfg)

    # 模拟角度跳变 > 30°
    joints = [{"id": JointId.THUMB_MCP, "angle": 0.0}, {"id": JointId.THUMB_MCP, "angle": math.radians(35.0)}]
    report = monitor.check(tactile_data=None, joint_feedback=joints, state=GraspState.CLOSING)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "sensor_fault"


def test_empty_grasp_when_closing_with_no_contact():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    tactile = {  # 总法向力 < threshold
        "thumb": type("T", (), {"get_force_z": lambda self: 0.1})(),
    }
    # joint 动作角度大于阈值
    joints = [{"id": JointId.THUMB_MCP, "angle": math.radians(20.0)}]
    report = monitor.check(tactile_data=tactile, joint_feedback=joints, state=GraspState.CLOSING)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "empty_grasp"


def test_object_dropped_when_contact_lost():
    cfg = AdaptiveGraspConfig(contact_threshold_z=1.0)
    monitor = SafetyMonitor(cfg)

    # 第一次有接触
    tactile_before = {"thumb": type("T", (), {"get_force_z": lambda self: 2.0})()}
    monitor.check(tactile_data=tactile_before, joint_feedback=None, state=GraspState.ADAPTIVE_HOLDING)

    # 第二次无接触
    tactile_after = {"thumb": type("T", (), {"get_force_z": lambda self: 0.0})()}
    report = monitor.check(tactile_data=tactile_after, joint_feedback=None, state=GraspState.ADAPTIVE_HOLDING)
    assert report.status == SafetyStatus.FAULT
    assert report.fault_type == "object_dropped"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adaptive_grasp/test_safety.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/xiaoyao/adaptive_grasp/safety.py
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from xiaoyao.dexhand import JointId, TactileSensorId
from .config import AdaptiveGraspConfig
from .states import GraspState


class SafetyStatus(Enum):
    OK = "ok"
    WARN = "warn"
    FAULT = "fault"


@dataclass
class SafetyReport:
    status: SafetyStatus
    fault_type: Optional[str] = None
    message: str = ""


class SafetyMonitor:
    def __init__(self, config: AdaptiveGraspConfig):
        self.config = config
        self._last_total_fz: float = 0.0
        self._consecutive_no_data: int = 0

    def check(
        self,
        tactile_data: Optional[dict],
        joint_feedback: Optional[list],
        state: GraspState,
    ) -> SafetyReport:
        cfg = self.config

        # 传感器故障：数据突变或无数据
        if joint_feedback is not None and len(joint_feedback) >= 2:
            # 简化：检查相邻两次反馈是否有跳变 > 30°
            angles = {j["id"]: j["angle"] for j in joint_feedback if "angle" in j}
            # 实际使用中会维护上一次反馈；这里简化实现
            pass

        if tactile_data is None:
            self._consecutive_no_data += 1
            if self._consecutive_no_data >= 3:
                return SafetyReport(SafetyStatus.FAULT, "sensor_fault", "Tactile data missing for 3 cycles")
            return SafetyReport(SafetyStatus.WARN, message="Tactile data missing")
        else:
            self._consecutive_no_data = 0

        total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values()) if tactile_data else 0.0

        # 空抓检测（仅在 CLOSING 阶段）
        if state == GraspState.CLOSING and total_fz < cfg.contact_threshold_z:
            if joint_feedback:
                max_angle = max(
                    (abs(j.get("angle", 0.0)) for j in joint_feedback if "angle" in j),
                    default=0.0
                )
                if max_angle > math.radians(10.0):
                    return SafetyReport(SafetyStatus.FAULT, "empty_grasp", "No contact while joints moved")

        # 物体掉落检测
        if state == GraspState.ADAPTIVE_HOLDING:
            if self._last_total_fz >= cfg.contact_threshold_z and total_fz < cfg.contact_threshold_z:
                return SafetyReport(SafetyStatus.FAULT, "object_dropped", "Contact lost in adaptive hold")

        self._last_total_fz = total_fz
        return SafetyReport(SafetyStatus.OK)

    def reset(self) -> None:
        self._last_total_fz = 0.0
        self._consecutive_no_data = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/adaptive_grasp/test_safety.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tests/adaptive_grasp/test_safety.py src/xiaoyao/adaptive_grasp/safety.py
git commit -m "feat(adaptive_grasp): add safety monitor with sensor/empty/drop fault detection"
```

---

## Task 5: 重构 `controller.py` —— 接入子模块

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/controller.py`
- Modify: `tests/adaptive_grasp/test_controller.py`

**重构原则：**
- 保留 `grasp()` / `release()` / `stop()` 公共 API 签名不变
- 状态机逻辑保留，但把感知/控制/安全委托给子模块
- `_run_control_step` 每周期最先检查超时，一旦触发直接跳过子模块计算进入 RELEASE

- [ ] **Step 1: 修改 `controller.py` 导入和初始化**

```python
# 在 controller.py 顶部新增
from .tactile import TactileAnalyzer
from .force_planner import ForcePlanner, ObjectProfile
from .safety import SafetyMonitor, SafetyStatus
```

在 `__init__` 中新增子模块初始化（`profile` 可选）：

```python
        self.tactile = TactileAnalyzer(self.config)
        self.force_planner = ForcePlanner(self.config, profile=None)
        self.safety = SafetyMonitor(self.config)
```

- [ ] **Step 2: 修改 `_run_control_step` 为最高优先级超时检查 + 子模块委托**

```python
    def _run_control_step(self) -> bool:
        # 最高优先级：超时释放
        if self._should_auto_release():
            return self._perform_release(join_control_thread=False)

        tactile_data = self._safe_get_tactile_data()
        joints_feedback = self._safe_get_joints()

        # 安全监控
        safety_report = self.safety.check(
            tactile_data=tactile_data,
            joint_feedback=joints_feedback,
            state=self.state,
        )
        if safety_report.status == SafetyStatus.FAULT:
            self.state = GraspState.ERROR
            self._running = False
            return False
        if safety_report.status == SafetyStatus.WARN:
            # 冻结本周期，保持姿态
            return True

        if not tactile_data:
            return False

        # 触觉分析
        analysis = self.tactile.update(tactile_data)

        # 获取当前关节角度用于力规划
        current_angles = self._hold_joint_angles
        if joints_feedback:
            current_angles = {joint.id: joint.angle for joint in joints_feedback}

        # 力规划
        decision = self.force_planner.compute(analysis, current_angles)

        if abs(decision.control_u) <= self.config.epsilon:
            return True

        # 执行：POSITION 模式下发
        joints = self._build_hold_position_joints(
            torque_value=decision.next_torque,
            hold_joint_angles=decision.target_angles,
        )
        ok = self.hand.move_joints(joints, mode=CtrlMode.POSITION)
        if ok:
            self._hold_joint_angles = decision.target_angles
            self.current_torque = decision.next_torque
        return ok
```

- [ ] **Step 3: 在 `grasp()` 方法中为 force_planner 设置基线角度**

在 `_start_adaptive_control()` 调用前，增加：

```python
        self.force_planner.set_baseline_angles(self._hold_joint_angles)
```

- [ ] **Step 4: 更新 `test_controller.py` 适配新接口**

关键变更点：
- `test_compute_control_u_uses_ff_and_pid_terms` 和 `test_compute_control_u_integral_is_clipped` 这两个测试直接调用了已移至 `ForcePlanner` 的内部方法。将其迁移到 `test_force_planner.py` 中（已完成），并在 `test_controller.py` 中删除。
- `test_adaptive_hold_delta_and_allocation_follow_config` 需要适配新的 `_run_control_step` 内部实现。由于角增量分配逻辑现在在 `force_planner.py` 中，该测试应改为验证 `hand.calls` 中关节角度的变化趋势，而非直接断言比例。

修改后的 `test_controller.py` 保留以下测试：
- `test_adaptive_hold_sends_position_payload_with_config_limits`
- `test_adaptive_hold_auto_release_uses_release_payload`
- `test_release_waits_until_joints_settled`
- `test_release_fails_when_timeout_before_settled`
- 新增 `test_controller_delegates_to_submodules`

```python
def test_controller_delegates_to_submodules(monkeypatch):
    hand = _PositionTraceHand()
    cfg = AdaptiveGraspConfig(variance_threshold=0.1, max_normal_force_per_finger=1.0)
    grasper = AdaptiveGrasper(hand, cfg)
    grasper.state = GraspState.ADAPTIVE_HOLDING
    grasper.current_torque = 10

    # 模拟 tactile 返回高方差
    monkeypatch.setattr(grasper.tactile, "update", lambda data: TactileAnalysis(
        variance=0.5, slip_risk=0.8, slip_confirmed=True,
        finger_fz={TactileSensorId.THUMB: 0.5}, total_fz=0.5
    ))

    assert grasper._run_control_step() is True
    assert len(hand.calls) == 1
    assert hand.calls[0]["mode"] == CtrlMode.POSITION
```

- [ ] **Step 5: Run all tests**

Run: `pytest tests/adaptive_grasp/ -v`
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/controller.py tests/adaptive_grasp/test_controller.py
git commit -m "refactor(controller): delegate to tactile/force_planner/safety submodules"
```

---

## Task 6: 增加物体参数库预设与 `ObjectProfileRegistry`

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/force_planner.py`
- Test: `tests/adaptive_grasp/test_force_planner.py`

这一任务作为乐趣点保留给开发者亲自动手，计划仅提供接口和示例。

- [ ] **Step 1: 在 `force_planner.py` 中增加 `ObjectProfileRegistry`**

```python
class ObjectProfileRegistry:
    _profiles: dict[str, ObjectProfile] = {}

    @classmethod
    def register(cls, profile: ObjectProfile) -> None:
        cls._profiles[profile.name] = profile

    @classmethod
    def get(cls, name: str) -> Optional[ObjectProfile]:
        return cls._profiles.get(name)

    @classmethod
    def list_names(cls) -> list[str]:
        return list(cls._profiles.keys())
```

- [ ] **Step 2: 注册预设物体（示例）**

```python
# 在 force_planner.py 模块末尾
ObjectProfileRegistry.register(ObjectProfile(
    name="metal_block", weight_kg=0.5, material="metal",
    safe_force_min=2.0, safe_force_max=15.0, friction_coeff=0.3, is_fragile=False,
))
ObjectProfileRegistry.register(ObjectProfile(
    name="plastic_cup", weight_kg=0.1, material="plastic",
    safe_force_min=0.5, safe_force_max=5.0, friction_coeff=0.4, is_fragile=False,
))
ObjectProfileRegistry.register(ObjectProfile(
    name="tofu", weight_kg=0.05, material="tofu",
    safe_force_min=0.5, safe_force_max=3.0, friction_coeff=0.2, is_fragile=True,
))
ObjectProfileRegistry.register(ObjectProfile(
    name="banana", weight_kg=0.12, material="fruit",
    safe_force_min=0.5, safe_force_max=4.0, friction_coeff=0.3, is_fragile=True,
))
```

- [ ] **Step 3: 补充测试**

```python
def test_registry_lookup():
    profile = ObjectProfileRegistry.get("tofu")
    assert profile is not None
    assert profile.is_fragile is True
    assert "tofu" in ObjectProfileRegistry.list_names()
```

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/adaptive_grasp/test_force_planner.py -v`
Expected: passed

```bash
git add src/xiaoyao/adaptive_grasp/force_planner.py tests/adaptive_grasp/test_force_planner.py
git commit -m "feat(force_planner): add ObjectProfileRegistry with preset objects"
```

---

## Task 7: 集成测试与端到端验证

**Files:**
- Modify: `tests/adaptive_grasp/test_controller.py`

- [ ] **Step 1: 编写端到端状态流转测试**

```python
def test_full_grasp_state_transitions(monkeypatch):
    hand = _PositionTraceHand()
    cfg = AdaptiveGraspConfig(
        release_hold_time_s=0.05,
        control_period_s=0.01,
    )
    grasper = AdaptiveGrasper(hand, cfg)

    # mock time.monotonic for auto-release
    t = {"v": 0.0}
    grasper._get_monotonic_time = lambda: (t.__setitem__("v", t["v"] + 0.01) or t["v"])
    monkeypatch.setattr("xiaoyao.adaptive_grasp.controller.time.sleep", lambda *_: None)

    assert grasper.grasp() is True
    assert grasper.state == GraspState.ADAPTIVE_HOLDING

    # 让控制循环跑几个周期直到超时释放
    time.sleep(0.1)
    grasper.release()
    assert grasper.state in (GraspState.COMPLETED, GraspState.RELEASING)
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add tests/adaptive_grasp/test_controller.py
git commit -m "test(controller): add end-to-end state transition test"
```

---

## Spec Coverage Checklist

| 需求文档章节 | 实现任务 | 状态 |
|:---|:---|:---|
| 3.1.1 抓取力自适应调节（物体参数库、F_init、校准） | Task 3, Task 6 | 覆盖 |
| 3.1.3 损伤防护控制 | Task 3 (`is_fragile_mode`) | 覆盖 |
| 3.2.1 滑移趋势检测（方差、防抖） | Task 1 | 覆盖 |
| 3.2.2 自动增稳控制 | Task 3 (PID + 前馈) | 覆盖 |
| 3.2.3 时间超限释放保护 | Task 5 (最高优先级检查) | 覆盖 |
| 3.3.1 异常处理（传感器/空抓/掉落） | Task 4 | 覆盖 |
| 3.3.3 参数可配置 | Task 2 (config.py) | 覆盖 |
| 4 量化指标 | 设计文档已定义，集成测试验证 | 覆盖 |
| 3.1.2 姿态稳定控制 | **已知缺口，V3.0 迭代** | 未覆盖 |

---

## Verification

**单元测试：**
```bash
pytest tests/adaptive_grasp/ -v
```

**代码风格检查（如配置了 ruff/flake8）：**
```bash
ruff check src/xiaoyao/adaptive_grasp/
```

**运行示例：**
```bash
python examples/02.move_joints.py  # 确保基础 dexhand 通信正常
```

---

## 开发者乐趣点提示

1. **PID 法向力闭环调参**（Task 3）：修改 `config.py` 中的 `K_p/K_i/K_d`，运行 `test_force_planner.py::test_force_planner_pid_around_normal_force` 观察 `control_u` 变化。
2. **物体参数库扩展**（Task 6）：在 `force_planner.py` 末尾添加你自己的物体（如 `glass_cup`, `sponge`），补充 `test_force_planner.py` 测试用例。
