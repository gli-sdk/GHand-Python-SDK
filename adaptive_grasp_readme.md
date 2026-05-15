# Adaptive Grasp 使用说明

`adaptive_grasp` 是xiaoyao灵巧手 SDK 中的自适应抓取模块。它基于触觉反馈完成预抓取、闭合到接触、自适应保持和释放，适合演示纸杯、气球、水瓶等不同物体的抓取保持能力。

## 快速运行 Demo

Demo 文件：

```bash
examples/25.adaptive_grasp_demo.py
```

Demo 用户只需要修改一个配置文件：

```bash
src/xiaoyao/adaptive_grasp/demo_config.py
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


每个对象会自动映射到内部预抓取姿态和活动手指配置。Demo 用户不需要手动配置 `pre_grasp_preset` 或 `active_fingers`。

## Demo 运行流程

`examples/25.adaptive_grasp_demo.py` 的主要流程如下：

1. 创建 `DexHand`
2. 打开 EtherCAT 通信
3. 打开触觉传感器
4. 从 `demo_config.py` 构建 `AdaptiveGraspConfig`
5. 创建 `AdaptiveGrasper`
6. 调用 `grasper.grasp_core()`
7. 进入自适应保持状态
8. 保持结束后调用 `grasper.finish()`
9. 程序退出前关闭触觉和设备连接

`grasp_core()` 会在抓取成功后启动后台自适应保持控制。Demo 中的 `while GraspState.ADAPTIVE_HOLD` 循环主要用于等待保持结束和打印状态，不是自适应控制本身。

## 常用 API

最小 SDK 使用方式：

```python
from xiaoyao.adaptive_grasp import AdaptiveGraspConfig, AdaptiveGrasper
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

### `AdaptiveGrasper.grasp_core()`

执行完整抓取流程：

- 初始化运行状态
- 启动触觉订阅
- 执行张手、预抓取、闭合到接触
- 成功后进入 `ADAPTIVE_HOLD`
- 启动后台自适应保持控制线程

返回值：

- `True`：抓取成功并进入自适应保持
- `False`：抓取失败或流程异常

### `AdaptiveGrasper.finish()`

正常收尾接口，内部会：

- 调用 `release()` 释放物体
- 等待可视化窗口关闭

Demo 默认关闭可视化，因此通常不会产生额外等待。

### `AdaptiveGrasper.emergency_release()`

异常/中断释放接口，适合 `KeyboardInterrupt` 或紧急停止场景。

它不会等待自适应保持线程完整收尾，而是优先发送张手释放命令：

```python
grasper.emergency_release(wait_s=1.0)
```

### 强制终止

代码中，已经通过在命令行按下`ctrl + c`的方式，退出自适应抓取。

## 配置分层建议

### Demo 用户

只修改：

```python
GRASP_OBJECT
HOLD_TIME_S
```

不需要关心预抓取姿态、活动手指、最大闭合力矩、触觉 CSV、可视化和力矩保持模式。

### 调参用户

可以直接构造 `AdaptiveGraspConfig`，常用参数包括：

| 参数 | 说明 |
| --- | --- |
| `default_object` | 默认物体配置 |
| `pre_grasp_preset` | 预抓取姿态 |
| `release_hold_time_s` | 自适应保持时间 |
| `max_torque` | 自适应闭合最大力矩 |
| `enable_position_hold_force_control` | 是否启用位置保持中的力控修正 |
| `control_period_s` | 自适应保持控制周期 |

### 内部研发用户

以下能力默认不对 demo 用户开放，主要用于内部调试和研发：

- 触觉 CSV 记录
- 可视化窗口
- 力矩保持模式
- PID 参数
- 滑移检测参数
- 力参考规划参数
- 单指 PID 覆盖

备注：目前基于力矩模式下的触觉力矩闭环模式还未完全开发完毕，请勿使用。

## 注意事项

- 运行 demo 前，请确认灵巧手通信正常。
- 运行 demo 前，请确认触觉传感器可正常打开。
- `GRASP_OBJECT` 必须是 `demo_config.py` 中 `DEMO_SCENES` 支持的对象名称。
- `HOLD_TIME_S` 必须大于 0。
- Demo 默认不保存触觉 CSV，也不开启可视化。
- `emergency_release()` 是中断释放接口，不建议作为正常结束流程使用。

## 自定义修改抓取物品与灵巧手关节角度
若用户想要自定义抓取物品，需进行如下操作：
    - 1）修改`src/xiaoyao/adaptive_grasp/grasp_presets.py`中的`PRE_GRASP_PRESET_DEGREE`，新增预抓取姿态，并配置各关节的预抓取角度。
    - 2）修改`src/xiaoyao/adaptive_grasp/grasp_presets.py`中的`PRESET_ACTIVE_FINGERS`，为该预抓取姿态配置参与触觉检测和闭环保持控制的手指集合。
    - 3）修改`src/xiaoyao/adaptive_grasp/object_profile.py`中的`DEFAULT_OBJECT_PROFILES`，通过`ObjectProfile`注册物品名称、材质、摩擦系数、安全力范围、保持力矩和保持速度等物品属性。
    - 4）修改`src/xiaoyao/adaptive_grasp/demo_config.py`中的`DEMO_SCENES`，新增一个demo场景，并将场景名映射到前面配置的物品名和预抓取姿态名。例如：`"new_object": DemoScene(default_object="new_object", pre_grasp_preset="new_object_grasp")`。
    - 5）修改`src/xiaoyao/adaptive_grasp/demo_config.py`中的`GRASP_OBJECT = "paper_cup"`，将其改为新增的`DEMO_SCENES`场景名，例如`GRASP_OBJECT = "new_object"`。

    注意：`GRASP_OBJECT`对应的是`DEMO_SCENES`的key；`DemoScene.default_object`对应`ObjectProfile.name`；`DemoScene.pre_grasp_preset`对应`PRE_GRASP_PRESET_DEGREE`和`PRESET_ACTIVE_FINGERS`中的预抓取姿态名。这三个名称可以相同，也可以不同，但必须能正确对应。
  
## 文件位置

主要文件：

```bash
src/xiaoyao/adaptive_grasp/
```

常用入口：

```bash
src/xiaoyao/adaptive_grasp/adaptive_grasp_manager.py
src/xiaoyao/adaptive_grasp/config.py
src/xiaoyao/adaptive_grasp/demo_config.py
src/xiaoyao/adaptive_grasp/grasp_presets.py
src/xiaoyao/adaptive_grasp/object_profile.py
```

Demo：

```bash
examples/25.adaptive_grasp_demo.py
```
