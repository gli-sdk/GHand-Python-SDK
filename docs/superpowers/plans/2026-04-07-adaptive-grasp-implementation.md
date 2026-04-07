# 自适应抓取（有符号电流闭环）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 将 `docs/superpowers/specs/adaptive-grasp-design.md` 中的“姿态-力解耦 + 基线阈值归一化 + 有符号电流映射”落地到当前 SDK 代码，并补齐可执行测试。  
**架构：** 保留现有四阶段状态机（`OPEN/PRE_GRASP/TORQUE/ADAPTIVE_HOLD`），把 Phase4 的控制核心从“扭矩步进”升级为“滑移风险归一化 -> 电流增量 -> 有符号电流限幅”的离散闭环；通过回调函数暴露关键状态切换事件。  
**技术栈：** Python 3.12, pytest, xiaoyao SDK (`DexHand`, `CtrlMode`, `Joint`)

---

## 文件结构与职责

- `src/xiaoyao/adaptive_grasp/config.py`  
  职责：配置项定义、参数约束、阈值映射（`stiffness -> max_normal_force/variance_threshold`）以及新电流控制参数。

- `src/xiaoyao/adaptive_grasp/controller.py`  
  职责：状态机流程、回调触发、滑移归一化、法向力误差计算、电流指令更新与限幅、命令下发。

- `examples/22.adaptive_grasp_demo.py`  
  职责：对外演示使用方式，展示新参数与关键状态输出。

- `tests/adaptive_grasp/test_config.py`（新建）  
  职责：验证配置参数合法性、默认值和映射规则。

- `tests/adaptive_grasp/test_controller.py`（新建）  
  职责：验证闭环公式、回调触发、命令范围与速率限制。

---

### Task 1: 建立测试目录与配置测试骨架

**Files:**
- Create: `tests/adaptive_grasp/test_config.py`

- [ ] **Step 1: 写失败测试（配置新增参数与约束）**

```python
import pytest
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig


def test_current_limits_default_range():
    cfg = AdaptiveGraspConfig()
    assert cfg.i_close_max <= 100
    assert cfg.i_open_max <= 100


def test_invalid_current_limits_raise():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(i_close_max=120)
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(i_open_max=120)


def test_rate_limits_positive():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(delta_up=0)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/adaptive_grasp/test_config.py -v`  
Expected: FAIL（`AdaptiveGraspConfig` 缺少新字段/校验）

- [ ] **Step 3: 提交测试骨架**

```bash
git add tests/adaptive_grasp/test_config.py
git commit -m "test: add config tests for signed-current constraints"
```

---

### Task 2: 扩展 `AdaptiveGraspConfig` 以支持有符号电流闭环

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/config.py`
- Modify: `tests/adaptive_grasp/test_config.py`

- [ ] **Step 1: 最小实现配置字段与校验**

```python
@dataclass
class AdaptiveGraspConfig:
    # ... existing fields ...
    variance_baseline: float = 0.0

    i_close_max: int = 35
    i_open_max: int = 20
    delta_up: int = 2
    delta_down: int = 3

    def __post_init__(self) -> None:
        # ... existing checks ...
        if not 0 <= self.i_close_max <= 100:
            raise ValueError("i_close_max must be in [0, 100]")
        if not 0 <= self.i_open_max <= 100:
            raise ValueError("i_open_max must be in [0, 100]")
        if self.delta_up <= 0 or self.delta_down <= 0:
            raise ValueError("delta_up/delta_down must be > 0")
        if self.variance_threshold is not None and self.variance_baseline >= self.variance_threshold:
            raise ValueError("variance_baseline must be < variance_threshold")
```

- [ ] **Step 2: 完善测试覆盖默认值与边界**

```python
def test_variance_baseline_must_be_less_than_threshold():
    with pytest.raises(ValueError):
        AdaptiveGraspConfig(variance_baseline=0.2, variance_threshold=0.1)
```

- [ ] **Step 3: 运行配置测试**

Run: `python -m pytest tests/adaptive_grasp/test_config.py -v`  
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/xiaoyao/adaptive_grasp/config.py tests/adaptive_grasp/test_config.py
git commit -m "feat: add signed-current config fields and validation"
```

---

### Task 3: 先写控制律失败测试（归一化 + 超限误差 + 电流限幅）

**Files:**
- Create: `tests/adaptive_grasp/test_controller.py`

- [ ] **Step 1: 写失败测试（核心公式）**

```python
import pytest
from unittest.mock import Mock
from xiaoyao.adaptive_grasp import AdaptiveGrasper, AdaptiveGraspConfig


def test_slip_normalization_baseline_threshold():
    g = AdaptiveGrasper(Mock(), AdaptiveGraspConfig(variance_baseline=0.02, variance_threshold=0.12))
    assert g._normalize_slip_risk(0.02) == pytest.approx(0.0)
    assert g._normalize_slip_risk(0.12) == pytest.approx(1.0)


def test_normal_force_error():
    g = AdaptiveGrasper(Mock(), AdaptiveGraspConfig(max_normal_force_per_finger=1.0))
    assert g._normal_force_error(0.8) == pytest.approx(0.0)
    assert g._normal_force_error(1.2) > 0


def test_current_command_clamped_to_signed_range():
    g = AdaptiveGrasper(Mock(), AdaptiveGraspConfig(i_close_max=30, i_open_max=15))
    g.current_cmd = 29
    assert g._limit_signed_current(60) == 30
    assert g._limit_signed_current(-99) == -15
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/adaptive_grasp/test_controller.py -v`  
Expected: FAIL（`AdaptiveGrasper` 尚无这些方法/字段）

- [ ] **Step 3: 提交失败测试**

```bash
git add tests/adaptive_grasp/test_controller.py
git commit -m "test: add failing tests for slip normalization and signed current mapping"
```

---

### Task 4: 在 `controller.py` 落地控制核心（不改外部接口）

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/controller.py`
- Modify: `tests/adaptive_grasp/test_controller.py`

- [ ] **Step 1: 引入有符号电流状态与工具函数**

```python
self.current_cmd = int(self._clamp_hardware_current(self.config.base_torque))


def _normalize_slip_risk(self, variance: float) -> float:
    cfg = self.config
    denom = (cfg.variance_threshold - cfg.variance_baseline) + 1e-6
    value = (variance - cfg.variance_baseline) / denom
    return max(0.0, min(1.0, value))


def _normal_force_error(self, max_fz: float) -> float:
    cfg = self.config
    return max(0.0, (max_fz - cfg.max_normal_force_per_finger) / (cfg.max_normal_force_per_finger + 1e-6))
```

- [ ] **Step 2: 落地增量电流控制律与两级限幅**

```python
def _next_current_cmd(self, max_fz: float, variance: float) -> int:
    s_k = self._normalize_slip_risk(variance)
    e_nk = self._normal_force_error(max_fz)
    delta_i = (self.config.torque_adjust_step * s_k) - (self.config.load_gain * e_nk)

    raw = self.current_cmd + int(round(delta_i))
    scene_limited = self._limit_signed_current(raw)
    hw_limited = self._clamp_hardware_current(scene_limited)
    return self._apply_rate_limit(hw_limited)
```

- [ ] **Step 3: 在 `_run_control_step` 接入新逻辑并下发命令**

```python
max_fz = max(finger_fz.values()) if finger_fz else 0.0
next_cmd = self._next_current_cmd(max_fz=max_fz, variance=variance)
joints = self._build_torque_joints(next_cmd)
self.hand.move_joints(joints, mode=CtrlMode.TORQUE)
self.current_cmd = next_cmd
```

- [ ] **Step 4: 运行单测**

Run: `python -m pytest tests/adaptive_grasp/test_controller.py -v`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/xiaoyao/adaptive_grasp/controller.py tests/adaptive_grasp/test_controller.py
git commit -m "feat: implement signed-current control loop with baseline-threshold normalization"
```

---

### Task 5: 增加回调触发点（模式切换事件）

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/controller.py`
- Modify: `tests/adaptive_grasp/test_controller.py`

- [ ] **Step 1: 先写失败测试（回调是否触发）**

```python
class ProbeGrasper(AdaptiveGrasper):
    def __init__(self, hand, config):
        super().__init__(hand, config)
        self.events = []

    def on_pre_grasp_reached(self):
        self.events.append("pre")

    def on_contact_detected(self, total_fz):
        self.events.append("contact")
```

- [ ] **Step 2: 实现默认空回调并在关键节点调用**

```python
def on_pre_grasp_reached(self) -> None:
    return None

# after pre_grasp success
self.on_pre_grasp_reached()

# when contact reached
self.on_contact_detected(total_fz)
```

- [ ] **Step 3: 运行对应测试**

Run: `python -m pytest tests/adaptive_grasp/test_controller.py::test_callbacks_are_triggered -v`  
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/xiaoyao/adaptive_grasp/controller.py tests/adaptive_grasp/test_controller.py
git commit -m "feat: add callback hooks for mode transition events"
```

---

### Task 6: 更新示例脚本与参数展示

**Files:**
- Modify: `examples/22.adaptive_grasp_demo.py`

- [ ] **Step 1: 适配新参数与日志输出**

```python
config = AdaptiveGraspConfig(
    stiffness=args.stiffness,
    i_close_max=args.max_torque,
    i_open_max=20,
    variance_baseline=0.02,
)

print(f"i_close_max={config.i_close_max}, i_open_max={config.i_open_max}")
```

- [ ] **Step 2: 语法检查**

Run: `python -m py_compile examples/22.adaptive_grasp_demo.py`  
Expected: no output

- [ ] **Step 3: 提交**

```bash
git add examples/22.adaptive_grasp_demo.py
git commit -m "chore: update adaptive grasp demo for signed-current config"
```

---

### Task 7: 全量回归与文档收尾

**Files:**
- Run: `tests/adaptive_grasp/test_config.py`
- Run: `tests/adaptive_grasp/test_controller.py`

- [ ] **Step 1: 运行全量测试**

Run: `python -m pytest tests/adaptive_grasp -v`  
Expected: 全部 PASS

- [ ] **Step 2: 补充 README/文档变更说明（如需要）**

```markdown
- 控制律从扭矩步进升级为有符号电流闭环
- 引入基线+阈值归一化
- 引入回调驱动状态切换
```

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: complete adaptive grasp signed-current control implementation"
```

---

## 里程碑验收标准

1. `PRE_GRASP -> TORQUE -> ADAPTIVE_HOLD` 切换可观测（回调可触发）。  
2. `s_k` 严格使用“基线+阈值归一化”。  
3. `I_cmd` 在任意时刻满足 `[-100,100]` 且受场景上限、速率限制约束。  
4. 关键单元测试和集成测试可重复通过。  

---

## 风险与应对

- 风险：`POSITION` 与 `TORQUE` 交替发送可能引起抖动。  
  - 应对：回调切换后只在 `TORQUE` 通道下发 MCP/PIP，姿态关节仅在前两阶段控制。

- 风险：触觉噪声导致 `s_k` 抖动。  
  - 应对：保留滑窗与速率限制，并在测试中加入噪声样例。

- 风险：场景上限配置不当导致夹持不足或过压。  
  - 应对：在 demo 提供参数输出与推荐值，先从低上限开始调试。
