# 修复传感器订阅问题

> **For agentic workers:** Use superpowers:executing-plans or inline execution.

**Goal:** 修复 `SubscriptionManager` 并发启动隐患、`_calibrate_force` 重复计算、`_data_producer` 异常处理三个问题。

**Architecture:** 保持现有线程回调模型，仅做针对性修复。

**Tech Stack:** Python, threading, pytest

---

### Task 1: 修复 SubscriptionManager.subscribe() 并发启动隐患

**Files:**
- Modify: `src/xiaoyao/subscription.py:66-73`
- Test: `tests/test_subscription.py` (新建)

- [ ] **Step 1: 写失败测试**

```python
import threading
import time
from xiaoyao.subscription import SubscriptionManager

class FakeClient:
    def recv_data(self):
        time.sleep(0.01)
        return {"data": 1}

def test_concurrent_subscribe_does_not_duplicate_threads():
    sm = SubscriptionManager(client=FakeClient())
    threads_before = threading.active_count()
    
    def subscribe_worker():
        sm.subscribe(lambda data: None)
    
    workers = [threading.Thread(target=subscribe_worker) for _ in range(10)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    
    # 只应启动 producer + dispatcher 两个线程
    assert sm._thread is not None
    assert sm._dispatcher_thread is not None
    # 线程数增加不超过 2（producer + dispatcher）
    assert threading.active_count() <= threads_before + 2
    
    sm.stop()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_subscription.py::test_concurrent_subscribe_does_not_duplicate_threads -v`
Expected: 可能偶发失败（线程重复启动）

- [ ] **Step 3: 实现修复**

修改 `src/xiaoyao/subscription.py` 的 `subscribe` 方法，将 `_running` 检查和 `start()` 移入锁内：

```python
def subscribe(self, callback: Optional[Callable] = None, *args, **kwargs):
    with self._lock:
        self._sub_id_counter += 1
        sub_id = self._sub_id_counter
        self._subscribers[sub_id] = (callback, args, kwargs)
        if not self._running:
            self.start()
    return sub_id
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_subscription.py::test_concurrent_subscribe_does_not_duplicate_threads -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_subscription.py src/xiaoyao/subscription.py
git commit -m "fix(subscription): 修复并发 subscribe 重复启动线程的隐患"
```

---

### Task 2: 删除 _calibrate_force 重复计算

**Files:**
- Modify: `src/xiaoyao/adaptive_grasp/controller.py:232`
- Test: 使用现有测试 `tests/adaptive_grasp/test_controller.py`

- [ ] **Step 1: 运行现有测试确认基线**

Run: `pytest tests/adaptive_grasp/test_controller.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 删除重复行**

在 `src/xiaoyao/adaptive_grasp/controller.py` 的 `_calibrate_force` 方法中，删除以下行：
```python
            total_fz = sum(abs(info.get_force_z()) for info in tactile_data.values())
```
保留下一行 `total_fz = self._sum_active_finger_normal_force(tactile_data)`。

- [ ] **Step 3: 运行测试确认未引入回归**

Run: `pytest tests/adaptive_grasp/test_controller.py -v`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add src/xiaoyao/adaptive_grasp/controller.py
git commit -m "fix(controller): 删除 _calibrate_force 中的重复计算"
```

---

### Task 3: 修复 _data_producer 持续异常时无限分发旧数据

**Files:**
- Modify: `src/xiaoyao/subscription.py:43-51`
- Test: `tests/test_subscription.py`

- [ ] **Step 1: 写失败测试**

```python
class FailingClient:
    def __init__(self, fail_after=0):
        self._calls = 0
        self._fail_after = fail_after
    
    def recv_data(self):
        self._calls += 1
        if self._calls > self._fail_after:
            raise RuntimeError("recv_data failed")
        return {"data": self._calls}

def test_data_producer_clears_data_after_consecutive_errors():
    client = FailingClient(fail_after=2)
    sm = SubscriptionManager(client=client)
    received = []
    sm.subscribe(lambda data: received.append(data))
    sm.start()
    
    time.sleep(0.5)  # 让 producer 运行几次
    
    # 前两次成功，之后持续失败
    assert client._calls >= 3
    # 持续异常后 _data 应被清空，避免分发 stale data
    assert sm._data is None
    
    sm.stop()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_subscription.py::test_data_producer_clears_data_after_consecutive_errors -v`
Expected: FAIL（_data 未被清空）

- [ ] **Step 3: 实现修复**

修改 `src/xiaoyao/subscription.py` 的 `_data_producer`：

```python
def _data_producer(self):
    consecutive_errors = 0
    while self._running:
        try:
            data = self._client.recv_data()
            self._data = data
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Error receiving data: {e} (consecutive: {consecutive_errors})")
            if consecutive_errors >= 10:
                logger.error("Data producer encountered too many consecutive errors, clearing stale data")
                self._data = None
            time.sleep(min(0.1 * (2 ** min(consecutive_errors, 5)), 5.0))
            continue
        time.sleep(0.1)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_subscription.py::test_data_producer_clears_data_after_consecutive_errors -v`
Expected: PASS

- [ ] **Step 5: 运行全部 subscription 测试**

Run: `pytest tests/test_subscription.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_subscription.py src/xiaoyao/subscription.py
git commit -m "fix(subscription): _data_producer 连续异常时清除旧数据并增加退避"
```

---

## Self-Review

- **Spec coverage:** 三个问题均有对应 Task。
- **Placeholder scan:** 无 TBD/TODO，每步含具体代码。
- **Type consistency:** 文件路径和函数名与现有代码一致。
