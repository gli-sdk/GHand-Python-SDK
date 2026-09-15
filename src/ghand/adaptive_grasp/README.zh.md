# 自适应抓取使用说明

`ghand.adaptive_grasp` 是 GHand Python SDK 内置的自适应抓取模块。它按照“张开手指 -> 预抓取姿态 -> 闭合到触觉接触 -> 自适应保持 -> 释放”的流程运行，并基于触觉数据进行滑移风险分析、抓取力参考更新和保持控制。

## 环境要求

- Python >= 3.10
- 已安装 GHand Python SDK 的项目虚拟环境
- 可访问触觉传感器的 GHand 硬件

推荐安装方式：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

开发和测试工具使用 `dev` extra 安装：

```powershell
python -m pip install -e ".[dev]"
```

## Demo 介绍

Demo 文件：

```text
examples/extension/02.adaptive_grasp_demo.py
```

运行前通常只需要修改：

```text
src/ghand/adaptive_grasp/demo_config.py
```

常用配置：

```python
GRASP_OBJECT = "paper_cup"
HOLD_TIME_S = 60.0
```

参数说明：

- `GRASP_OBJECT`：Demo 场景名，必须是 `DEMO_SCENES` 中已有的 key。
- `HOLD_TIME_S`：进入自适应保持后的自动释放时间，单位为秒，必须大于 0。
- `_INTERRUPT_RELEASE_WAIT_S`：中断快速释放后的等待时间，必须大于 0。

快速运行：

```powershell
.\.venv\Scripts\python.exe examples\extension\02.adaptive_grasp_demo.py
```

Demo 会执行：

1. 创建 `GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)`。
2. 调用 `hand.open("auto")` 连接灵巧手。
3. 调用 `hand.tactile_open()` 打开触觉。
4. 根据 `demo_config.py` 构建 `AdaptiveGraspConfig`。
5. 调用 `AdaptiveGrasper.grasp_core()` 进入抓取和自适应保持。
6. 到达 `HOLD_TIME_S` 后自动释放。
7. 在 `finally` 中关闭触觉和通信。

运行中按 `Ctrl+C` 会触发 `emergency_release(wait_s=runtime_config.interrupt_release_wait_s)` 快速释放。

## 最小 API 示例

```python
import time

from ghand import CommType, GHand, ProductType
from ghand.adaptive_grasp import AdaptiveGrasper
from ghand.adaptive_grasp.demo_config import build_demo_runtime_config

hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)
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

    if not grasper.grasp_core():
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

- `grasp_core()`：执行张开、预抓取、闭合到接触，并启动自适应保持线程。
- `wait_for_completion()`：等待自适应保持和自动释放流程结束。
- `get_state()`：读取当前抓取状态。
- `release()`：主动停止保持并按正常释放参数张手。
- `emergency_release(wait_s=...)`：中断场景下快速释放。
- `shutdown()`：停止控制线程、传感器订阅和通信端口，不主动张手。

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

`interrupt_release_wait_s` 属于 Demo 运行时配置，不属于 `AdaptiveGraspConfig`；它只影响 `Ctrl+C` 中断场景下快速释放后的等待时间。

## 自定义物体和预抓取姿态

如果需要自定义抓取物体，请配置：

1. `src/ghand/adaptive_grasp/grasp_presets.py` 中的 `PRE_GRASP_PRESET_DEGREES`。
2. `src/ghand/adaptive_grasp/grasp_presets.py` 中的 `PRESET_ACTIVE_FINGERS`。
3. `src/ghand/adaptive_grasp/object_profile.py` 中的 `DEFAULT_OBJECT_PROFILES`。
4. `src/ghand/adaptive_grasp/demo_config.py` 中的 `DEMO_SCENES`。
5. `src/ghand/adaptive_grasp/demo_config.py` 中的 `GRASP_OBJECT`。

## 主要文件

```text
examples/extension/02.adaptive_grasp_demo.py
src/ghand/adaptive_grasp/demo_config.py
src/ghand/adaptive_grasp/config.py
src/ghand/adaptive_grasp/adaptive_grasp_manager.py
src/ghand/adaptive_grasp/grasp_sequence.py
src/ghand/adaptive_grasp/adaptive_hold_loop.py
src/ghand/adaptive_grasp/hold_planner_factory.py
src/ghand/adaptive_grasp/grasp_presets.py
src/ghand/adaptive_grasp/object_profile.py
```
