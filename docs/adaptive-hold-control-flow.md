# 自适应保持控制流程

本文档说明自适应保持阶段中，位置模式与力矩模式的控制流程，并使用 `AdaptiveGraspConfig` 中的参数名写出主要数学表达式。

## 1. 总体流程

自适应保持阶段每个控制周期执行一次闭环控制：

1. 从 `SensorClient` 读取触觉数据、关节反馈和采样时间。
2. `TactileAnalyzer` 根据触觉数据计算每根活动手指的法向力、切向力和滑动风险。
3. `ForceReferencePlanner` 根据接触快照和滑动风险生成每根手指的参考法向力 `F_ref,i`。
4. 根据 `adaptive_hold_command_mode` 选择控制模式。
5. 位置模式由 `PositionHoldPlanner` 生成目标关节角度。
6. 力矩模式由 `TorqueHoldPlanner` 生成每根手指的目标力矩。
7. `JointCommandBuilder` 将控制结果转换为可下发的关节命令。

两种模式共用同一套参考法向力规划逻辑，区别只在最后的执行器输出：

```text
位置模式：F_ref - F_actual -> PID -> 关节角度增量 -> 位置命令
力矩模式：F_ref - F_actual -> PID -> 力矩增量 -> 力矩命令
```

## 2. 触觉分析

对每根活动手指 `i`，读取触觉传感器三轴力：

```text
F_z,i = abs(force_z,i)
F_t,i = sqrt(F_x,i^2 + F_y,i^2)
```

其中 `F_z,i` 为法向力，`F_t,i` 为切向合力。

切向力窗口方差：

```text
var_i = mean((F_t,i - mean(F_t,i))^2)
```

当前代码对切向力方差做在线窗口归一化：

```text
s_k,i = clip((var_i - mean(var_i_window)) / max(std(var_i_window), epsilon), 0, 1)
```

摩擦利用率：

```text
r_k,i = clip((F_t,i / (F_z,i + epsilon)) / friction_coeff, 0, 1)
```

方向变化量记为：

```text
d_k,i
```

滑动风险融合：

```text
slip_risk_i = s_total,i
            = clip(
                variance_weight * s_k,i
              + direction_weight * d_k,i
              + friction_weight * r_k,i,
                0,
                1
              )
```

滑动确认使用防抖计数：

```text
if slip_risk_i + epsilon >= 0.7:
    slip_count_i += 1
else:
    slip_count_i = max(0, slip_count_i - 1)

slip_confirmed_i = slip_count_i >= slip_detect_debounce_cycles
```

## 3. 参考法向力规划

自适应保持进入时，会使用闭合找接触阶段记录的 `ContactSnapshot` 初始化参考法向力。

### 3.1 初始参考总法向力

```text
F_ref,total(0) = contact_snapshot.total_fz + force_ref_margin_n
```

如果存在材质库 `ObjectProfile`，还会受安全力范围限制：

```text
F_ref,total(0) = clip(
    F_ref,total(0),
    safe_force_min,
    safe_force_max
)
```

如果没有材质库，则上限使用：

```text
max_normal_force_per_finger * active_finger_count
```

### 3.2 接触比例分配

对每根活动手指：

```text
raw_i = max(contact_snapshot.finger_fz[i], 0)
```

如果 `sum(raw_i) > 0`：

```text
ratio_i = max(raw_i / sum(raw_i), force_ref_min_contact_ratio)
alpha_i = ratio_i / sum(ratio_i)
```

如果没有有效接触力，则均分：

```text
alpha_i = 1 / active_finger_count
```

每根手指的初始参考力：

```text
F_ref,i(0) = F_ref,total(0) * alpha_i
```

### 3.3 滑动风险增力

每个周期根据 `slip_risk_i` 更新 `F_ref,i`。

若滑动风险超过告警阈值：

```text
if slip_risk_i >= force_ref_slip_warning_threshold:
    slip_excess_i = slip_risk_i - force_ref_slip_warning_threshold
    delta_F_i = force_ref_slip_gain_n_per_s * slip_excess_i * dt
    F_ref,i += min(delta_F_i, force_ref_max_rise_step_n)
```

如果本周期确认滑动，且上一周期未确认滑动：

```text
if slip_confirmed_i and not last_slip_confirmed_i:
    F_ref,i += force_ref_confirmed_boost_n
```

### 3.4 稳定衰减

若滑动风险低于稳定阈值：

```text
if slip_risk_i <= force_ref_stable_threshold:
    stable_time_i += dt
```

稳定时间超过延迟后，参考力缓慢衰减：

```text
if stable_time_i >= force_ref_stable_decay_delay_s:
    F_ref,i -= force_ref_decay_rate_n_per_s * dt
```

若滑动风险处于中间区间：

```text
force_ref_stable_threshold < slip_risk_i < force_ref_slip_warning_threshold
```

则不增力、不衰减，并重置稳定计时。

### 3.5 总参考力限幅

每次更新后，都会限制参考总法向力：

```text
safe_force_min <= sum(F_ref,i) <= safe_force_max
```

若总参考力超过上限：

```text
scale = safe_force_max / sum(F_ref,i)
F_ref,i = F_ref,i * scale
```

若总参考力低于下限：

```text
scale = safe_force_min / sum(F_ref,i)
F_ref,i = F_ref,i * scale
```

## 4. 位置模式自适应保持

当：

```text
adaptive_hold_command_mode == "position"
```

进入位置模式闭环。

### 4.1 法向力误差

每根手指独立计算误差：

```text
e_i = F_ref,i - F_z,i
```

### 4.2 PID 控制量

PID 参数来自：

```text
position_hold_K_p
position_hold_K_i
position_hold_K_d
position_hold_I_min
position_hold_I_max
```

积分项：

```text
I_i(k) = clip(
    I_i(k-1) + e_i(k) * dt,
    position_hold_I_min,
    position_hold_I_max
)
```

微分项：

```text
D_i(k) = (e_i(k) - e_i(k-1)) / dt
```

第一步没有上一时刻误差，因此微分项为 0。

PID 输出：

```text
u_pid,i = position_hold_K_p * e_i
        + position_hold_K_i * I_i
        + position_hold_K_d * D_i
```

### 4.3 超限保护项

每根手指的法向力上限：

```text
F_limit,i = safe_force_max / effective_contact_count
```

若没有材质库，则使用：

```text
F_limit,i = max_normal_force_per_finger
```

超限误差：

```text
overlimit_i = max(0, (F_z,i - F_limit,i) / (F_limit,i + epsilon))
```

保护项：

```text
u_over,i = -K_n * overlimit_i
```

最终控制量：

```text
u_i = u_pid,i + u_over,i
```

如果是易碎物体，且 `F_z,i >= F_limit,i`，则禁止继续增加夹紧：

```text
u_i = min(u_i, 0)
```

### 4.4 角度增量限幅

基础角度增量上限：

```text
delta_limit = delta_theta_limit
```

易碎物体降低步长：

```text
if is_fragile:
    delta_limit *= fragile_step_reduction
```

若任一活动手指接近安全力上限：

```text
F_z,i >= near_force_limit_ratio * F_limit,i
```

则进一步降低步长：

```text
delta_limit *= near_limit_step_scale
```

总角度增量：

```text
delta_theta_total,i = clip(u_i, -delta_limit, delta_limit)
```

### 4.5 MCP/PIP 角度分配

```text
delta_theta_MCP,i =
    thumb_K_MCP * delta_theta_total,i    if i == THUMB
    finger_K_MCP * delta_theta_total,i   otherwise
delta_theta_PIP,i =
    thumb_K_PIP * delta_theta_total,i    if i == THUMB
    finger_K_PIP * delta_theta_total,i   otherwise
```

下一时刻目标角度：

```text
theta_MCP,i,next = theta_MCP,i,current + delta_theta_MCP,i
theta_PIP,i,next = theta_PIP,i,current + delta_theta_PIP,i
```

### 4.6 接触快照角度限幅

自适应保持阶段不会让关节无限远离闭合找接触时的角度快照：

```text
theta_j,next = clip(
    theta_j,next,
    theta_j,contact - contact_snapshot_angle_limit,
    theta_j,contact + contact_snapshot_angle_limit
)
```

### 4.7 下发位置命令

位置模式最终下发：

```text
mode = POSITION
angle = theta_j,next
speed = position_hold_speed 或 position_speed_limit
torque = position_hold_torque 或 position_torque_limit
```

若物体为易碎物体，位置模式下发力矩会乘以：

```text
fragile_torque_reduction
```

## 5. 力矩模式自适应保持

当：

```text
adaptive_hold_command_mode == "torque"
```

进入力矩模式闭环。

### 5.1 法向力误差

每根手指独立计算：

```text
e_i = F_ref,i - F_z,i
```

### 5.2 PID 力矩增量

PID 参数来自：

```text
torque_hold_K_p
torque_hold_K_i
torque_hold_K_d
torque_hold_I_min
torque_hold_I_max
```

积分项：

```text
I_i(k) = clip(
    I_i(k-1) + e_i(k) * dt,
    torque_hold_I_min,
    torque_hold_I_max
)
```

微分项：

```text
D_i(k) = (e_i(k) - e_i(k-1)) / dt
```

第一步微分项为 0。

力矩增量：

```text
delta_tau_i = torque_hold_K_p * e_i
            + torque_hold_K_i * I_i
            + torque_hold_K_d * D_i
```

### 5.3 目标力矩

基础保持力矩：

```text
adaptive_hold_torque
```

目标力矩：

```text
tau_i = adaptive_hold_torque + delta_tau_i
```

力矩限幅：

```text
tau_i = clip(tau_i, -100, max_torque)
```

### 5.4 下发力矩命令

力矩模式对活动手指的 MCP/PIP 同时下发同一个手指力矩：

```text
tau_MCP,i = round(tau_i)
tau_PIP,i = round(tau_i)
```

最终命令：

```text
mode = TORQUE
torque = round(tau_i)
```

拇指旋转和摆动关节使用辅助力矩：

```text
thumb_aux_torque
```

## 6. 两种模式对比

| 项目 | 位置模式 | 力矩模式 |
| --- | --- | --- |
| 参考法向力 | `ForceReferencePlanner` | `ForceReferencePlanner` |
| 控制误差 | `F_ref,i - F_z,i` | `F_ref,i - F_z,i` |
| PID 输出 | 角度控制量 `u_i` | 力矩增量 `delta_tau_i` |
| 最终命令 | `POSITION` | `TORQUE` |
| 控制对象 | MCP/PIP 目标角度 | MCP/PIP 目标力矩 |
| 是否使用接触快照角度限幅 | 是 | 否 |
| 是否使用 `delta_theta_limit` | 是 | 否 |
| 是否使用 `adaptive_hold_torque` | 否 | 是 |
| 是否使用 `position_torque_limit` | 是 | 否 |

可以把两种模式理解为：

```text
位置模式：通过“多弯一点/少弯一点”改变接触法向力。
力矩模式：通过“多给一点/少给一点力矩”改变接触法向力。
```

两者的上层目标一致：根据滑动风险动态调节 `F_ref,i`，再让每根手指尽量跟随自己的参考法向力。
