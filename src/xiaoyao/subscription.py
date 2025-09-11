import threading
import time
from .client import Client
from typing import Callable, Optional


class SubscriptionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._client = Client()
        self._data = None
        self._sub_id_counter = 0
        self._lock = threading.Lock()
        self._subscribers = {}

    def start(self):
        if not self._running:
            self._running = True
            res = self._client.pdo_init()
            print(f"PDO initialized: {res}")
            self._thread = threading.Thread(
                target=self._data_producer, daemon=True)
            self._thread.start()
            self._dispatcher_thread = threading.Thread(
                target=self._data_dispatcher, daemon=True)
            self._dispatcher_thread.start()

    def stop(self):
        """停止订阅"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        if self._dispatcher_thread:
            self._dispatcher_thread.join(timeout=1)

    def _data_producer(self):
        """数据生产者线程"""
        while self._running:
            data = self._client.recv_data()
            self._data = data
            time.sleep(0.1)

    def _data_dispatcher(self):
        while self._running:
            if self._data:
                with self._lock:
                    subscribers_copy = self._subscribers.copy()
                for sub_id, (callback, args, kwargs) in subscribers_copy.items():
                    if callback:
                        try:
                            callback(self._data, *args, **kwargs)
                        except Exception as e:
                            print(f"Error in callback {sub_id}: {e}")
            time.sleep(0.1)

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
