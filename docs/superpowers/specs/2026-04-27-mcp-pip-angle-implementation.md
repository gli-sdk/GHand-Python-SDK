# MCP/PIP 关节角度实现补充文档

**日期**: 2026-04-27
**说明**: 本文档补充 MCP/PIP 关节映射、角增量分配与可视化显示的工程实现细节。

---

## 1. 关节映射关系

每根活跃手指对应一对主动关节（MCP + PIP）。系统通过 `utils.FINGER_TO_MCP_PIP` 建立反向映射：

| 手指 (TactileSensorId) | MCP 关节 | PIP 关节 |
|:---|:---|:---|
| THUMB | THUMB_MCP | THUMB_PIP |
| FOREFINGER | FF_MCP | FF_PIP |
| MIDDLE_FINGER | MF_MCP | MF_PIP |
| RING_FINGER | RF_MCP | RF_PIP |
| LITTLE_FINGER | LF_MCP | LF_PIP |

该映射与已有的 `JOINT_TO_FINGER`（关节 → 手指）互为补充，供可视化层和力规划层独立使用。

---

## 2. 角增量分配机制

`ADAPTIVE_HOLD` 阶段，总控制量 `u_k` 按 `K_MCP` / `K_PIP` 分配到 MCP 与 PIP：

```
Δθ_MCP = u_k × K_MCP
Δθ_PIP = u_k × K_PIP
K_MCP + K_PIP = 1
```

实现位于 `force_planner.py` 的 `_build_finger_decision`：
- 遍历 `current_angles`，通过 `JOINT_TO_FINGER` 过滤出当前手指对应的关节
- 跳过 `THUMB_SWING`、`THUMB_ROTATION`、`FF_SWING` 等非弯曲自由度
- 对含 `"MCP"` / `"PIP"` 的关节名分别叠加 `mcp_delta` / `pip_delta`
- 易碎模式或接近力上限时，`delta_limit` 会额外收缩

---

## 3. 可视化中的 MCP/PIP 角度显示

`TactileVisualizer` 子图布局从 `n×5` 扩展为 `n×7`，末尾新增两列：

| 列 | 标题 | 数据键 |
|---|---|---|
| 5 | MCP angle (deg) | mcp_deg |
| 6 | PIP angle (deg) | pip_deg |

**角度单位约定**：
- 控制器内部、关节反馈、`current_angles` 全程使用**弧度（rad）**
- 可视化层在 `update()` 中通过 `math.degrees()` 一次性转换，显示单位为**度（deg）**

**数据流**：
```
_run_control_step
  ├─ joint_feedback = _safe_get_joints()
  ├─ current_angles = _get_current_angles(joint_feedback)   # rad
  └─ visualizer.update(..., joint_angles=current_angles)     # 内部转 deg
```

缺失关节数据时，`update()` 向对应队列 append `None`，matplotlib 自动断线，不抛异常。

---

## 4. 验证标准

- 启动 `examples/22.adaptive_grasp_demo.py`，可视化窗口出现 7 列子图
- `ADAPTIVE_HOLD` 阶段 MCP/PIP 曲线持续刷新，量级在 0~90 deg
- 原 5 列触觉曲线显示与改动前一致（目视回归）
