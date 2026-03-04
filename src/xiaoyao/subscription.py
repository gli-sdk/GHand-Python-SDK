import threading
import time
import logging
from .ecatclient import EthercatClient
from typing import Callable, Optional

logger = logging.getLogger("xiaoyao")

class SubscriptionManager:
    def __init__(self, client=None):
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        # 如果提供了客户端实例，则使用它，否则创建新的实例
        self._client = client if client else EthercatClient()
        self._data = None
        self._sub_id_counter = 0
        self._lock = threading.Lock()
        self._subscribers = {}
        self._is_client_owner = client is None  # 标记是否拥有客户端实例

    def start(self):
        if not self._running:
            self._running = True
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
            try:
                data = self._client.recv_data()
                self._data = data
            except Exception as e:
                logger.error(f"Error receiving data: {e}")
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
                            logger.error(f"Error in callback {sub_id}: {e}")
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
                # 如果没有订阅者了，自动停止
                if not self._subscribers:
                    self.stop()
                return True
            return False