# Adaptive Grasp 使用说明

`adaptive_grasp` 是 GHand Python SDK 的高层自适应抓取模块。它完成开手、预抓取、闭合至接触、自适应保持、自动释放，并使用触觉数据进行滑移与安全监测。

## 环境要求

- Python `>= 3.10`
- 已连接支持触觉传感器的 GHand 硬件
- 当前仓库及运行依赖已安装

推荐在虚拟环境中安装：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

## 快速运行 Demo

入口脚本：

```text
examples/extension/02.adaptive_grasp_demo.py
```

运行前通常只需修改 [demo_config.py](src/adaptive_grasp/demo_config.py) 中的两个值：

```python
GRASP_OBJECT = "paper_cup"
HOLD_TIME_S = 60.0
```

运行：

```powershell
.\.venv\Scripts\python.exe examples\extension\02.adaptive_grasp_demo.py
```

Demo 使用 `GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)`，连接设备并打开触觉后，创建 `AdaptiveGrasper` 执行抓取。按 `Ctrl+C` 时会调用 `emergency_release()` 快速张手。

### Demo 场景

`GRASP_OBJECT` 是 `DEMO_SCENES` 的场景名，不一定等于物体配置名。

| 场景名 | 物体配置名 | 预抓取预设 | 保持模式 |
| --- | --- | --- | --- |
| `paper_cup` | `paper_cup` | `paper_cup_grasp` | `POSITION` |
| `balloon` | `balloon` | `balloon_pinch` | `POSITION` |
| `glass_cup` | `glass` | `three_finger_grasp` | `STIFF_POSITION` |
| `plastic_cup` | `plastic_cup` | `paper_cup_grasp` | `POSITION` |
| `mineral_water_bottle_500ml` | `mineral_water_bottle_500ml` | `minreal_water_grasp` | `POSITION` |
| `plastic_object` | `plastic` | `two_finger_pinch` | `POSITION` |
| `orange` | `fruit` | `four_finger_grasp` | `POSITION` |
| `cylinder_piece` | `cylinder_piece` | `cylinder_piece_grasp` | `STIFF_POSITION` |

`build_demo_runtime_config()` 会校验场景名和保持时间。`HOLD_TIME_S` 必须大于 `0`；小于等于 `1` 秒会记录警告。Demo 的可视化默认关闭，可通过 `build_demo_runtime_config(enable_visualization=True)` 打开。中断释放等待时间来自 `DemoRuntimeConfig.interrupt_release_wait_s`，默认值是 `3.0` 秒。

## 最小示例

下面代码从当前 Demo 主流程精简而来，保留连接、触觉初始化、抓取、等待完成、中断释放和关闭资源的调用顺序。

```python
import time

from adaptive_grasp import AdaptiveGrasper
from adaptive_grasp.demo_config import build_demo_runtime_config
from ghand import CommType, GHand, ProductType

hand = GHand(
    product_type=ProductType.GHand5,
    comm_type=CommType.ETHERCAT,
)
runtime_config = build_demo_runtime_config()
grasper = None

try:
    if not hand.open("auto"):
        raise RuntimeError("Connection failed")
    if not hand.tactile_open():
        raise RuntimeError("Failed to open tactile sensors")

    time.sleep(0.5)
    grasper = AdaptiveGrasper(
        hand=hand,
        config=runtime_config.adaptive_config,
    )
    if not grasper.grasp_core():
        raise RuntimeError(f"Grasp failed at state={grasper.get_state().value}")

    print(f"Final state: {grasper.wait_for_completion().value}")
except KeyboardInterrupt:
    if grasper is not None:
        grasper.emergency_release(
            wait_s=runtime_config.interrupt_release_wait_s,
        )
finally:
    hand.tactile_close()
    hand.close()
```

`grasp_core()` 成功后会启动后台保持线程。保持时间达到 `release_hold_time_s` 后，后台线程自动执行释放；`wait_for_completion()` 只等待流程结束，不会主动触发释放。

## 直接配置

不使用 Demo 时，使用 `AdaptiveGraspConfig` 和 `HoldCommandMode` 直接构造配置：

```python
from adaptive_grasp import (
    AdaptiveGraspConfig,
    AdaptiveGrasper,
    HoldCommandMode,
)

config = AdaptiveGraspConfig(
    default_object="paper_cup",
    pre_grasp_preset="paper_cup_grasp",
    hold_command_mode=HoldCommandMode.POSITION,
    release_hold_time_s=20.0,
    enable_visualization=False,
)
grasper = AdaptiveGrasper(hand=hand, config=config)
```

`hold_command_mode` 必须传入枚举，当前仅支持：

```python
HoldCommandMode.POSITION
HoldCommandMode.STIFF_POSITION
```

不支持字符串输入，也没有对外开放的 `TORQUE` 保持模式。

### 配置规则

- 所有关节角度均为 **度**，包括 `pre_grasp_pose`、`position_hold_*_deg` 和 `stiff_position_*_deg`。
- `pre_grasp_preset` 必填。未显式传入 `pre_grasp_pose` 时，会从该预设生成姿态。
- `pre_grasp_pose` 不能包含被动 DIP 关节：`THUMB_IP`、`FF_DIP`、`MF_DIP`、`RF_DIP`、`LF_DIP`。
- `active_fingers` 为空时，当前实现会按 `PRESET_ACTIVE_FINGERS` 中对应的预设自动推导；也可显式传入 `set[TactileSensorId]` 覆盖。
- `default_object` 必须存在于 `ObjectProfileRegistry`。

常用配置项：

| 参数 | 含义 |
| --- | --- |
| `open_speed` / `open_torque` | 开手阶段的位置命令速度和力矩/电流限制 |
| `pre_grasp_speed` / `pre_grasp_torque` | 预抓取阶段的位置命令速度和力矩/电流限制 |
| `phase_timeout` | 闭合至接触阶段超时 |
| `closing_total_contact_threshold_n` | 结束闭合阶段所需的总法向力阈值 |
| `finger_touch_threshold_n` | 单指触觉接触阈值 |
| `control_period_s` | 自适应保持控制周期 |
| `release_hold_time_s` | 自动释放前的保持时长 |
| `release_open_speed` / `release_open_torque` | 释放张手命令参数 |
| `enable_visualization` | 是否启用内部触觉诊断可视化 |

完整默认值和校验范围以 [config.py](src/adaptive_grasp/config.py) 为准。

## 两种保持模式

### `HoldCommandMode.POSITION`

默认模式。模块基于每根有效手指的触觉法向力、滑移风险和物体安全力范围计算位置修正，并下发位置模式命令。

常用参数：

- `enable_position_hold_force_control`
- `position_hold_max_step_deg`
- `position_hold_contact_angle_guard_margin_deg`
- `position_hold_force_limit_slowdown_ratio`
- `position_hold_slip_risk_deadband`
- `position_hold_slip_risk_full`

该模式需要有效的 `ObjectProfile`，并使用其中的 `position_hold_speed`、`position_hold_torque`、`safe_force_min` 与 `safe_force_max`。

### `HoldCommandMode.STIFF_POSITION`

用于刚性物体。触觉总法向力低于目标值时，活动关节相对接触瞬间的角度按固定步长递增；到达目标力或检测到接触力突然下降时停止递增。

常用参数：

- `stiff_position_hold_speed`
- `stiff_position_hold_torque`
- `stiff_position_step_deg`
- `stiff_position_max_delta_deg`
- `stiff_position_force_drop_ratio`

目标力优先级如下：

1. `grasp_core(hold_target_force_n=...)`
2. `ObjectProfile.stiff_position_hold_target_force`
3. `ObjectProfile.safe_force_min`

刚性位置保持的速度和力矩优先使用 `ObjectProfile.stiff_position_hold_speed` 与 `ObjectProfile.stiff_position_hold_torque`；物体配置未填写时，回退到 `AdaptiveGraspConfig` 的 `stiff_position_hold_speed=90` 和 `stiff_position_hold_torque=90`。

## 物体配置与预抓取预设

默认物体配置位于 [object_profile.py](src/adaptive_grasp/object_profile.py) 的 `DEFAULT_OBJECT_PROFILES`。每个 `ObjectProfile` 包含：

- `safe_force_min` / `safe_force_max`：所有活动手指法向力之和的安全范围
- `friction_coeff`：触觉滑移分析使用的摩擦系数
- `is_fragile`：易碎物体标记
- `phase_closing_torque`：闭合至接触阶段的力矩/电流限制
- `position_hold_speed` / `position_hold_torque`：普通位置保持参数
- `stiff_position_hold_speed` / `stiff_position_hold_torque` / `stiff_position_hold_target_force`：刚性位置保持的可选覆盖值

预抓取预设位于 [grasp_presets.py](src/adaptive_grasp/grasp_presets.py)：

- `PRE_GRASP_PRESET_DEGREES`：预抓取关节角度，单位为度
- `PRESET_ACTIVE_FINGERS`：每个预设参与接触、触觉分析与保持控制的手指

新增 Demo 场景时，需要保持以下映射完整：

```text
DEMO_SCENES 场景名
  -> DemoScene.default_object
  -> ObjectProfile.name

DEMO_SCENES 场景名
  -> DemoScene.pre_grasp_preset
  -> PRE_GRASP_PRESET_DEGREES 和 PRESET_ACTIVE_FINGERS 的 key
```

如果只在业务代码中直接构造 `AdaptiveGraspConfig`，无需修改 `DEMO_SCENES`；但 `default_object`、`pre_grasp_preset` 及其活动手指映射必须有效。

## 常用 API

### `AdaptiveGrasper`

- `grasp_core(object_profile=None, *, hold_target_force_n=None) -> bool`：运行开手、预抓取和闭合至接触；成功后启动后台保持。
- `wait_for_completion(poll_period_s=0.1) -> GraspState`：等待保持和释放结束。
- `release() -> bool`：停止保持并按正常释放参数张手。
- `emergency_release(wait_s=2.0) -> bool`：不等待控制线程，立即张手，适用于中断处理。
- `release_and_wait_for_visualizer_close() -> bool`：释放并等待可视化窗口关闭。
- `shutdown() -> None`：停止控制、传感器、可视化和通信端口，不主动张手。
- `get_state() -> GraspState`：读取当前状态。

可用于诊断的只读属性：

- `last_tactile_analysis`
- `last_safety_report`
- `last_force_decisions`
- `last_tactile_data_age_s`
- `last_control_cycle_s`
- `last_control_cycle_jitter_s`
- `last_contact_snapshot`

### 状态值

```text
idle
open
pre_grasp
closing_to_contact
adaptive_hold
release
completed
error
stopped
```

## 关键源码位置

```text
examples/extension/02.adaptive_grasp_demo.py
src/adaptive_grasp/demo_config.py
src/adaptive_grasp/config.py
src/adaptive_grasp/adaptive_grasp_manager.py
src/adaptive_grasp/grasp_sequence.py
src/adaptive_grasp/adaptive_hold_loop.py
src/adaptive_grasp/hold_planner_factory.py
src/adaptive_grasp/grasp_presets.py
src/adaptive_grasp/object_profile.py
```
