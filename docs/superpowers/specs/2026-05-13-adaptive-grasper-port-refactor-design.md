# AdaptiveGrasper 端口化拆分设计

## 背景

`src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py` 中的 `AdaptiveGrasper`
目前同时承担 SDK 对外入口、硬件访问、传感器订阅、运行时状态、抓取阶段编排、
adaptive hold 线程循环、释放动作和可视化转发。这个形态已经能工作，但后续要接入
MuJoCo 时会遇到两个边界问题：

- 当前控制流程直接依赖 `DexHand` 的 `move_joints()`、`subscribe()`、`unsubscribe()`。
- 当前传感器模型偏硬件回调，而 MuJoCo 更自然的是仿真 step 后主动读取状态。

本次设计目标是采用“端口拆分版 B”：保持 `AdaptiveGrasper` 对外 API 兼容，同时把命令
输出和传感器帧来源抽象出来，为真实硬件、测试 fake 和未来 MuJoCo 后端共用同一控制
主干。

## 非目标

- 不在本轮实现完整 MuJoCo 后端。
- 不重写触觉分析、force reference、position hold、torque hold 等控制算法。
- 不改变示例脚本和 SDK 用户依赖的主要 API。
- 不把所有 `xiaoyao.dexhand.Joint`、`CtrlMode`、`TactileSensorId` 立即替换成全新的领域模型。

## 设计选择

选择薄端口抽象，而不是完整仿真器抽象。第一轮只引入两个稳定边界：

1. 命令端口：控制器发送关节命令，不关心命令落到真实手还是仿真模型。
2. 传感器帧来源：控制器读取最新触觉和关节反馈，不关心数据来自 EtherCAT 回调还是 MuJoCo step。

这样可以先解除 `AdaptiveGrasper` 和 `DexHand` 的强绑定，又避免过早承诺 MuJoCo 的具体实现细节。

## 新模块

### `ports.py`

定义 adaptive grasp 需要的最小端口协议。

```python
class HandCommandPort(Protocol):
    def move_joints(self, joints: list[Joint], mode: CtrlMode) -> bool: ...
    def stop(self) -> None: ...


class SensorFrameSource(Protocol):
    def start(self) -> None: ...
    def stop(self, clear_joint_feedback: bool = False) -> None: ...
    def reset(self) -> None: ...
    @property
    def tactile_data(self) -> Optional[dict[TactileSensorId, Any]]: ...
    @property
    def joint_feedback(self) -> Optional[list[Joint]]: ...
    @property
    def sample_time_s(self) -> Optional[float]: ...
    def data_age_s(self, current_time: float) -> Optional[float]: ...
    def sum_active_finger_normal_force(self) -> float: ...
    def active_finger_touch_flag(self) -> dict[TactileSensorId, bool]: ...
```

短期内 `SensorClient` 可以直接满足 `SensorFrameSource`，不必立即改名。

### `hand_adapter.py`

提供真实硬件适配。

```python
class DexHandCommandPort:
    def __init__(self, hand: DexHand): ...
    def move_joints(self, joints: list[Joint], mode: CtrlMode) -> bool: ...
    def stop(self) -> None: ...
    def configure_subscription_periods(
        self,
        recv_period_s: float,
        dispatch_period_s: float,
    ) -> None: ...
```

`configure_subscription_periods()` 负责封装当前对 `hand._sub_manager` 的私有访问。以后如果
`DexHand` 暴露正式 API，只改适配层。

`ensure_hand_command_port()` 用于兼容旧入口：`AdaptiveGrasper(DexHand(), config)` 仍然可用；
如果传入对象已经满足 `HandCommandPort`，则直接使用。

### `runtime.py`

保存一次抓取生命周期内的可变状态和 telemetry。

```python
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

    def reset_for_grasp(self) -> None: ...
    def record_hold_step(self, step: HoldStepResult, sensor: SensorFrameSource, step_start: float) -> None: ...
```

`AdaptiveGrasper` 的 `state`、`current_torque` 和 `last_*` 属性继续保留，但实现上转发到 runtime。

### `components.py`

集中构造运行时组件。

```python
@dataclass
class AdaptiveGraspComponents:
    sensor: SensorFrameSource
    tactile: TactileAnalyzer
    safety: SafetyMonitor
    joint_builder: JointCommandBuilder
    hold_planner_factory: HoldPlannerFactory
    visualizer: Optional[TactileVisualizer]
```

真实硬件路径默认创建 `SensorClient`。未来 MuJoCo 路径可以传入 `MuJoCoSensorFrameSource`，
复用后续的 phase/hold/release 编排。

### `release_controller.py`

集中处理释放动作和线程互锁规则。

```python
class ReleaseController:
    def release(
        self,
        *,
        wait_control_thread: bool,
        release_wait_s: Optional[float] = None,
        control_thread: Optional[threading.Thread] = None,
    ) -> bool: ...
```

它负责：

- 设置 `runtime.state = GraspState.RELEASE`。
- 设置 `runtime.running = False`。
- 停止 `SensorFrameSource`。
- 当 `wait_control_thread=True` 且不是当前线程时 join control thread。
- 发送 open pose。
- 根据 `move_joints()` 结果设置 `COMPLETED` 或 `ERROR`。

### `adaptive_hold_runner.py`

管理 adaptive hold 的线程和循环。

```python
class AdaptiveHoldRunner:
    def start(self, contact_snapshot: Optional[ContactSnapshot]) -> None: ...
    def stop(self, timeout_s: float = 1.0) -> None: ...
    @property
    def thread(self) -> Optional[threading.Thread]: ...
```

它负责：

- 创建 `HoldController`。
- 创建 hold planner bundle。
- 设置 `runtime.state = GraspState.ADAPTIVE_HOLD`。
- 记录 `adaptive_hold_started_at`。
- 启动控制线程。
- 在循环中调用 `HoldController.run_step()`。
- 写入 runtime telemetry。
- 根据 `HoldResult.ERROR` 清理为 `ERROR`。
- 根据 `AUTO_RELEASE` / `FAULT_RELEASE` 调用 `ReleaseController.release(wait_control_thread=False)`。

## 现有模块调整

### `AdaptiveGrasper`

保留 facade 角色，主要职责变为：

- 接收 `hand` 和 `config`。
- 创建 command port、sensor source、runtime 和 components。
- 调用 `PhaseController` 完成 OPEN / PRE_GRASP / CLOSING。
- 把 closing 结果写入 runtime。
- 启动 `AdaptiveHoldRunner`。
- 对外转发 `release()`、`release_fast()`、`stop()`、`get_state()`、`last_*`、可视化方法。

外部 API 保持：

```python
grasper = AdaptiveGrasper(hand, config)
grasper.grasp_core()
grasper.release()
grasper.release_fast(wait_s=1.0)
grasper.stop()
grasper.get_state()
grasper.last_tactile_analysis
grasper.last_torque_hold_decision
```

### `PhaseController`

第一轮只把 `hand: DexHand` 参数替换为 `hand: HandCommandPort`。它仍然可以使用现有
`SensorFrameSource` 接口读取触觉和关节反馈。

### `HoldController`

第一轮只把 `hand: DexHand` 参数替换为 `hand: HandCommandPort`，其余控制逻辑保持不变。

### `SensorClient`

短期继续作为真实硬件 sensor source。它仍然用 `hand.subscribe()` 更新缓存。后续若要更彻底
解耦，可以把 TPDO 解析拆成独立 mapper，但不放入本轮。

## MuJoCo 迁移路径

未来 MuJoCo 后端不需要伪装成 `DexHand`，只需要实现两个边界：

```text
MuJoCoHandCommandPort
  - 把 Joint command 映射到 MuJoCo actuator ctrl
  - 负责 position/torque 模式映射

MuJoCoSensorFrameSource
  - 每次 sim.step() 后生成 tactile_data / joint_feedback / sample_time_s
  - 暴露与 SensorClient 相同的读取接口
```

如果 MuJoCo 控制循环需要由外部仿真主循环驱动，可以在第二阶段为 `AdaptiveHoldRunner` 增加
同步 step API：

```python
def run_one_hold_step(self, current_time: float) -> HoldStepResult: ...
```

第一轮先保留当前线程循环，避免同时改变执行模型。

## 错误处理

- phase 失败且要求释放时，`AdaptiveGrasper` 调用 `ReleaseController.release(wait_control_thread=False)`。
- phase 失败但不要求释放时，runtime 进入 `ERROR`，sensor source 停止。
- hold loop 抛异常时，`AdaptiveHoldRunner` 记录日志，停止 sensor source，runtime 进入 `ERROR`。
- release 发送 open pose 失败时，runtime 进入 `ERROR` 并返回 `False`。
- `stop()` 停止 hold runner、sensor source、visualizer，并调用 command port `stop()`。

## 测试计划

保留现有 manager 行为测试，并新增窄单元测试：

- `DexHandCommandPort.configure_subscription_periods()` 调用 `_sub_manager.configure_periods()`。
- 没有 `_sub_manager` 时配置订阅周期不报错。
- `AdaptiveGraspRuntime.reset_for_grasp()` 清理所有 runtime telemetry。
- `AdaptiveGraspRuntime.record_hold_step()` 正确写入 `last_*` 和 `current_torque`。
- `ReleaseController.release(wait_control_thread=True)` 会 join 非当前控制线程。
- `ReleaseController.release(wait_control_thread=False)` 不 join 控制线程。
- `ReleaseController` 在 `move_joints()` 失败时进入 `ERROR`。
- `AdaptiveHoldRunner` 遇到 `HoldResult.ERROR` 时清理到 `ERROR`。
- `AdaptiveHoldRunner` 遇到 `FAULT_RELEASE` 时调用 release controller。
- `PhaseController` 和 `HoldController` 可接受 fake `HandCommandPort`。

## 兼容性

- `AdaptiveGrasper` 对外构造方式和公开方法不变。
- `xiaoyao.adaptive_grasp.__all__` 可继续导出 `AdaptiveGrasper`；新端口类型可以选择性导出。
- 示例脚本无需立即修改。
- 现有测试中的 `_MockHand` 仍可通过 adapter 或协议兼容继续使用。

