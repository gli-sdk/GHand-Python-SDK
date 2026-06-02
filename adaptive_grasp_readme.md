# Adaptive Grasp 使用说明

`adaptive_grasp` 是 GHand Python SDK 中的自适应抓取模块。它会按“张开手指 -> 预抓取姿态 -> 闭合到触觉接触 -> 自适应保持 -> 释放”的流程运行，并基于触觉数据做滑移风险分析、抓取力参考更新和保持控制。


## 环境要求

- Python >= 3.10（当前验证环境为 Python 3.13）
- 已安装 GHand SDK 的项目虚拟环境
- 可访问触觉传感器的 GHand 硬件

当前项目推荐使用虚拟环境，虚拟环境的创建步骤如下

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

如果需要运行测试和开发工具，再安装 dev 依赖：

```powershell
python -m pip install -e ".[dev]"
```

`requirements.txt` 只保留运行 SDK 和 Demo 需要的依赖；`pytest`、`mypy`、`yapf`、`pre-commit` 等开发工具由 `pyproject.toml` 的 `dev` extra 管理。



## Demo介绍

Demo 文件：

```text
examples/extension/02.adaptive_grasp_demo.py
```

运行前通常只需要修改：

```text
src/adaptive_grasp/demo_config.py
```

最常用的两个配置是：

```python
GRASP_OBJECT = "paper_cup"
HOLD_TIME_S = 60.0
```
DEMO 参数解读
- `GRASP_OBJECT`：Demo 场景名，必须是 `DEMO_SCENES` 中已有的 key。
- `HOLD_TIME_S`：进入自适应保持后的自动释放时间，单位为秒，必须大于 0。


### 快速运行：

创建虚拟环境后，在终端输入如下指令
```powershell
.\.venv\Scripts\python.exe examples\extension\02.adaptive_grasp_demo.py
```

Demo 会执行以下动作：

1. 创建 `GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)`。
2. 调用 `hand.open("auto")` 连接灵巧手。
3. 调用 `hand.tactile_open()` 打开触觉。
4. 根据 `demo_config.py` 构建 `AdaptiveGraspConfig`。
5. 调用 `AdaptiveGrasper.grasp_core()` 进入抓取和自适应保持。
6. 到达 `HOLD_TIME_S` 后自动释放。
7. 在 `finally` 中关闭触觉和通信。

运行中按 `Ctrl+C` 会触发 `emergency_release(wait_s=runtime_config.interrupt_release_wait_s)` 快速释放。

## 当前支持的 Demo 场景

`GRASP_OBJECT` 当前支持：

| 场景名 | 物体配置 | 预抓取姿态 |
| --- | --- | --- |
| `paper_cup` | `paper_cup` | `paper_cup_grasp` |
| `balloon` | `balloon` | `balloon_pinch` |
| `glass_cup` | `glass` | `three_finger_grasp` |
| `plastic_cup` | `plastic_cup` | `paper_cup_grasp` |
| `smooth_ball` | `plastic_cup` | `smooth_ball` |
| `mineral_water_bottle_500ml` | `mineral_water_bottle_500ml` | `minreal_water_grasp` |
| `plastic_object` | `plastic` | `two_finger_pinch` |
| `orange` | `fruit` | `four_finger_grasp` |
| `pen` | `plastic` | `pen_pinch` |

注意：`GRASP_OBJECT` 是 Demo 场景名，不一定等于内部的 `ObjectProfile.name`。所有名字需要与配置的统一，否则将会调用内部默认参数。

## 最小 API 示例

```python
import time
from adaptive_grasp import AdaptiveGrasper
from adaptive_grasp.demo_config import build_demo_runtime_config
from ghand import CommType, GHand, ProductType

hand = GHand(product_type=ProductType.G5, comm_type=CommType.ETHERCAT)
grasper = None
runtime_config = build_demo_runtime_config("paper_cup", 60.0)

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

    grasp_ok = grasper.grasp_core()
    if not grasp_ok:
        raise RuntimeError(f"Grasp failed at state={grasper.get_state().value}")

    final_state = grasper.wait_for_completion()
    print(f"Final state: {final_state.value}")
except KeyboardInterrupt:
    if grasper is not None:
        grasper.emergency_release(wait_s=runtime_config.interrupt_release_wait_s)
finally:
    hand.tactile_close()
    hand.close()
```

常用方法：

- `grasp_core()`：执行张开、预抓取、闭合到接触，并启动自适应保持线程。成功返回后不要立刻调用 `release()` 或 `release_and_wait_for_visualizer_close()`，否则会马上释放。
- `wait_for_completion()`：等待自适应保持和自动释放流程结束，并返回最终 `GraspState`。
- `get_state()`：读取当前抓取状态。

- `release_and_wait_for_visualizer_close()`：主动提前释放并等待可视化窗口关闭。
- `emergency_release(wait_s=...)`：中断场景下快速释放。
- `shutdown()`：停止控制线程、传感器订阅和手部通信，不会张开手。




状态枚举见 `GraspState`：

```text
idle, open, pre_grasp, closing_to_contact, adaptive_hold,
release, completed, error, stopped
```
## 用户调参

可以直接构造 `AdaptiveGraspConfig`，常用参数包括：

| 参数 | 说明 |
| --- | --- |
| `default_object` | 默认物体配置 |
| `pre_grasp_preset` | 预抓取姿态 |
| `release_hold_time_s` | 自适应保持时间 |
| `enable_position_hold_force_control` | 是否启用位置保持中的力控修正 |
| `control_period_s` | 自适应保持控制周期 |

Demo 默认：

```python
enable_visualization = False
hold_command_mode = "position"
interrupt_release_wait_s = _INTERRUPT_RELEASE_WAIT_S
```

`interrupt_release_wait_s` 属于 Demo 运行时配置，不属于 `AdaptiveGraspConfig`；它只影响 `Ctrl+C` 中断场景下快速释放后的等待时间。普通释放阶段使用的是 `AdaptiveGraspConfig.release_timeout_s`。


## 自定义抓取物品和关节角度

如果需要自定义抓取物品，请按以下步骤配置：

1. 修改 `src/adaptive_grasp/grasp_presets.py` 中的 `PRE_GRASP_PRESET_DEGREE`，新增预抓取姿态，并配置各关节的预抓取角度。
2. 修改 `src/adaptive_grasp/grasp_presets.py` 中的 `PRESET_ACTIVE_FINGERS`，为该预抓取姿态配置参与触觉检测和闭环保持控制的手指集合。
3. 修改 `src/adaptive_grasp/object_profile.py` 中的 `DEFAULT_OBJECT_PROFILES`，通过 `ObjectProfile` 注册物品名称、材质、摩擦系数、安全力范围、保持力矩和保持速度等物品属性。
4. 修改 `src/adaptive_grasp/demo_config.py` 中的 `DEMO_SCENES`，新增一个 Demo 场景，并将场景名映射到前面配置的物品名和预抓取姿态名。
5. 修改 `src/adaptive_grasp/demo_config.py` 中的 `GRASP_OBJECT = "paper_cup"`，将其改为新增的 `DEMO_SCENES` 场景名。


示例：

```python
"new_object": DemoScene(
    default_object="new_object",
    pre_grasp_preset="new_object_grasp",
)
```

命名关系：

- `GRASP_OBJECT` 对应 `DEMO_SCENES` 的 key。
- `DemoScene.default_object` 对应 `ObjectProfile.name`。
- `DemoScene.pre_grasp_preset` 对应 `PRE_GRASP_PRESET_DEGREE` 和 `PRESET_ACTIVE_FINGERS` 的 key。

这三个名称可以相同，也可以不同，但必须能正确对应。



## 主要文件

```text
examples/extension/02.adaptive_grasp_demo.py
src/adaptive_grasp/demo_config.py
src/adaptive_grasp/config.py
src/adaptive_grasp/adaptive_grasp_manager.py
src/adaptive_grasp/grasp_presets.py
src/adaptive_grasp/object_profile.py
```
