# Controller 重构设计：降低认知负荷

## 背景

`controller.py` 当前 558 行，`AdaptiveGrasper` 类承担了过多职责：状态机编排、顺序阶段执行、自适应保持后台循环、关节指令构建、传感器协调、安全监控、触觉分析、力规划调用、可视化。文件过长导致难以一次性理解。

## 决策

采用**方案 B：职责分离**，将 `AdaptiveGrasper` 拆分为一个轻量级协调器 + 三个专注子模块。不引入抽象基类或策略模式（避免过度设计）。

## 模块拆分

| 文件 | 职责 | 预期行数 |
|------|------|---------|
| `controller.py` | 生命周期编排（`grasp_core`、`release`、`stop`）、线程管理、状态管理、暴露 `last_*` 属性 | ~150 |
| `phase_controller.py` | 顺序阶段执行：`OPEN → PRE_GRASP → CLOSING`、力校准、停滞检测 | ~140 |
| `hold_controller.py` | `ADAPTIVE_HOLD` 单步控制逻辑（不含线程管理） | ~120 |
| `joint_builder.py` | 所有关节指令组装（torque/position/hold） | ~60 |

### AdaptiveGrasper（协调器）

- 创建并持有 `_phase_controller`、`_hold_controller`、`_joint_builder`
- `grasp_core()`：调用 `_phase_controller.run()`，成功后启动 `_hold_controller` 的后台线程
- `release()` / `stop()`：生命周期终止，停止传感器订阅和后台线程
- 维护所有 `_last_*` 对外只读属性
- 作为唯一修改 `self.state` 和 `self._running` 的模块

### PhaseController

- `run(force_planner, is_running) -> PhaseResult`
- 依次执行 OPEN、PRE_GRASP、CLOSING 三个阶段
- `is_running: Callable[[], bool]` 用于响应外部 `stop()` 调用
- 内部维护 `current_torque`，最终通过 `PhaseResult.final_torque` 回传

### HoldController

- `run_step(current_time: float) -> HoldStepResult`
- 执行一个控制周期的完整逻辑：安全检查 → 触觉分析 → 力规划 → 执行 move_joints
- 不管理线程，不修改外部状态，只返回结果
- 内部维护 `_consecutive_move_failures`

### JointCommandBuilder

- 纯函数式接口，无可变状态
- `open_pose()`、`init_hold_angles()`、`position_command()`、`torque_command()`、`hold_position_command()`

## 关键接口

### PhaseResult

```python
@dataclass
class PhaseResult:
    success: bool
    final_torque: int
```

### HoldStepResult / HoldResult

```python
class HoldResult(Enum):
    CONTINUE = auto()
    AUTO_RELEASE = auto()
    FAULT_RELEASE = auto()
    ERROR = auto()

@dataclass
class HoldStepResult:
    result: HoldResult
    tactile_analysis: Optional[TactileAnalysis] = None
    safety_report: Optional[SafetyReport] = None
    force_decisions: Optional[dict[TactileSensorId, ForceDecision]] = None
```

## 数据流

### grasp_core 流程

```
AdaptiveGrasper.grasp_core()
  → _phase_controller.run(force_planner, lambda: self._running)
    → PhaseResult(success=True, final_torque=42)
  → self.current_torque = result.final_torque
  → _start_adaptive_control()
    → 创建 HoldController
    → 启动后台线程 _adaptive_control_loop()
```

### adaptive_control_loop 流程

```
AdaptiveGrasper._adaptive_control_loop()
  while _running:
    → step = _hold_controller.run_step(monotonic_time)
    → 同步 _last_* 属性
    → if step.result == AUTO_RELEASE:
         _perform_release(wait_control_thread=False); break
       elif step.result == FAULT_RELEASE:
         _perform_release(wait_control_thread=False); break
       elif step.result == ERROR:
         state = ERROR; _running = False; break
    → sleep(control_period_s)
```

## 状态属性归属

| 状态属性 | 归属 |
|----------|------|
| `state` / `_running` | `AdaptiveGrasper` 唯一写入 |
| `_last_tactile_analysis` / `_last_safety_report` / `_last_force_decisions` | `AdaptiveGrasper` 从 `HoldStepResult` 同步 |
| `_last_tactile_data_age_s` | `AdaptiveGrasper` 在线程循环中计算 |
| `_last_control_cycle_s` / `_last_control_cycle_jitter_s` | `AdaptiveGrasper` 在线程循环中计算 |
| `_consecutive_move_failures` | 内收到 `HoldController` |

## 错误处理

- `PhaseController` 遇到超时/传感器丢失/空抓 → 返回 `PhaseResult(success=False)`，`AdaptiveGrasper` 负责 `_cleanup_grasp()`
- `HoldController` 遇到 safety FAULT → 根据 `enable_fault_release_fallback` 返回 `FAULT_RELEASE` 或让调用者处理；遇到连续 move 失败 → 返回 `ERROR`
- `AdaptiveGrasper` 统一做状态机转换（`STOPPED` / `ERROR` / `COMPLETED`）

## 公共 API 变化

- `AdaptiveGrasper` 公共方法（`grasp_core`、`release`、`stop`、`get_state`、`last_*`）**签名不变**
- 内部方法（`_run_control_step`、`_phase_closing`、`_build_*_joints` 等）消失，转移到新模块
- 新增 `HoldResult`、`HoldStepResult`、`PhaseResult` 三个内部数据类型

## 测试迁移

| 测试 | 重构后归属 | 改动量 |
|------|-----------|--------|
| `test_adaptive_hold_*` (hold 系列) | `HoldController` | 中 |
| `test_closing_*` / `test_calibrate_force_*` (phase 系列) | `PhaseController` | 中 |
| `test_build_torque_joints_*` | `JointCommandBuilder` | 小 |
| `test_release_*` / `test_full_grasp_*` (集成测试) | 不变 | 无 |

新增测试建议：
- `test_joint_builder_open_pose`：验证 `JointCommandBuilder.open_pose()` 返回的关节集合
- `test_phase_controller_returns_final_torque`：验证 `PhaseResult.final_torque` 被正确传递
