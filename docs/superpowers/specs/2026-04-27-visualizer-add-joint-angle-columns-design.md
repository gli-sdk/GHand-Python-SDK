# 可视化窗口新增 MCP/PIP 关节角度曲线设计

## 决策

在 `TactileVisualizer` 现有 n×5 子图布局基础上，**末尾增加两列**：MCP 关节角度-时间曲线、PIP 关节角度-时间曲线。子图布局变为 n×7，n 为活动手指数。

角度统一以**度（deg）**显示。控制器和关节反馈仍按弧度（rad）传递，转换在可视化层一次性完成（`math.degrees`）。

## 架构

```
AdaptiveGrasper._run_control_step
  ├─ joint_feedback = self._safe_get_joints()
  ├─ current_angles: dict[JointId, float]   (弧度)
  └─ self._visualizer.update(
         tactile_data, analysis, joint_angles=current_angles, timestamp=...,
     )
        └─ TactileVisualizer.update
            ├─ append fz/ft/variance/direction/friction (沿用)
            └─ for finger in active_fingers:
                 mcp_id, pip_id = FINGER_TO_MCP_PIP[finger]
                 append math.degrees(joint_angles[mcp_id]) → mcp_deg
                 append math.degrees(joint_angles[pip_id]) → pip_deg
```

## 关键接口

- `utils.FINGER_TO_MCP_PIP: dict[TactileSensorId, tuple[JointId, JointId]]`
  - 反向映射，对应每根手指的 (MCP, PIP) 关节 ID。
  - 拇指 → `(THUMB_MCP, THUMB_PIP)`，食指 → `(FF_MCP, FF_PIP)`，依此类推。
- `TactileVisualizer.update(tactile_data, analysis, joint_angles=None, timestamp=None)`
  - 新增可选参数 `joint_angles: dict[JointId, float] | None`。
  - 当 `joint_angles is None` 或对应关节缺失时，append `None`，曲线自然断线。
- `TactileVisualizer._data[finger]` 新增两个键：`"mcp_deg"`、`"pip_deg"`，复用 `deque(maxlen=max_points)`。

## 子图布局

| 列 | 标题 | 数据键 |
|---|---|---|
| 0 | normal force Fz (N) | fz |
| 1 | tangential force Ft (N) | ft |
| 2 | Ft Variance | variance |
| 3 | Ft direction consistency | direction |
| 4 | tangential force Friction | friction |
| 5 | MCP angle (deg) | mcp_deg |
| 6 | PIP angle (deg) | pip_deg |

`subplots(n, 7, ...)`、`titles` 列表追加两项，绘图循环 `range(5)` 改为 `range(7)`，绘制键元组 `_PLOT_KEYS` 同步增加。

## 缺失数据处理

沿用既有规则：
- 整帧无触觉/关节数据 → 所有键 append `None`。
- 仅缺失某手指的 MCP 或 PIP（理论上不会发生，但防御性处理）→ 仅该键 append `None`。
- matplotlib 自动断线，不抛异常。

## 验证标准

- 启动 `examples/22.adaptive_grasp_demo.py`，可视化窗口出现 7 列子图，每行对应一根活动手指。
- 在 ADAPTIVE_HOLD 阶段，新增的 MCP / PIP 两列曲线持续刷新，量级在 0~90 deg，与 `pre_grasp_pose` 中度数对应。
- 原 5 列曲线显示与改动前一致（目视回归）。
- `tests/adaptive_grasp/test_controller.py` 全部通过。

## 不变更的模块

- 触觉分析 (`tactility.py`)、安全监控 (`safety.py`)、力规划 (`force_planner.py`) 不变。
- 控制器主循环结构不变，仅 `_run_control_step` 调用 visualizer 时多传一个 kwarg。
- 不引入 rad/deg 切换开关，不新增可视化配置项。
