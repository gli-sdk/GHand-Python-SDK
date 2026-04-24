# adaptive_grasp_demo.py 重写设计

## 背景

`examples/22.adaptive_grasp_demo.py` 是自适应抓取模块的示例代码，但存在以下问题：

1. 直接访问 `AdaptiveGrasper` 的私有类属性 `_TORQUE_JOINTS`（第 131-170 行），违反了封装原则
2. 手动根据 `pre_grasp_preset` 映射关节集合，但 `AdaptiveGraspConfig.__post_init__` 已自动推导 `active_fingers`，`AdaptiveGrasper.__init__` 已据此过滤 `_torque_joints`，这些手动设置完全多余
3. 未展示 `ObjectProfile` 材质库、`TactileAnalyzer`、`SafetyMonitor` 等子模块的公共 API
4. CSV 记录逻辑与主抓取流程耦合在一起

## 目标

- 消除对私有属性的访问
- 展示 `src/xiaoyao/adaptive_grasp` 子模块的公共 API
- 添加 `ObjectProfile` 和详细输出支持
- 提升代码可读性和模块化程度

## 方案

采用 **公共 API 展示版（方案 B）**：修复问题的同时，通过公共 API 展示子模块用法，保持 demo 简洁。

## 修改范围

### 1. `src/xiaoyao/adaptive_grasp/controller.py`

在 `AdaptiveGrasper` 中添加三个公共只读属性，暴露最近一次控制循环的分析结果：

```python
@property
def last_tactile_analysis(self) -> Optional[TactileAnalysis]: ...
@property
def last_safety_report(self) -> Optional[SafetyReport]: ...
@property
def last_force_decisions(self) -> Optional[dict[TactileSensorId, ForceDecision]]: ...
```

在 `_run_control_step()` 中保存这些结果。此修改最小且非破坏性。

### 2. `examples/22.adaptive_grasp_demo.py`

#### 2.1 新增 `TactileLogger` 类

封装 CSV 文件操作：
- `__init__(hand, output_dir)`：创建 CSV 文件、写入表头
- `write_row(state, torque)`：读取触觉数据、构造行、写入
- `close()`：关闭文件

#### 2.2 参数解析扩展

`build_parser()` 新增：
- `--object`：可选值从 `ObjectProfileRegistry.list_names()` 获取（metal_block / plastic_cup / tofu / banana / egg），默认 None
- `--verbose` / `-v`：启用逐指详细输出

#### 2.3 删除的代码

- 所有 `grasper._TORQUE_JOINTS = (...)` 的手动设置（约 40 行）
- 内联的 CSV 相关函数 `_build_csv_header`、`_read_tactile_row`（逻辑移至 `TactileLogger`）

#### 2.4 `main()` 流程

1. 解析参数
2. 连接 hand、打开触觉传感器
3. 若指定 `--object`，从 `ObjectProfileRegistry.get(name)` 获取 `ObjectProfile`
4. 构建 `AdaptiveGraspConfig`（preset 自动推导 `active_fingers`，无需手动设置关节）
5. 创建 `AdaptiveGrasper`，调用 `grasp_core(object_profile)`
6. 保持阶段循环（每 0.1s）：
   - 打印状态、力矩、已保持时间
   - 若 `--verbose`：通过 `grasper.last_tactile_analysis` 和 `grasper.last_force_decisions` 打印每根手指的滑移风险 `s_total`、法向力 `fz`、控制量 `control_u`
   - 调用 `tactile_logger.write_row()` 记录 CSV
7. 超时后调用 `grasper.release()`
8. `finally` 中关闭 `TactileLogger` 和 hand

#### 2.5 异常处理

保留现有的分类异常捕获：
- `KeyboardInterrupt`
- `DeviceDisconnectedError`
- `JointFaultError`
- `DeviceFaultError`
- `DataReceiveError`
- 通用 `Exception`

## 数据流

```
args -> build_config() -> AdaptiveGraspConfig
                    -> ObjectProfileRegistry.get(args.object) -> ObjectProfile

hand + config + profile -> AdaptiveGrasper.grasp_core() -> 启动状态机

保持阶段：
  grasper.current_torque / grasper.get_state() -> 终端打印
  grasper.last_tactile_analysis / last_force_decisions -> verbose 打印
  hand.get_tactile_data() -> TactileLogger -> CSV 文件
```

## 自检清单

- [x] 无 TBD / TODO
- [x] `controller.py` 的修改不破坏现有接口
- [x] demo 不再访问任何私有属性
- [x] ObjectProfile 的获取路径清晰
- [x] CSV 资源在 finally 中释放
