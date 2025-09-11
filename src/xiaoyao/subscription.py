import threading
import time
import queue
from .client import Client
from typing import Callable, Optional


class SubscriptionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._dispatcher_thread = None
        self._client = Client()
        self._data_queue = queue.Queue(maxsize=10)
        self._sub_id_counter = 0
        self._subscribers = {}

    def start(self):
        if not self._running:
            self._running = True
            res = self._client.pdo_init()
            print(f"PDO initialized: {res}")
            self._thread = threading.Thread(
                target=self._data_producer, daemon=True, name="SubscriptionDataProducer")
            self._thread.start()
            self._dispatcher_thread = threading.Thread(
                target=self._data_dispatcher, daemon=True, name="SubscriptionDataDispatcher")
            self._dispatcher_thread.start()

    def stop(self):
        """停止订阅"""
        print("Stopping subscription manager...")
        self._running = False
        
        # 等待线程结束
        threads_to_join = []
        thread_names = []
        if self._thread and self._thread.is_alive():
            threads_to_join.append(self._thread)
            thread_names.append("data producer")
        if self._dispatcher_thread and self._dispatcher_thread.is_alive():
            threads_to_join.append(self._dispatcher_thread)
            thread_names.append("data dispatcher")
        
        # 第一次尝试正常终止
        for thread in threads_to_join:
            thread.join(timeout=1)
        
        # 检查是否所有线程都已终止
        alive_threads = [(t, name) for t, name in zip(threads_to_join, thread_names) if t.is_alive()]
        if alive_threads:
            print(f"Warning: The following threads did not terminate within timeout:")
            for thread, name in alive_threads:
                print(f"  - {name} thread (ID: {thread.ident})")
            print("These threads will be left to terminate naturally.")
            print("Consider optimizing thread loop to check stop condition more frequently.")

    def _data_producer(self):
        """数据生产者线程"""
        print("Data producer thread started")
        try:
            while self._running:
                try:
                    # 更频繁地检查运行状态
                    if not self._running:
                        break
                        
                    data = self._client.recv_data()
                    if not self._running:
                        break
                        
                    try:
                        self._data_queue.put_nowait(data)
                    except queue.Full:
                        try:
                            self._data_queue.get_nowait()
                            self._data_queue.put_nowait(data)
                        except queue.Empty:
                            pass
                except Exception as e:
                    if self._running:  # 只在仍在运行时打印错误
                        print(f"Error in data producer: {e}")
                        
                # 更短的睡眠间隔，提高响应速度
                for _ in range(10):  # 将 0.1 秒拆分为 10 个 0.01 秒的间隔
                    if not self._running:
                        break
                    time.sleep(0.01)
        except Exception as e:
            print(f"Unexpected error in data producer: {e}")
        finally:
            print("Data producer thread stopped")

    def _data_dispatcher(self):
        print("Data dispatcher thread started")
        try:
            while self._running:
                try:
                    # 使用更短的超时时间以提高响应速度
                    data = self._data_queue.get(timeout=0.1)
                    if not self._running:
                        break
                        
                    with self._lock:
                        subscribers_copy = self._subscribers.copy()
                    for sub_id, (callback, args, kwargs) in subscribers_copy.items():
                        if callback:
                            try:
                                callback(data, *args, **kwargs)
                            except Exception as e:
                                print(f"Error in callback {sub_id}: {e}")
                except queue.Empty:
                    # 超时继续检查运行状态
                    continue
                except Exception as e:
                    if self._running:  # 只在仍在运行时打印错误
                        print(f"Error in data dispatcher: {e}")
        except Exception as e:
            print(f"Unexpected error in data dispatcher: {e}")
        finally:
            print("Data dispatcher thread stopped")

    def subscribe(self, callback: Optional[Callable] = None, *args, **kwargs):
        with self._lock:
            self._sub_id_counter += 1
            sub_id = self._sub_id_counter
            self._subscribers[sub_id] = (callback, args, kwargs)
        if not self._running:
            self.start()
        return sub_id

    def unsubscribe(self, sub_id):
        with self._lock:
            if sub_id in self._subscribers:
                del self._subscribers[sub_id]
                return True
            return False
        