# Adaptive Grasp 使用说明

`adaptive_grasp` 是xiaoyao灵巧手 SDK 中的自适应抓取模块。它基于触觉反馈完成预抓取、闭合到接触、自适应保持和释放，适合演示纸杯、气球、水瓶等不同物体的抓取保持能力。

## 快速运行 Demo

Demo 文件：

```bash
examples/25.adaptive_grasp_demo.py
```

Demo 用户只需要修改一个配置文件：

```bash
src/adaptive_grasp/demo_config.py
```

目前只暴露两个参数：

```python
GRASP_OBJECT = "paper_cup"
HOLD_TIME_S = 60.0
```

- `GRASP_OBJECT`：抓取对象名称。
- `HOLD_TIME_S`：自适应保持时间，单位为秒。

配置完成后，直接运行 `examples/25.adaptive_grasp_demo.py` 即可，不需要命令行传参。

## 支持的 Demo 抓取对象

当前 `GRASP_OBJECT` 支持：

| 对象名称 | 说明 |
| --- | --- |
| `paper_cup` | 纸杯 |
| `balloon` | 气球 |
| `plastic_cup` | 塑料杯 |
| `smooth_ball` | 光滑球体 |
| `minreal_water_bottle_500ml` | 500ml 矿泉水瓶 |
| `plastic_object` | 3D打印的塑料物体 |
| `orange` | 橙子/水果类物体 |


每个对象会自动映射到内部预抓取姿态和活动手指配置。


## 常用 API

最小 SDK 使用方式：

```python
from adaptive_grasp import AdaptiveGraspConfig, AdaptiveGrasper
from xiaoyao.dexhand import CommType, DexHand

hand = DexHand()
hand.open(CommType.ETHERCAT, "auto")
hand.tactile_open()

config = AdaptiveGraspConfig(
    default_object="paper_cup",
    pre_grasp_preset="paper_cup_grasp",
    release_hold_time_s=20.0,
)

grasper = AdaptiveGrasper(hand=hand, config=config)

try:
    if grasper.grasp_core():
        grasper.finish()
finally:
    hand.tactile_close()
    hand.close()
```


## 强制终止

代码中，可以通过在命令行按下`ctrl + c`的方式，进行强制终止。


## 用户调参

可以直接构造 `AdaptiveGraspConfig`，常用参数包括：

| 参数 | 说明 |
| --- | --- |
| `default_object` | 默认物体配置 |
| `pre_grasp_preset` | 预抓取姿态 |
| `release_hold_time_s` | 自适应保持时间 |
| `enable_position_hold_force_control` | 是否启用位置保持中的力控修正 |
| `control_period_s` | 自适应保持控制周期 |

## 注意事项

- 运行 demo 前，请确认灵巧手通信正常。
- 运行 demo 前，请确认触觉传感器可正常打开。
- `GRASP_OBJECT` 必须是 `demo_config.py` 中 `DEMO_SCENES` 支持的对象名称。
- `HOLD_TIME_S` 必须大于 0。
- Demo 默认不保存触觉 CSV，也不开启可视化。
- `emergency_release()` 是中断释放接口，不建议作为正常结束流程使用。

## 自定义修改抓取物品与灵巧手关节角度
若用户想要自定义抓取物品，需进行如下操作：
    - 1）修改`src/adaptive_grasp/grasp_presets.py`中的`PRE_GRASP_PRESET_DEGREE`，新增预抓取姿态，并配置各关节的预抓取角度。
    - 2）修改`src/adaptive_grasp/grasp_presets.py`中的`PRESET_ACTIVE_FINGERS`，为该预抓取姿态配置参与触觉检测和闭环保持控制的手指集合。
    - 3）修改`src/adaptive_grasp/object_profile.py`中的`DEFAULT_OBJECT_PROFILES`，通过`ObjectProfile`注册物品名称、材质、摩擦系数、安全力范围、保持力矩和保持速度等物品属性。
    - 4）修改`src/adaptive_grasp/demo_config.py`中的`DEMO_SCENES`，新增一个demo场景，并将场景名映射到前面配置的物品名和预抓取姿态名。例如：`"new_object": DemoScene(default_object="new_object", pre_grasp_preset="new_object_grasp")`。
    - 5）修改`src/adaptive_grasp/demo_config.py`中的`GRASP_OBJECT = "paper_cup"`，将其改为新增的`DEMO_SCENES`场景名，例如`GRASP_OBJECT = "new_object"`。

    注意：`GRASP_OBJECT`对应的是`DEMO_SCENES`的key；`DemoScene.default_object`对应`ObjectProfile.name`；`DemoScene.pre_grasp_preset`对应`PRE_GRASP_PRESET_DEGREE`和`PRESET_ACTIVE_FINGERS`中的预抓取姿态名。这三个名称可以相同，也可以不同，但必须能正确对应。
  
## 文件位置

主要文件：

```bash
src/adaptive_grasp/
```

常用入口：

```bash
src/adaptive_grasp/adaptive_grasp_manager.py
src/adaptive_grasp/config.py
src/adaptive_grasp/demo_config.py
src/adaptive_grasp/grasp_presets.py
src/adaptive_grasp/object_profile.py
```

Demo：

```bash
examples/25.adaptive_grasp_demo.py
```
