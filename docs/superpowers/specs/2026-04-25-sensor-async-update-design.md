# 传感器数据异步更新设计

## 决策

保持现有**线程回调模型**，不引入 `asyncio`。

`AdaptiveGrasper` 通过 `hand.subscribe(callback)` 订阅传感器数据，`SubscriptionManager` 在后台线程中接收并分发 TPDO 数据，回调函数同步解析并缓存触觉/关节数据。控制循环独立运行，从缓存读取最新数据。

## 架构

```
EthercatClient.recv_data()
  → SubscriptionManager._data_producer (后台线程)
    → self._data = data
      → SubscriptionManager._data_dispatcher (后台线程)
        → 遍历 subscribers，同步调用 callback(self._data)
          → AdaptiveGrasper._sensor_update_callback(tpdo)
            → 解析并赋值 _latest_tactile_data / _latest_joint_feedback
              ← AdaptiveGrasper._run_control_step (控制线程) 读取缓存
```

## 关键接口

- `hand.subscribe(callback)` —— 注册同步回调，返回订阅 ID。
- `hand.unsubscribe(sub_id)` —— 注销订阅。
- `AdaptiveGrasper._sensor_update_callback(tpdo)` —— 解析 `Tpdo` 对象，按活跃手指过滤，更新触觉和关节缓存。
- `AdaptiveGrasper._safe_get_tactile_data()` / `_safe_get_joints()` —— 安全读取缓存，检查传感器在线状态和数据新鲜度。

## 线程安全

缓存变量（`_latest_tactile_data`、`_latest_joint_feedback`、`_last_tactile_sample_time_s`）均采用**引用替换**策略。在 CPython 中，引用赋值是原子的，控制线程读取时不会得到部分写入的中间状态。

## 不变更的模块

- `AdaptiveGrasper` 状态机（`grasp_core`、`_phase_*`、`_adaptive_control_loop`）保持同步线程模型不变。
- 所有 `time.sleep` 保持原样。
