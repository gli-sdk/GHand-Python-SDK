# 力矩模式闭环保持实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现力矩模式下的三指闭环保持，让纸杯在倒水过程中能够根据触觉滑动趋势逐步增加夹持力，尽量避免掉落和压坏。

**Architecture:** 新增独立的 `TorqueHoldPlanner`，专门负责力矩模式闭环控制，不把力矩控制逻辑继续塞进位置保持用的 `ForcePlanner`。闭合找接触阶段保存逐指法向力快照，用快照建立三指非均分接触比例；自适应保持阶段根据滑动趋势更新总目标法向力 `F_ref_total`，再按接触比例得到逐指 `F_ref_i`，最后用每指 PID 生成逐指力矩命令。

**Tech Stack:** Python 3.12/3.13, pytest, existing `DexHand`, `TactileAnalyzer`, `PidController`, `JointCommandBuilder`, `AdaptiveGrasper`

当前代码中的 `PidController` 构造方式是 `PidController(PidParams(...))`，不是 `PidController(kp=..., ki=..., kd=...)`。执行本计划时必须使用当前类接口，避免引入第二套 PID 写法。

---

## 核心控制思路

三指抓纸杯时，不要强行让三个手指法向力均分。每个手指的接触位置、杯壁刚度、接触面积都可能不同，均分目标反而可能让某个手指过度挤压纸杯。

闭合找接触结束时，记录逐指法向力快照：

```text
contact_fz_thumb
contact_fz_forefinger
contact_fz_middle
contact_total_fz
```

用接触快照计算初始受力比例：

```python
ratio_i = contact_fz_i / contact_total_fz
ratio_i = max(ratio_i, min_contact_ratio)
ratio_i = ratio_i / sum(ratios)
```

初始总目标力：

```python
F_ref_total = max(contact_total_fz + margin, profile.safe_force_min)
F_ref_total = min(F_ref_total, profile.safe_force_max)
```

### 200 ml 纸杯 demo 负载估算

纸杯大约能装满 `200 ml` 水时，需要把“空杯抓取”和“满杯保持”分开看：

```text
水密度约 1 g/ml
200 ml 水质量约 0.20 kg
空纸杯质量暂按 0.01 kg 估算
满杯总质量约 0.21 kg
满杯重力 W = 0.21 * 9.81 ≈ 2.06 N
```

如果三指主要靠侧向夹持摩擦防止下滑，粗略需要的总法向力下限为：

```text
F_normal_min = W * safety_factor / friction_coeff
             ≈ 2.06 * 1.5 / 0.8
             ≈ 3.86 N
```

如果沿用当前 `ForcePlanner` 的估算习惯，再加 `base_holding_force=0.5 N`，满杯时目标总法向力会接近：

```text
F_ref_full ≈ 3.86 + 0.5 = 4.36 N
```

因此 demo 参数建议是：

```text
weight_kg: 仍按空杯质量 0.01 kg 记录，不要直接写 0.21 kg，否则空杯阶段容易一开始就夹得过紧。
safe_force_min: 用于空杯初始稳定接触，建议 0.5-0.8 N。
safe_force_max: 用于满杯倒水阶段的总力上限。200 ml demo 在摩擦系数 0.8 时理论上需要约 4.0-4.4 N，但第一次实物实验先用 3.0-3.5 N 验证杯壁不变形，再逐步放宽到 4.0-4.4 N。
adaptive_hold_torque: 初始力矩，配置在 AdaptiveGraspConfig，建议从 5 开始。
torque_hold_slip_gain_n_per_s: 滑动风险响应增益，配置在 AdaptiveGraspConfig；它不是倒水速度，而是当触觉检测到滑动趋势时，允许 `F_ref_total` 随 `slip_risk` 增加的最大响应强度。
torque_hold_max_rise_step_n: 单个控制周期允许的最大增力步长，配置在 AdaptiveGraspConfig，用作安全限幅，避免触觉噪声导致力目标突跳。
torque_hold_confirmed_boost_n: 确认滑动时的一次性目标力增量，配置在 AdaptiveGraspConfig，建议小于等于 0.5 N；默认仍使用更保守的小值，避免阶跃压坏杯壁。
```

参数归属原则：

```text
本次力矩闭环保持功能的控制参数，统一配置在 src/xiaoyao/adaptive_grasp/config.py 的 AdaptiveGraspConfig 中。
object_profile.py 只保存物体/材质属性，例如 weight_kg、safe_force_min、safe_force_max、friction_coeff、is_fragile、material。
不要把 torque_hold_force_margin_n、torque_hold_slip_gain_n_per_s、torque_hold_max_rise_step_n、torque_hold_confirmed_boost_n、torque_hold_K_p/K_i/K_d 这类控制器调参项放进 ObjectProfile。
力矩闭环不读取 `ObjectProfile.base_hold_torque`。该字段如果暂时保留，只作为旧位置保持逻辑的兼容字段；基础保持力矩统一使用 AdaptiveGraspConfig.adaptive_hold_torque。
```

保持阶段：

```text
slip_risk > warning_threshold -> F_ref_total 缓慢增加
slip_confirmed 上升沿 -> F_ref_total 一次性增加 boost
slip_risk 长时间很低 -> F_ref_total 缓慢回落
```

逐指目标力：

```python
F_ref_i = F_ref_total * ratio_i
```

后续如果需要逐指局部增强，再单独增加 `local_boost_i` 设计；本计划第一版先不引入该项，避免控制量来源过多。

逐指 PID 输出力矩：

```python
error_i = F_ref_i - fz_i
torque_i_float = config.adaptive_hold_torque + pid_i.compute(error_i, dt)
```

内部计算保持浮点，不截断 PID 增量；只有最终生成电机力矩命令时，才用 `round()` 转成整数并限幅。

命令映射：

```text
THUMB_MCP / THUMB_PIP 使用 thumb torque
FF_MCP / FF_PIP 使用 forefinger torque
MF_MCP / MF_PIP 使用 middle_finger torque
```

---

## 文件结构

| 文件 | 操作 | 责任 |
| --- | --- | --- |
| `src/xiaoyao/adaptive_grasp/grasp_sequence.py` | 修改 | `ContactSnapshot` 增加逐指法向力 `finger_fz`，闭合找接触时保存快照 |
| `tests/adaptive_grasp/test_grasp_sequence.py` | 修改 | 验证接触快照记录逐指法向力 |
| `src/xiaoyao/adaptive_grasp/config.py` | 修改 | 增加本次力矩闭环保持功能的全部控制参数，作为唯一调参入口 |
| `src/xiaoyao/adaptive_grasp/object_profile.py` | 修改 | 只补充 `paper_cup` 的物体/材质属性，不放控制器调参项 |
| `tests/adaptive_grasp/test_config.py` | 修改 | 验证新增配置默认值和边界检查 |
| `tests/adaptive_grasp/test_object_profile.py` | 修改或新增 | 验证 `paper_cup` 的物体/材质属性 |
| `src/xiaoyao/adaptive_grasp/joint_builder.py` | 修改 | 增加逐指力矩命令构造，活动手指 MCP/PIP 分别下发对应力矩 |
| `tests/adaptive_grasp/test_joint_builder.py` | 修改 | 验证逐指力矩映射到 MCP/PIP |
| `src/xiaoyao/adaptive_grasp/torque_hold_planner.py` | 新增 | 计算 `F_ref_total`、逐指 `F_ref_i`、逐指 PID 力矩 |
| `tests/adaptive_grasp/test_torque_hold_planner.py` | 新增 | TDD 覆盖比例初始化、滑动增力、稳定回落、PID 力矩 |
| `src/xiaoyao/adaptive_grasp/adaptive_hold_loop.py` | 修改 | torque 模式下调用 `TorqueHoldPlanner` 并发送逐指力矩命令 |
| `tests/adaptive_grasp/test_adaptive_hold_loop.py` | 修改 | 验证保持循环使用逐指力矩 |
| `src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py` | 修改 | 把接触快照传给 torque planner |
| `tests/adaptive_grasp/test_adaptive_grasp_manager.py` | 修改 | 验证 manager 将快照接入保持阶段 |
| `examples/2x.adaptive_grasp_demo.py` | 修改 | 增加 demo 状态观察项和纸杯力矩模式运行入口 |
| `tests/examples/test_2x_adaptive_grasp_demo.py` | 修改 | 验证 demo 状态输出辅助函数 |
| `docs/需求.md` | 修改 | 记录纸杯倒水 demo 实验参数和调参记录模板 |

---

## Task 1: 接触快照记录逐指法向力

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/grasp_sequence.py`
- Modify: `tests/adaptive_grasp/test_grasp_sequence.py`

- [ ] **Step 1: 写失败测试**

在 `tests/adaptive_grasp/test_grasp_sequence.py` 增加测试，构造三指触觉数据，运行闭合找接触后断言 `result.contact_snapshot.finger_fz` 包含三指法向力。

```python
def test_phase_closing_records_per_finger_force_snapshot(monkeypatch):
    # Arrange: active_fingers = thumb/forefinger/middle_finger
    # Arrange: tactile z force = 0.30, 0.15, 0.10
    # Act: controller.run(...)
    # Assert: contact_snapshot.finger_fz records each active finger force
```

- [ ] **Step 2: 确认测试失败**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_grasp_sequence.py::test_phase_closing_records_per_finger_force_snapshot -q
```

Expected: FAIL，因为 `ContactSnapshot` 还没有 `finger_fz`。

- [ ] **Step 3: 最小实现**

修改 `ContactSnapshot`：

```python
@dataclass(frozen=True)
class ContactSnapshot:
    joint_angles: dict[JointId, float]
    total_fz: float
    torque: int
    reason: str
    timestamp_s: float
    finger_fz: dict[TactileSensorId, float]
```

增加私有函数：

```python
def _contact_finger_fz(self) -> dict[TactileSensorId, float]:
    tactile_data = self._sensor.tactile_data or {}
    return {
        finger: abs(tactile_data[finger].get_force_z())
        for finger in self.config.active_fingers
        if finger in tactile_data
    }
```

在 `_record_contact_snapshot()` 中传入 `finger_fz=self._contact_finger_fz()`。

- [ ] **Step 4: 跑相关测试**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_grasp_sequence.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/grasp_sequence.py tests/adaptive_grasp/test_grasp_sequence.py
git commit -m "feat(adaptive_grasp): record per-finger contact force snapshot"
```

---

## Task 2: 增加力矩闭环保持配置和纸杯物体参数

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/config.py`
- Modify: `src/xiaoyao/adaptive_grasp/object_profile.py`
- Modify: `tests/adaptive_grasp/test_config.py`
- Modify or Create: `tests/adaptive_grasp/test_object_profile.py`

本任务的参数归属要求：

```text
控制参数只放在 AdaptiveGraspConfig。
ObjectProfile 不承载本次功能的控制器调参项。
ObjectProfile 只负责描述物体自身属性和安全边界。
```

- [ ] **Step 1: 写配置测试**

```python
def test_torque_hold_closed_loop_defaults():
    cfg = AdaptiveGraspConfig()

    assert cfg.torque_hold_force_margin_n == pytest.approx(0.10)
    assert cfg.torque_hold_slip_warning_threshold == pytest.approx(0.40)
    assert cfg.torque_hold_stable_threshold == pytest.approx(0.20)
    assert cfg.torque_hold_slip_gain_n_per_s == pytest.approx(0.20)
    assert cfg.torque_hold_max_rise_step_n == pytest.approx(0.02)
    assert cfg.torque_hold_confirmed_boost_n == pytest.approx(0.05)
    assert cfg.torque_hold_decay_rate_n_per_s == pytest.approx(0.02)
    assert cfg.torque_hold_stable_decay_delay_s == pytest.approx(1.0)
    assert cfg.torque_hold_min_contact_ratio == pytest.approx(0.15)
    assert cfg.torque_hold_K_p == pytest.approx(5.0)
    assert cfg.torque_hold_K_i == pytest.approx(0.0)
    assert cfg.torque_hold_K_d == pytest.approx(0.0)
    assert cfg.torque_hold_I_min == pytest.approx(-1.0)
    assert cfg.torque_hold_I_max == pytest.approx(1.0)
```

```python
def test_torque_hold_min_contact_ratio_must_fit_active_fingers():
    with pytest.raises(ValueError, match="torque_hold_min_contact_ratio"):
        AdaptiveGraspConfig(
            active_fingers={
                TactileSensorId.THUMB,
                TactileSensorId.FOREFINGER,
                TactileSensorId.MIDDLE_FINGER,
            },
            torque_hold_min_contact_ratio=0.40,
        )
```

```python
def test_paper_cup_profile_has_pouring_demo_material_properties():
    profile = ObjectProfileRegistry.get("paper_cup")

    assert profile is not None
    assert profile.weight_kg == pytest.approx(0.01)
    assert profile.safe_force_max == pytest.approx(3.5)
    assert profile.friction_coeff == pytest.approx(0.8)
    assert profile.is_fragile is True
```

- [ ] **Step 2: 确认测试失败**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_config.py tests\adaptive_grasp\test_object_profile.py -q
```

Expected: FAIL，因为配置项还不存在。

- [ ] **Step 3: 增加配置项**

在 `AdaptiveGraspConfig` 增加：

```python
torque_hold_force_margin_n: float = 0.10
torque_hold_slip_warning_threshold: float = 0.40
torque_hold_stable_threshold: float = 0.20
torque_hold_slip_gain_n_per_s: float = 0.20
torque_hold_max_rise_step_n: float = 0.02
torque_hold_confirmed_boost_n: float = 0.05
torque_hold_decay_rate_n_per_s: float = 0.02
torque_hold_stable_decay_delay_s: float = 1.0
torque_hold_min_contact_ratio: float = 0.15
torque_hold_K_p: float = 5.0
torque_hold_K_i: float = 0.0
torque_hold_K_d: float = 0.0
torque_hold_I_min: float = -1.0
torque_hold_I_max: float = 1.0
```

在 `__post_init__()` 中增加边界检查：

```python
_validate("torque_hold_force_margin_n", self.torque_hold_force_margin_n, greater_equal=0.0)
_validate("torque_hold_slip_warning_threshold", self.torque_hold_slip_warning_threshold, greater_equal=0.0, less_equal=1.0)
_validate("torque_hold_stable_threshold", self.torque_hold_stable_threshold, greater_equal=0.0, less_equal=1.0)
_validate("torque_hold_slip_gain_n_per_s", self.torque_hold_slip_gain_n_per_s, greater_equal=0.0)
_validate("torque_hold_max_rise_step_n", self.torque_hold_max_rise_step_n, greater_equal=0.0)
_validate("torque_hold_confirmed_boost_n", self.torque_hold_confirmed_boost_n, greater_equal=0.0)
_validate("torque_hold_decay_rate_n_per_s", self.torque_hold_decay_rate_n_per_s, greater_equal=0.0)
_validate("torque_hold_stable_decay_delay_s", self.torque_hold_stable_decay_delay_s, greater_equal=0.0)
_validate("torque_hold_min_contact_ratio", self.torque_hold_min_contact_ratio, greater_equal=0.0, less_equal=1.0)
if self.torque_hold_min_contact_ratio * len(self.active_fingers) > 1.0:
    raise ValueError("torque_hold_min_contact_ratio * active_finger_count must be <= 1.0")
_validate("torque_hold_K_p", self.torque_hold_K_p, greater_equal=0.0)
_validate("torque_hold_K_i", self.torque_hold_K_i, greater_equal=0.0)
_validate("torque_hold_K_d", self.torque_hold_K_d, greater_equal=0.0)
if self.torque_hold_I_min > self.torque_hold_I_max:
    raise ValueError("torque_hold_I_min must be <= torque_hold_I_max")
```

更新 `paper_cup`：

```python
ObjectProfile(
    name="paper_cup",
    weight_kg=0.01,  # 空杯质量；200 ml 水是 demo 负载，不作为初始空杯重量。
    safe_force_min=0.5,
    safe_force_max=3.5,  # 首次实物实验先用保守上限；确认杯壁不变形后，再逐步调到 4.0-4.4 N。
    friction_coeff=0.8,
    is_fragile=True,
    material="paper",
)
```

不要在 `ObjectProfile` 中新增以下字段：

```python
torque_hold_force_margin_n
torque_hold_slip_warning_threshold
torque_hold_stable_threshold
torque_hold_slip_gain_n_per_s
torque_hold_max_rise_step_n
torque_hold_confirmed_boost_n
torque_hold_decay_rate_n_per_s
torque_hold_stable_decay_delay_s
torque_hold_min_contact_ratio
torque_hold_K_p
torque_hold_K_i
torque_hold_K_d
torque_hold_I_min
torque_hold_I_max
```

这些字段统一属于 `AdaptiveGraspConfig`。

注意：力矩闭环不读取 `ObjectProfile.base_hold_torque`。如果旧代码暂时保留该字段，只允许位置保持兼容路径继续使用；`TorqueHoldPlanner` 的初始力矩必须来自 `AdaptiveGraspConfig.adaptive_hold_torque`。

- [ ] **Step 4: 跑配置测试**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_config.py tests\adaptive_grasp\test_object_profile.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/config.py src/xiaoyao/adaptive_grasp/object_profile.py tests/adaptive_grasp/test_config.py tests/adaptive_grasp/test_object_profile.py
git commit -m "feat(adaptive_grasp): add torque hold tuning parameters"
```

---

## Task 3: JointCommandBuilder 支持逐指力矩命令

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/joint_builder.py`
- Modify: `tests/adaptive_grasp/test_joint_builder.py`

- [ ] **Step 1: 写失败测试**

```python
def test_hold_per_finger_torque_command_maps_finger_to_mcp_pip():
    cfg = AdaptiveGraspConfig(
        active_fingers={
            TactileSensorId.THUMB,
            TactileSensorId.FOREFINGER,
            TactileSensorId.MIDDLE_FINGER,
        },
    )
    builder = JointCommandBuilder(
        cfg,
        (
            JointId.THUMB_PIP,
            JointId.THUMB_MCP,
            JointId.FF_PIP,
            JointId.FF_MCP,
            JointId.MF_PIP,
            JointId.MF_MCP,
        ),
    )

    joints = builder.hold_per_finger_torque_command({
        TactileSensorId.THUMB: 5,
        TactileSensorId.FOREFINGER: 7,
        TactileSensorId.MIDDLE_FINGER: 9,
    })

    joint_map = {joint.id: joint for joint in joints}
    assert joint_map[JointId.THUMB_PIP].torque == 5
    assert joint_map[JointId.THUMB_MCP].torque == 5
    assert joint_map[JointId.FF_PIP].torque == 7
    assert joint_map[JointId.FF_MCP].torque == 7
    assert joint_map[JointId.MF_PIP].torque == 9
    assert joint_map[JointId.MF_MCP].torque == 9
    assert joint_map[JointId.RF_PIP].torque == 0
    assert joint_map[JointId.LF_PIP].torque == 0
```

- [ ] **Step 2: 确认测试失败**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_joint_builder.py::test_hold_per_finger_torque_command_maps_finger_to_mcp_pip -q
```

Expected: FAIL，因为方法还不存在。

- [ ] **Step 3: 最小实现**

在 `joint_builder.py` 引入 `TactileSensorId`，增加映射：

```python
FINGER_TORQUE_JOINTS = {
    TactileSensorId.THUMB: (JointId.THUMB_MCP, JointId.THUMB_PIP),
    TactileSensorId.FOREFINGER: (JointId.FF_MCP, JointId.FF_PIP),
    TactileSensorId.MIDDLE_FINGER: (JointId.MF_MCP, JointId.MF_PIP),
    TactileSensorId.RING_FINGER: (JointId.RF_MCP, JointId.RF_PIP),
    TactileSensorId.LITTLE_FINGER: (JointId.LF_MCP, JointId.LF_PIP),
}
```

新增方法：

```python
def hold_per_finger_torque_command(
    self,
    finger_torques: Mapping[TactileSensorId, float],
) -> list[Joint]:
    active_joints = set(self._torque_joints)
    joint_torques: dict[JointId, int] = {}

    for finger, torque in finger_torques.items():
        for joint_id in FINGER_TORQUE_JOINTS.get(finger, ()):
            if joint_id in active_joints:
                joint_torques[joint_id] = round(
                    clip(torque, -100.0, self._config.max_torque)
                )

    joints = [
        Joint(id=joint_id, torque=joint_torques[joint_id])
        if joint_id in joint_torques
        else Joint(id=joint_id, angle=0.0, speed=0, torque=0)
        for joint_id in TORQUE_CONTROL_JOINTS
    ]
    joints += [
        Joint(id=JointId.THUMB_ROTATION, angle=0.0, speed=0, torque=5),
        Joint(id=JointId.THUMB_SWING, angle=0.0, speed=0, torque=5),
    ]
    return joints
```

- [ ] **Step 4: 跑测试**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_joint_builder.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/joint_builder.py tests/adaptive_grasp/test_joint_builder.py
git commit -m "feat(adaptive_grasp): build per-finger torque commands"
```

---

## Task 4: 新增 TorqueHoldPlanner 的初始化逻辑

**Files:**
- Create: `src/xiaoyao/adaptive_grasp/torque_hold_planner.py`
- Create: `tests/adaptive_grasp/test_torque_hold_planner.py`

- [ ] **Step 1: 写失败测试**

测试目标：根据 `ContactSnapshot.finger_fz` 计算 `contact_ratios`，比例不是均分，并且满足 `min_contact_ratio` 后重新归一化。
计算比例时保留接触快照中的逐指法向力原始读数，不做低力过滤；比例下限由 `torque_hold_min_contact_ratio` 负责兜底。

```python
def test_torque_hold_planner_initializes_contact_ratios_from_snapshot():
    snapshot = ContactSnapshot(
        joint_angles={},
        total_fz=0.50,
        torque=5,
        reason="force_threshold",
        timestamp_s=0.0,
        finger_fz={
            TactileSensorId.THUMB: 0.30,
            TactileSensorId.FOREFINGER: 0.15,
            TactileSensorId.MIDDLE_FINGER: 0.10,
        },
    )
    cfg = AdaptiveGraspConfig(
        active_fingers={
            TactileSensorId.THUMB,
            TactileSensorId.FOREFINGER,
            TactileSensorId.MIDDLE_FINGER,
        },
        torque_hold_min_contact_ratio=0.15,
    )

    planner = TorqueHoldPlanner(cfg, profile=None, contact_snapshot=snapshot)

    assert planner.contact_ratios[TactileSensorId.THUMB] > planner.contact_ratios[TactileSensorId.FOREFINGER]
    assert planner.contact_ratios[TactileSensorId.MIDDLE_FINGER] >= 0.15 - 1e-6
    assert sum(planner.contact_ratios.values()) == pytest.approx(1.0)
```

- [ ] **Step 2: 确认测试失败**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_torque_hold_planner.py::test_torque_hold_planner_initializes_contact_ratios_from_snapshot -q
```

Expected: FAIL，因为 `TorqueHoldPlanner` 不存在。

- [ ] **Step 3: 最小实现**

新增数据结构：

```python
@dataclass(frozen=True)
class TorqueHoldDecision:
    finger_torques: dict[TactileSensorId, float]
    force_refs: dict[TactileSensorId, float]
    contact_ratios: dict[TactileSensorId, float]
    F_ref_total: float
```

`TorqueHoldDecision` 后续需要从 `HoldStepResult` 暴露给 demo/logging，用于观察 `F_ref_total`、逐指 `force_refs` 和逐指 `finger_torques`。

新增类：

```python
class TorqueHoldPlanner:
    def __init__(
        self,
        config: AdaptiveGraspConfig,
        profile: Optional[ObjectProfile],
        contact_snapshot: ContactSnapshot,
    ):
        self.config = config
        self.profile = profile
        self.contact_snapshot = contact_snapshot
        self.contact_ratios = self._compute_contact_ratios(contact_snapshot)
        self.F_ref_total = self._initial_force_ref(contact_snapshot)
        self._pid_by_finger = {
            finger: PidController(
                PidParams(
                    K_p=config.torque_hold_K_p,
                    K_i=config.torque_hold_K_i,
                    K_d=config.torque_hold_K_d,
                    I_min=config.torque_hold_I_min,
                    I_max=config.torque_hold_I_max,
                )
            )
            for finger in config.active_fingers
        }
        self._last_slip_confirmed = False
        self._stable_time_s = 0.0
```

注意：

```text
接触快照中的 contact_fz 保持原始值，不做低力过滤。
如果 contact_snapshot.total_fz <= 0，使用活动手指均分比例作为降级策略。
```

补全辅助函数的预期行为，避免实现时出现多套边界语义：

```python
def _compute_contact_ratios(
    self,
    contact_snapshot: ContactSnapshot,
) -> dict[TactileSensorId, float]:
    raw = {
        finger: max(0.0, contact_snapshot.finger_fz.get(finger, 0.0))
        for finger in self.config.active_fingers
    }
    total = sum(raw.values())
    if total <= 0.0:
        return self._uniform_contact_ratios()

    ratios = {
        finger: max(force / total, self.config.torque_hold_min_contact_ratio)
        for finger, force in raw.items()
    }
    ratio_sum = sum(ratios.values())
    if ratio_sum <= 0.0:
        return self._uniform_contact_ratios()
    return {finger: ratio / ratio_sum for finger, ratio in ratios.items()}
```

```python
def _uniform_contact_ratios(self) -> dict[TactileSensorId, float]:
    active = set(self.config.active_fingers)
    if not active:
        return {}
    ratio = 1.0 / len(active)
    return {finger: ratio for finger in active}
```

```python
def _initial_force_ref(self, contact_snapshot: ContactSnapshot) -> float:
    contact_force = max(0.0, contact_snapshot.total_fz)
    target = contact_force + self.config.torque_hold_force_margin_n
    if self.profile is not None:
        target = max(target, self.profile.safe_force_min)
    return self._clamp_force_ref(target)
```

```python
def _minimum_force_ref(self) -> float:
    if self.profile is None:
        return 0.0
    return self.profile.safe_force_min
```

```python
def _maximum_force_ref(self) -> float:
    if self.profile is None:
        return float(self.config.max_normal_force_per_finger * len(self.config.active_fingers))
    return self.profile.safe_force_max
```

```python
def _clamp_force_ref(self, value: float) -> float:
    lower = self._minimum_force_ref()
    upper = self._maximum_force_ref()
    if upper < lower:
        return upper
    return clip(value, lower, upper)
```

如果 `safe_force_max < _minimum_force_ref()`，说明材质库安全上限比 `safe_force_min` 更保守，优先遵守材质库上限，避免为了满足目标力下限而压坏物体。

- [ ] **Step 4: 跑测试**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_torque_hold_planner.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/torque_hold_planner.py tests/adaptive_grasp/test_torque_hold_planner.py
git commit -m "feat(adaptive_grasp): initialize torque hold planner"
```

---

## Task 5: 实现滑动趋势驱动的 F_ref_total 更新

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/torque_hold_planner.py`
- Modify: `tests/adaptive_grasp/test_torque_hold_planner.py`

- [ ] **Step 1: 写失败测试**

测试滑动风险超过阈值时，总目标力随时间增加：

```python
def test_torque_hold_planner_increases_force_ref_when_slip_risk_high():
    planner = _make_planner(
        profile=ObjectProfile(
            name="paper_cup",
            weight_kg=0.01,
            safe_force_min=0.5,
            safe_force_max=1.0,
            friction_coeff=0.8,
            is_fragile=True,
            material="paper",
        ),
    )
    initial = planner.F_ref_total

    planner.compute(_analysis(slip_risk=0.8, slip_confirmed=False), dt=0.5)

    assert planner.F_ref_total > initial
    assert planner.F_ref_total <= 1.0
```

测试 `slip_confirmed` 上升沿不重复触发 confirmed boost。注意：如果下一次 `slip_risk` 仍然高，控制器仍应继续走滑动风险缓慢增力，直到抵达材质库中的 `safe_force_max`：

```python
def test_torque_hold_planner_does_not_repeat_confirmed_boost():
    planner = _make_planner()
    initial = planner.F_ref_total

    planner.compute(_analysis(slip_risk=0.8, slip_confirmed=True), dt=0.02)
    boosted = planner.F_ref_total
    planner.compute(_analysis(slip_risk=0.0, slip_confirmed=True), dt=0.02)

    assert boosted > initial
    assert planner.F_ref_total < boosted + planner.config.torque_hold_confirmed_boost_n
```

补充测试：`slip_confirmed` 已经保持为 True 且 `slip_risk` 仍高时，不再重复 confirmed boost，但继续按滑动风险缓慢增力，且不超过 `safe_force_max`。

```python
def test_torque_hold_planner_continues_slow_rise_when_confirmed_slip_stays_risky():
    planner = _make_planner(
        profile=ObjectProfile(
            name="paper_cup",
            weight_kg=0.01,
            safe_force_min=0.5,
            safe_force_max=1.0,
            friction_coeff=0.8,
            is_fragile=True,
            material="paper",
        ),
    )

    planner.compute(_analysis(slip_risk=0.8, slip_confirmed=True), dt=0.02)
    boosted = planner.F_ref_total
    planner.compute(_analysis(slip_risk=0.8, slip_confirmed=True), dt=0.5)

    assert planner.F_ref_total > boosted
    assert planner.F_ref_total <= planner.profile.safe_force_max
```

测试稳定低滑动时缓慢回落：

```python
def test_torque_hold_planner_decays_force_ref_when_stable():
    planner = _make_planner()
    planner.F_ref_total = 0.9

    planner.compute(_analysis(slip_risk=0.0, slip_confirmed=False), dt=2.0)

    assert planner.F_ref_total < 0.9
    assert planner.F_ref_total >= planner._minimum_force_ref()
```

- [ ] **Step 2: 确认测试失败**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_torque_hold_planner.py -q
```

Expected: FAIL，因为 `compute()` 还未实现完整 `F_ref_total` 更新。

- [ ] **Step 3: 实现参数读取和更新逻辑**

控制参数只从 `self.config` 读取，不从 `ObjectProfile` 读取。

核心更新逻辑：

```python
def _update_total_force_ref(self, analysis: TactileAnalysis, dt: float) -> None:
    warning_threshold = self.config.torque_hold_slip_warning_threshold
    stable_threshold = self.config.torque_hold_stable_threshold
    slip_gain = self.config.torque_hold_slip_gain_n_per_s
    max_rise_step = self.config.torque_hold_max_rise_step_n
    boost = self.config.torque_hold_confirmed_boost_n
    decay_rate = self.config.torque_hold_decay_rate_n_per_s
    decay_delay = self.config.torque_hold_stable_decay_delay_s

    confirmed_rising_edge = analysis.slip_confirmed and not self._last_slip_confirmed

    if confirmed_rising_edge:
        self.F_ref_total += boost
        self._stable_time_s = 0.0

    if analysis.slip_risk >= warning_threshold:
        slip_excess = analysis.slip_risk - warning_threshold
        rise_step = slip_gain * slip_excess * dt
        self.F_ref_total += min(rise_step, max_rise_step)
        self._stable_time_s = 0.0
    elif analysis.slip_risk <= stable_threshold:
        self._stable_time_s += dt
        if self._stable_time_s >= decay_delay:
            self.F_ref_total -= decay_rate * dt
    else:
        self._stable_time_s = 0.0

    self.F_ref_total = self._clamp_force_ref(self.F_ref_total)
    self._last_slip_confirmed = analysis.slip_confirmed
```

- [ ] **Step 4: 跑测试**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_torque_hold_planner.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/torque_hold_planner.py tests/adaptive_grasp/test_torque_hold_planner.py
git commit -m "feat(adaptive_grasp): adjust torque force target from slip risk"
```

---

## Task 6: 使用每指 PID 生成逐指力矩

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/torque_hold_planner.py`
- Modify: `tests/adaptive_grasp/test_torque_hold_planner.py`

- [ ] **Step 1: 写失败测试**

```python
def test_torque_hold_planner_returns_base_torque_when_force_error_zero():
    planner = _make_planner(adaptive_hold_torque=5)
    planner.F_ref_total = 0.6
    analysis = _analysis(
        slip_risk=0.0,
        slip_confirmed=False,
        finger_fz={
            TactileSensorId.THUMB: planner.F_ref_total * planner.contact_ratios[TactileSensorId.THUMB],
            TactileSensorId.FOREFINGER: planner.F_ref_total * planner.contact_ratios[TactileSensorId.FOREFINGER],
            TactileSensorId.MIDDLE_FINGER: planner.F_ref_total * planner.contact_ratios[TactileSensorId.MIDDLE_FINGER],
        },
    )

    decision = planner.compute(analysis, dt=0.02)

    assert set(decision.finger_torques) == planner.config.active_fingers
    assert all(torque == 5 for torque in decision.finger_torques.values())
```

```python
def test_torque_hold_planner_increases_torque_for_low_force_finger():
    planner = _make_planner(adaptive_hold_torque=5)
    analysis = _analysis(
        slip_risk=0.0,
        slip_confirmed=False,
        finger_fz={
            TactileSensorId.THUMB: 0.0,
            TactileSensorId.FOREFINGER: 0.2,
            TactileSensorId.MIDDLE_FINGER: 0.2,
        },
    )

    decision = planner.compute(analysis, dt=0.02)

    assert decision.finger_torques[TactileSensorId.THUMB] > 5
```

- [ ] **Step 2: 确认测试失败**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_torque_hold_planner.py -q
```

Expected: FAIL，因为 `finger_torques` 还没有按照 PID 计算。

- [ ] **Step 3: 实现逐指目标力和力矩计算**

```python
def _compute_finger_force_refs(self) -> dict[TactileSensorId, float]:
    return {
        finger: self.F_ref_total * self.contact_ratios.get(finger, 0.0)
        for finger in self.config.active_fingers
    }
```

```python
def _initial_hold_torque(self) -> int:
    return self.config.adaptive_hold_torque
```

```python
def _compute_finger_torque(
    self,
    finger: TactileSensorId,
    force_ref: float,
    force_actual: float,
    dt: float,
) -> float:
    error = force_ref - force_actual
    pid_u = self._pid_by_finger[finger].compute(error=error, dt=dt)
    torque = self._initial_hold_torque() + pid_u
    return clip(torque, 0.0, self.config.max_torque)
```

`compute()` 返回：

```python
def compute(self, analysis: TactileAnalysis, dt: float) -> TorqueHoldDecision:
    self._update_total_force_ref(analysis, dt)
    force_refs = self._compute_finger_force_refs()
    finger_torques = {
        finger: self._compute_finger_torque(
            finger,
            force_refs[finger],
            analysis.finger_fz.get(finger, 0.0),
            dt,
        )
        for finger in self.config.active_fingers
    }
    return TorqueHoldDecision(
        finger_torques=finger_torques,
        force_refs=force_refs,
        contact_ratios=dict(self.contact_ratios),
        F_ref_total=self.F_ref_total,
    )
```

- [ ] **Step 4: 跑测试**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_torque_hold_planner.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/torque_hold_planner.py tests/adaptive_grasp/test_torque_hold_planner.py
git commit -m "feat(adaptive_grasp): compute per-finger torque with pid"
```

---

## Task 7: 接入自适应保持阶段

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_hold_loop.py`
- Modify: `src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py`
- Modify: `tests/adaptive_grasp/test_adaptive_hold_loop.py`
- Modify: `tests/adaptive_grasp/test_adaptive_grasp_manager.py`

- [ ] **Step 1: 写保持循环测试**

```python
def test_torque_hold_loop_uses_torque_hold_planner_per_finger_torques():
    # Arrange: adaptive_hold_command_mode="torque"
    # Arrange: torque_hold_planner.compute() returns thumb=6, forefinger=8
    # Act: controller.run_step(current_time=0.0)
    # Assert: hand.move_joints receives THUMB_MCP/PIP torque=6 and FF_MCP/PIP torque=8
```

- [ ] **Step 2: 确认测试失败**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_adaptive_hold_loop.py::test_torque_hold_loop_uses_torque_hold_planner_per_finger_torques -q
```

Expected: FAIL，因为 `HoldController` 还不接收 `torque_hold_planner`。

- [ ] **Step 3: 修改 HoldController**

在 `_HoldCommand` 增加：

```python
finger_torques: Optional[dict[TactileSensorId, float]] = None
torque_hold_decision: Optional[TorqueHoldDecision] = None
```

在 `HoldStepResult` 增加：

```python
torque_hold_decision: Optional[TorqueHoldDecision] = None
```

在 `HoldController.__init__()` 增加：

```python
torque_hold_planner: Optional[TorqueHoldPlanner] = None
```

同时在 `__init__()` 中保存 planner 并初始化传感器样本时间状态。所有传感器数据都从 `SensorClient` 获取，包括触觉数据、关节反馈和采样时间戳；`HoldController` 只负责接收并传递这些参数：

```python
self._torque_hold_planner = torque_hold_planner
self._last_sample_time_s: Optional[float] = None
```

在 `HoldController` 中增加真实周期计算。`TorqueHoldPlanner` 的 PID 和 `F_ref_total` 增减都依赖 `dt`，因此优先使用 `SensorClient.sample_time_s` 的前后样本时间差；如果时间戳缺失或异常，再回退到 `config.control_period_s`：

```python
def _compute_dt(self, sample_time_s: Optional[float]) -> float:
    if sample_time_s is None or self._last_sample_time_s is None:
        dt = self.config.control_period_s
    else:
        dt = sample_time_s - self._last_sample_time_s
        if dt <= 0.0 or dt > 1.0:
            dt = self.config.control_period_s
    self._last_sample_time_s = sample_time_s
    return dt
```

`run_step()` 开始时一次性从 `SensorClient` 读取 `tactile_data`、`joint_feedback` 和 `sample_time_s`，避免回调线程刚好更新导致触觉数据和时间戳不是同一帧。然后先计算 `dt`，再传给 `_plan_hold_command()`：

```python
tactile_data = self._sensor.tactile_data
joint_feedback = self._sensor.joint_feedback
sample_time_s = self._sensor.sample_time_s
dt = self._compute_dt(sample_time_s)
command = self._plan_hold_command(analysis, current_angles, dt)
```

在 `_plan_hold_command()` 中，优先处理 torque planner：

```python
if (
    self.config.adaptive_hold_command_mode == "torque"
    and self._torque_hold_planner is not None
):
    decision = self._torque_hold_planner.compute(
        analysis,
        dt=dt,
    )
    return _HoldCommand(
        angles=current_angles,
        torque=max(decision.finger_torques.values(), default=self._current_torque),
        finger_torques=decision.finger_torques,
        torque_hold_decision=decision,
    )
```

在 `run_step()` 返回 `HoldStepResult` 时传出：

```python
return HoldStepResult(
    result=HoldResult.CONTINUE,
    tactile_analysis=analysis,
    safety_report=safety,
    force_decisions=command.decisions,
    torque_hold_decision=command.torque_hold_decision,
    current_torque=self._current_torque,
)
```

在 `AdaptiveGrasper` 中增加保存和读取力矩闭环决策的状态，供 demo 状态行和 CSV 使用：

```python
self._last_torque_hold_decision: Optional[TorqueHoldDecision] = None
```

```python
@property
def last_torque_hold_decision(self) -> Optional[TorqueHoldDecision]:
    return self._last_torque_hold_decision
```

```python
def _record_hold_step(self, step, step_start: float) -> None:
    self._last_torque_hold_decision = step.torque_hold_decision
```

在 `_reset_runtime_state()` 中同步清空：

```python
self._last_torque_hold_decision = None
```

在 `_build_hold_payload()` 中：

```python
if self.config.adaptive_hold_command_mode == "torque":
    if command.finger_torques is not None:
        next_torque = round(
            clip(
                max(command.finger_torques.values(), default=float(command.torque)),
                -100.0,
                self.config.max_torque,
            )
        )
        return (
            self._joint_builder.hold_per_finger_torque_command(command.finger_torques),
            CtrlMode.TORQUE,
            next_torque,
        )
    torque = command.torque
    return self._joint_builder.hold_torque_command(torque), CtrlMode.TORQUE, torque
```

`TorqueHoldDecision` 中的 `finger_torques` 保留 float，用于观察 PID 的连续输出；`_current_torque` 和 `HoldStepResult.current_torque` 只记录实际发送电机命令后的 round 后整数最大力矩。

- [ ] **Step 4: 修改 AdaptiveGrasper**

在进入保持阶段时，如果满足以下条件就创建 `TorqueHoldPlanner`：

```python
if (
    self.config.adaptive_hold_command_mode == "torque"
    and self._last_contact_snapshot is not None
):
    torque_hold_planner = TorqueHoldPlanner(
        self.config,
        self._object_profile,
        self._last_contact_snapshot,
    )
```

然后传给 `HoldController`。

- [ ] **Step 5: 跑相关测试**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_adaptive_hold_loop.py tests\adaptive_grasp\test_adaptive_grasp_manager.py -q
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/adaptive_hold_loop.py src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py tests/adaptive_grasp/test_adaptive_hold_loop.py tests/adaptive_grasp/test_adaptive_grasp_manager.py
git commit -m "feat(adaptive_grasp): integrate closed-loop torque hold planner"
```

---

## Task 8: Demo 可观察性

**Files:**
- Modify: `examples/2x.adaptive_grasp_demo.py`
- Modify: `tests/examples/test_2x_adaptive_grasp_demo.py`

- [ ] **Step 1: 写状态输出测试**

```python
def test_format_hold_status_includes_torque_decision():
    decision = TorqueHoldDecision(
        finger_torques={
            TactileSensorId.THUMB: 5.4,
            TactileSensorId.FOREFINGER: 6.2,
        },
        force_refs={},
        contact_ratios={},
        F_ref_total=0.8,
    )

    line = demo.format_hold_status(
        state="adaptive_hold",
        torque=6,
        mode="torque",
        total_fz=0.7,
        slip_risk=0.4,
        slip_confirmed=False,
        torque_decision=decision,
    )

    assert "F_ref_total=0.80" in line
    assert "THUMB=5.40" in line
```

- [ ] **Step 2: 确认测试失败**

Run:

```powershell
python -m pytest tests\examples\test_2x_adaptive_grasp_demo.py::test_format_hold_status_includes_torque_decision -q
```

Expected: FAIL，如果 demo 还没有状态输出辅助函数。

- [ ] **Step 3: 增加 demo 状态输出**

```python
def format_hold_status(
    state: str,
    torque: int,
    mode: str,
    total_fz: Optional[float],
    slip_risk: Optional[float],
    slip_confirmed: Optional[bool],
    torque_decision: Optional[TorqueHoldDecision],
) -> str:
    ...
```

建议状态输出至少包含：

```text
state
mode
current_torque
total_fz
slip_risk
slip_confirmed
F_ref_total
finger_torques
```

其中 `F_ref_total` 和 `finger_torques` 来自 `HoldStepResult.torque_hold_decision`。
demo 主循环中通过 `grasper.last_torque_hold_decision` 读取最近一次闭环决策；如果为 `None`，状态行只显示基础状态和当前 torque。

本计划第一版不做低力门控；如果实测出现低力误触发，先记录数据并分析原因，后续根据实测误触发行为再设计门控策略。

- [ ] **Step 4: 跑 demo 测试**

Run:

```powershell
python -m pytest tests\examples\test_2x_adaptive_grasp_demo.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add examples/2x.adaptive_grasp_demo.py tests/examples/test_2x_adaptive_grasp_demo.py
git commit -m "feat(examples): show torque hold status"
```

---

## Task 9: 验证和纸杯倒水实验流程

**Files:**
- Modify: `docs/需求.md`
- Modify: `docs/superpowers/plans/2026-05-09-torque-closed-loop-hold.md`

- [ ] **Step 1: 跑聚焦测试**

Run:

```powershell
python -m pytest tests\adaptive_grasp\test_pid_controller.py tests\adaptive_grasp\test_torque_hold_planner.py tests\adaptive_grasp\test_joint_builder.py tests\adaptive_grasp\test_grasp_sequence.py tests\adaptive_grasp\test_adaptive_hold_loop.py tests\adaptive_grasp\test_adaptive_grasp_manager.py tests\examples\test_2x_adaptive_grasp_demo.py -q
```

Expected: PASS。

- [ ] **Step 2: 跑 adaptive_grasp 全量测试**

Run:

```powershell
python -m pytest tests\adaptive_grasp -q
```

Expected: PASS。`.pytest_cache` 权限 warning 如果出现，记录为非阻塞。

- [ ] **Step 3: 空载 demo 检查**

Run:

```powershell
python examples\2x.adaptive_grasp_demo.py --default_object paper_cup --pre_grasp_preset three_finger_pinch --hold-command-mode torque
```

观察：

```text
1. 能进入 adaptive_hold
2. 当前控制模式为 torque
3. 初始 torque 来自 AdaptiveGraspConfig.adaptive_hold_torque
4. 活动手指 MCP/PIP 都有力矩命令
```

- [ ] **Step 4: 纸杯空杯保持 30 秒**

观察：

```text
纸杯不明显变形
slip_risk 低时 F_ref_total 不持续上升
torque 不持续爬升
```

- [ ] **Step 5: 纸杯倒水实验**

200 ml 满杯 demo 的关键不是一开始就用满杯力抓，而是逐步倒水，让触觉滑动趋势驱动 `F_ref_total` 从空杯低力缓慢增加到满杯所需范围。

负载估算：

```text
空杯质量: 约 0.01 kg
满水体积: 约 200 ml
满水质量: 约 0.20 kg
满杯总质量: 约 0.21 kg
满杯重力: 约 2.06 N
摩擦系数 friction_coeff=0.8、安全系数 safety_factor=1.5 时：
满杯所需总法向力下限约 3.86 N
如果加 base_holding_force=0.5 N，满杯目标上限约 4.36 N
```

实物调参顺序：

```text
首次实验 safe_force_max=3.5 N，优先确认空杯和半杯时杯壁不明显变形。
如果 150-200 ml 阶段出现滑动但杯壁仍安全，再逐步把 safe_force_max 调到 4.0 N、4.4 N。
不要一开始直接用 4.4 N 做满杯测试。
```

建议分阶段倒水，不要第一次直接倒满：

```text
0 ml -> 空杯保持 30 s
50 ml -> 观察 slip_risk、F_ref_total、torque 是否缓慢上升
100 ml -> 检查杯壁是否明显变形
150 ml -> 检查是否出现持续滑动
200 ml -> 满杯目标测试
```

观察闭环链条是否成立：

```text
倒水 -> 重量增加 -> slip_risk 增加
slip_risk 增加 -> F_ref_total 增加
F_ref_total 增加 -> 相关手指 torque 增加
纸杯稳定后 -> torque 不继续无限增加
```

- [ ] **Step 6: 调参顺序**

优先调：

```text
1. AdaptiveGraspConfig.adaptive_hold_torque
2. AdaptiveGraspConfig.torque_hold_force_margin_n
3. AdaptiveGraspConfig.torque_hold_confirmed_boost_n
4. AdaptiveGraspConfig.torque_hold_slip_gain_n_per_s
5. AdaptiveGraspConfig.torque_hold_max_rise_step_n
6. AdaptiveGraspConfig.torque_hold_K_p
7. AdaptiveGraspConfig.torque_hold_K_i
8. AdaptiveGraspConfig.torque_hold_K_d
```

实验初期建议：

```text
torque_hold_K_i = 0
torque_hold_K_d = 0
先只调 torque_hold_K_p
确认不震荡后，再考虑非常小的 torque_hold_K_i
```

- [ ] **Step 7: 在 docs/需求.md 记录实验模板**

追加：

```markdown
## 纸杯倒水力矩闭环实验记录

- 日期:
- 物体:
- 纸杯容量:
- 当前水量:
- 估算总质量:
- active_fingers:
- adaptive_hold_torque:
- safe_force_min / safe_force_max:
- torque_hold_force_margin_n:
- torque_hold_confirmed_boost_n:
- torque_hold_slip_gain_n_per_s:
- torque_hold_max_rise_step_n:
- torque_hold_K_p / torque_hold_K_i / torque_hold_K_d:
- 是否掉落:
- 是否压坏/明显变形:
- 观察结论:
```

- [ ] **Step 8: Commit**

```bash
git add docs/需求.md docs/superpowers/plans/2026-05-09-torque-closed-loop-hold.md
git commit -m "docs(adaptive_grasp): document torque closed-loop hold validation plan"
```

---

## 关键风险

- `safe_force_max`、`max_torque`、`adaptive_hold_torque` 必须保守设置，纸杯实验中宁可掉落，也不要一上来把杯壁压坏。
- `slip_confirmed` 不适合直接触发大幅阶跃力矩；建议只给 `F_ref_total` 小 boost，剩下用 `slip_risk` 缓慢增加。
- 接触快照比例不是永久真理。如果某个手指后续明显失去接触，需要后续版本考虑比例重估。
- PID 先从 P 控制开始，`torque_hold_K_i=0`、`torque_hold_K_d=0`。确认响应稳定后，再引入力矩闭环专用的小积分项。
- 后续版本增加低力门控，避免低法向力时切向噪声通过摩擦利用率放大成误滑动。

---

## 完成标准

- [ ] `ContactSnapshot` 保存逐指 `finger_fz`
- [ ] `TorqueHoldPlanner` 根据接触快照生成非均分接触比例
- [ ] `TorqueHoldPlanner` 根据滑动趋势更新 `F_ref_total`
- [ ] `TorqueHoldPlanner` 输出逐指 `finger_torques`
- [ ] `JointCommandBuilder` 支持逐指 MCP/PIP torque
- [ ] `HoldController` 在 torque 模式下发送逐指力矩命令
- [ ] `paper_cup` 材质参数只包含物体属性和安全力边界，不包含力矩闭环控制参数
- [ ] demo 支持 `--hold-command-mode torque --default_object paper_cup`
- [ ] 聚焦测试和 `tests/adaptive_grasp` 测试通过
- [ ] 纸杯倒水实验记录写入 `docs/需求.md`

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-09-torque-closed-loop-hold.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
