# 自适应抓取功能实现补充文档

**日期**: 2026-04-27
**说明**: 本文档补充《自适应抓取功能设计文档》中未涉及但已在代码中实现的工程细节与扩展功能。

---

## 1. 预抓取姿态预设系统

原设计文档仅提及"预抓姿态"，未说明工程中已内置一套完整的姿态预设与自动推导机制。

### 1.1 四种内置预设

代码中通过 `pre_grasp_preset` 字段支持四种抓取姿态，预设表以角度维护，在配置初始化时统一转换为弧度：

| 预设名称 | 活跃手指（自动推导） | 适用场景 |
|:---|:---|:---|
| `two_finger_pinch` | 拇指 + 食指 | 两指捏取小物体 |
| `three_finger_pinch` | 拇指 + 食指 + 中指 | 三指稳定捏取 |
| `four_finger_grasp` | 拇指 + 食指 + 中指 + 无名指 | 四指包络抓握 |
| `five_finger_grasp` | 全部五指 | 全手包络大力抓握 |

### 1.2 活跃手指自动推导

若用户未显式指定 `active_fingers`，配置初始化时会根据 `pre_grasp_preset` 自动从 `_PRESET_ACTIVE_FINGERS` 映射表中推导参与闭环控制的手指集合。若预设名称未知，则回退为全部手指活跃，避免静默失败。

### 1.3 被动 DIP 关节过滤

预抓取姿态构建时，系统会自动过滤 **DIP（远端指间关节）**：

- 被过滤关节：`THUMB_DIP`、`FF_DIP`、`MF_DIP`、`RF_DIP`、`LF_DIP`
- 原因：DIP 为被动关节，由 PIP 通过机械连杆带动，不应直接下发目标角度
- 行为：若用户传入的自定义 `pre_grasp_pose` 包含 DIP 关节，这些键值对被静默移除；若移除后字典为空，则自动回退到预设姿态

---

## 2. 单指独立 PID 参数配置

除全局 `K_p` / `K_i` / `K_d` 外，系统支持为**每根手指独立配置 PID 参数**，未配置的手指自动回退到全局默认值。

```python
@dataclass
class PerFingerPidConfig:
    K_p: Optional[float] = None
    K_i: Optional[float] = None
    K_d: Optional[float] = None
    I_min: Optional[float] = None
    I_max: Optional[float] = None
```

通过 `AdaptiveGraspConfig.per_finger_pid: dict[TactileSensorId, PerFingerPidConfig]` 注入。此设计允许针对拇指（高刚度）与无名指（低刚度）采用差异化的闭环增益，提升异构手指的协同稳定性。

---

## 3. 传感器数据订阅与缓存架构 (`SensorClient`)

原设计文档未描述底层传感器数据如何进入控制器。实际实现中，所有传感器访问均通过 `SensorClient` 封装，而非控制器直接调用 `hand.get_tactile_data()`。

### 3.1 订阅机制

- **启动**：`grasp_core()` 阶段调用 `_start_sensor_subscription()`，通过 `hand.subscribe(callback)` 注册后台回调 `_on_data`
- **停止**：阶段切换或异常时调用 `_stop_sensor_subscription()`，执行 `hand.unsubscribe()`，默认保留关节反馈缓存供释放阶段读取

### 3.2 数据缓存与过滤

`SensorClient` 在每次 Tpdo 回调中完成以下工作：

1. **tactile 解析**：从 Tpdo 提取五指 resultant_force / distributed_force / state 位
2. **活跃手指过滤**：仅保留 `active_fingers` 范围内的手指数据，非活跃手指的触觉噪声不会进入闭环
3. **关节反馈构建**：将 Tpdo 中所有 16 个关节映射为 `Joint` 对象列表（含 angle / speed / torque / state / error）
4. **时间戳记录**：使用单调时钟记录最近采样时间 `_last_sample_time_s`

### 3.3 辅助接口

| 接口 | 说明 |
|:---|:---|
| `sum_active_finger_normal_force()` | 计算活跃手指法向力绝对值之和，用于接触判定与力校准 |
| `data_age_s(current_time)` | 计算当前触觉缓存的时效，供外部判断数据是否过期 |

---

## 4. 力矩-运动停滞检测（备用接触判定）

原设计文档将接触判定完全归因于触觉阈值 `contact_threshold_z`。实际实现中，为防止在捏易碎物品时，驱动力矩=阻力矩，但触觉数据无法达到触觉阈值，从而无法触发"已接触"状态，增加了**基于关节运动停滞的备用接触判定**。

### 4.1 判定条件

当触觉力始终低于 `contact_threshold_z` 时，系统同时监测关节运动状态：

- **单周期停滞**：所有 `_torque_joints`（已过滤非活跃关节）的角度变化量 `< closing_stall_angle_threshold`（默认 `0.5°`）
- **连续周期确认**：停滞连续发生 `closing_stall_cycles`（默认 `5`）个周期后，判定为"力矩驱动下已接触但物体过软/过滑导致法向力不足"
- **触发动作**：调用 `_calibrate_force()` 并进入 `ADAPTIVE_HOLD`

### 4.2 与空抓检测的区分

为避免将空抓误判为 stall contact：

- 空抓检测（`SafetyMonitor.is_grasp_empty`）在每次循环中优先执行
- 空抓依据：关节已运动较大角度（如 `> 30°`）但触觉力始终接近零
- 只有在**排除空抓**后，才会进入 stall contact 判定逻辑

---

## 5. 实时触觉数据可视化

系统在 `ADAPTIVE_HOLD` 阶段支持可选的**实时触觉数据可视化窗口**，用于调试与标定。

### 5.1 配置项

| 参数 | 说明 |
|:---|:---|
| `enable_visualization` | 是否启用可视化，默认 `False` |
| `visualization_backend` | matplotlib 后端，默认 `"TkAgg"`，可选 `"Agg"`、`"Qt5Agg"` 等 |

### 5.2 运行时机

可视化器在 `_start_adaptive_control()` 时启动独立后台线程，在每次控制周期中接收原始触觉数据与 `TactileAnalysis` 结果，实时绘制法向力曲线、滑移风险图等。

---

## 6. 连续指令下发失败保护

`ADAPTIVE_HOLD` 阶段每次控制周期都会调用 `hand.move_joints()`。若底层通信或驱动瞬时异常，系统不会因单次失败立即崩溃，而是引入了**连续失败计数器**：

```python
if not ok:
    self._consecutive_move_failures += 1
    if self._consecutive_move_failures >= self._max_consecutive_move_failures:  # 默认 3
        self.state = GraspState.ERROR
        self._running = False
        return False
else:
    self._consecutive_move_failures = 0
```

- 连续失败 1~2 次：保持循环，等待下一周期重试
- 连续失败 3 次：判定为持续性硬件故障，进入 `ERROR` 并停止控制线程

---

## 7. 控制周期与抖动实时监测

为便于性能诊断与调参，控制器在每个控制周期记录以下运行时指标：

| 属性 | 类型 | 说明 |
|:---|:---|:---|
| `last_control_cycle_s` | `float` | 上两次控制步的实际间隔（秒） |
| `last_control_cycle_jitter_s` | `float` | 实际间隔与理论 `control_period_s` 的偏差 |
| `last_tactile_data_age_s` | `float` | 当前触觉缓存距最近一次订阅回调的间隔 |
| `last_tactile_analysis` | `TactileAnalysis` | 最近周期的触觉分析结果快照 |
| `last_safety_report` | `SafetyReport` | 最近周期的安全检查报告 |
| `last_force_decisions` | `dict[TactileSensorId, ForceDecision]` | 最近周期的单指力规划决策 |

这些属性均为只读（`@property`），供上层监控、日志记录或调试接口使用。

---

## 8. 异常降级释放可配置开关

原设计文档提到"异常降级至 RELEASE 或 ERROR"，但未说明该行为可通过配置项精确控制。

代码中通过 `enable_fault_release_fallback: bool`（默认 `True`）实现：

- **`True`**（默认）：当 `SafetyMonitor.check()` 返回 `FAULT` 时，自动执行 `_perform_release(wait_control_thread=False)`，即先尝试安全张开再停止
- **`False`**：直接设置 `state = ERROR` 并停止运行，不执行释放动作，适用于需要人工介入或外部急停的场景

---

## 9. 释放阶段的反馈支持自适应

原设计文档假设释放阶段总能读取关节反馈进行到位检测。实际代码兼容**无关节反馈支持的硬件**：

```python
feedback_supported = callable(getattr(self.hand, "get_joints", None))
if feedback_supported:
    # 轮询关节角度，连续 N 周期在阈值内才判定完成
    if self._wait_joints_settled(...):
        self.state = GraspState.COMPLETED
        return True
    self.state = GraspState.ERROR
    return False
# 无反馈支持时：直接根据 move_joints 的返回布尔值判定
self.state = GraspState.COMPLETED if ok else GraspState.ERROR
return ok
```

这使得同一套控制器代码可在不同硬件代际（有反馈 vs 无反馈）上运行，无需分支版本。

---

## 10. 配置参数的严格校验规则

`AdaptiveGraspConfig` 在 `__post_init__` 中对全部关键参数执行**启动时严格校验**，避免无效配置在运行时才暴露：

| 校验项 | 规则 |
|:---|:---|
| `sliding_window_size` | `>= 3` |
| `control_period_s` / `closing_period_s` / `phase_timeout` | `> 0` |
| `max_torque` / `torque_adjust_step` | `> 0` |
| `position_speed_limit` / `position_torque_limit` | `[0, 100]` |
| `K_MCP` / `K_PIP` | `[0.0, 1.0]` 且和为 `1.0` |
| `variance_weight` + `direction_weight` + `friction_weight` | 和为 `1.0` |
| `safety_factor` | `[1.2, 2.0]` |
| `variance_baseline` / `variance_threshold` | `baseline < threshold` |
| `I_min` / `I_max` | `I_min <= I_max` |
| `fragile_speed_reduction` / `fragile_step_reduction` / `fragile_torque_reduction` | `(0.0, 1.0]` |
| `default_friction_coeff` / `max_normal_force_per_finger` | `> 0` |

任何校验失败均抛出 `ValueError` 并附带明确错误信息，在单元测试中已覆盖全部边界条件。

---

## 11. 易损模式的力矩降低

原设计文档第 7.3 节提到易损模式下速度限幅与角增量限幅的降低，但未提及力矩同样会被降低：

- `fragile_torque_reduction`（默认 `0.8`）：易损模式下，位置模式指令中的力矩上限临时乘以该系数
- `fragile_step_reduction`（默认 `0.5`）：力矩校准阶段的 `torque_adjust_step` 临时乘以该系数

三者共同作用，确保易损物体在闭合、保持、释放全阶段都受到降力保护。

---

## 12. `STOPPED` 状态

原设计文档的状态图中未出现 `STOPPED`。实际代码中 `GraspState` 枚举包含该状态：

- **含义**：控制器被外部显式 `stop()` 后的静止状态
- **与 `ERROR` 的区别**：`ERROR` 由异常触发，通常伴随故障记录与报警；`STOPPED` 是正常停止，无故障语义
- **转换路径**：`RELEASE → STOPPED`（释放完成后）、`ERROR → STOPPED`（故障清除后）、任意状态可通过 `stop()` 直接进入

---

## 13. 关节力矩模式下的非活跃关节零力矩控制

`_build_torque_joints()` 在生成 `CLOSING_TO_CONTACT` 阶段的力矩指令时，对**非活跃关节**显式下发：

```python
Joint(id=joint_id, angle=0.0, speed=0, torque=0)
```

这确保不参与当前抓取预设的手指（如两指捏时的中指/无名指/小指）不会收到残余力矩，避免非预期运动或能耗。同时，`THUMB_ROTATION` 与 `THUMB_SWING` 被硬编码追加到指令列表末尾，带有固定维持力矩 `torque=5`，保证拇指姿态在闭合过程中保持稳定。

---

## 14. 触觉数据逐指 `state` 位有效性检查

`_safe_get_tactile_data()` 不仅检查整体数据是否为 `None`，还会逐指验证 `info.state` 布尔位：

```python
for finger, info in tactile_data.items():
    if not getattr(info, "state", True):
        _logger.error("TACTILE: active finger %s data invalid (state=False)", finger)
        return None
```

若活跃手指中**任意一指**的 `state=False`（传感器故障或离线），该周期整个触觉数据被视为无效，控制器回退到"保持上一周期姿态"的安全策略，避免基于不完整数据做出错误闭环决策。

备注：该功能判断要求过于严苛，暂时已经注释

---

## 15. 新增配置参数清单（设计文档未收录）

以下参数已在 `AdaptiveGraspConfig` 中实现并校验，但未出现在原设计文档的参数表中：

| 参数名 | 默认值 | 说明 |
|:---|:---|:---|
| `base_torque` | `10` | 闭合阶段初始力矩（TORQUE 模式） |
| `max_torque` | `80` | 力矩命令上限，同时受硬件 `[-100, 100]` 约束 |
| `torque_adjust_step` | `5` | 力矩校准阶段的步进增量（N） |
| `phase_timeout` | `10.0` s | OPEN / PRE_GRASP / CLOSING 等阶段的超时保护 |
| `closing_period_s` | `0.2` s | CLOSING 阶段每次力矩指令后的休眠周期 |
| `tactile_sensor_update_period_s` | `0.015` s | 触觉传感器理论更新周期（15 ms，对应 66.7 Hz） |
| `closing_stall_angle_threshold` | `0.5°` | 关节运动停滞判定的单周期角度阈值 |
| `closing_stall_cycles` | `5` | 关节停滞连续周期数，达到后触发备用接触判定 |
| `fragile_torque_reduction` | `0.8` | 易损模式力矩降低比例 |
| `enable_fault_release_fallback` | `True` | 故障时是否先执行释放再进入 ERROR |
| `enable_visualization` | `False` | 是否启用 ADAPTIVE_HOLD 实时可视化 |
| `visualization_backend` | `"TkAgg"` | matplotlib 可视化后端 |
