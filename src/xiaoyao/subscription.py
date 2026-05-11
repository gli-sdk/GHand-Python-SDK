import threading
import time
import logging
from .ecatclient import EthercatClient
from typing import Callable, Optional

logger = logging.getLogger("xiaoyao")

class SubscriptionManager:
    def __init__(self, client=None, recv_period_s=0.02, dispatch_period_s=0.02):
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._dispatcher_thread = None
        # 如果提供了客户端实例，则使用它，否则创建新的实例
        self._client = client if client else EthercatClient()
        self._data = None
        self._sub_id_counter = 0
        self._subscribers = {}
        self._recv_period_s = self._validate_period("recv_period_s", recv_period_s)
        self._dispatch_period_s = self._validate_period("dispatch_period_s", dispatch_period_s)
        self._is_client_owner = client is None  # 标记是否拥有客户端实例

    @staticmethod
    def _validate_period(name, value):
        if value <= 0:
            raise ValueError(f"{name} must be > 0")
        return float(value)

    @property
    def recv_period_s(self):
        return self._recv_period_s

    @property
    def dispatch_period_s(self):
        return self._dispatch_period_s

    def configure_periods(self, *, recv_period_s=None, dispatch_period_s=None):
        if recv_period_s is not None:
            self._recv_period_s = self._validate_period("recv_period_s", recv_period_s)
        if dispatch_period_s is not None:
            self._dispatch_period_s = self._validate_period("dispatch_period_s", dispatch_period_s)

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
            self._thread = None
        if self._dispatcher_thread:
            self._dispatcher_thread.join(timeout=1)
            self._dispatcher_thread = None
        self._data = None

    def _data_producer(self):
        """数据生产者线程"""
        consecutive_errors = 0
        while self._running:
            try:
                data = self._client.recv_data()
                self._data = data
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error receiving data: {e} (consecutive: {consecutive_errors})")
                if consecutive_errors >= 3:
                    logger.error("Data producer encountered too many consecutive errors, clearing stale data")
                    self._data = None
                time.sleep(min(0.1 * (2 ** min(consecutive_errors, 5)), 5.0))
                continue
            time.sleep(self._recv_period_s)

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
            time.sleep(self._dispatch_period_s)

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
