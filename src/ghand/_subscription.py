# Copyright 2026 GLITech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger("ghand")


class SubscriptionManager:
    """Manages background threads for receiving and dispatching device data."""

    _DEFAULT_INTERVAL_SEC = 0.01

    def __init__(self, client, is_connected=None):
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._dispatcher_thread = None
        self._client = client
        self._is_connected = is_connected
        self._data = None
        self._sub_id_counter = 0
        self._subscribers = {}
        self._interval_sec = self._DEFAULT_INTERVAL_SEC

    def start(self):
        """Start the background producer and dispatcher threads."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._data_producer, daemon=True)
            self._thread.start()
            self._dispatcher_thread = threading.Thread(target=self._data_dispatcher, daemon=True)
            self._dispatcher_thread.start()

    def stop(self):
        """Stop the background threads and clear subscription state."""
        self._running = False
        current = threading.current_thread()
        if self._thread and self._thread is not current:
            self._thread.join(timeout=1)
        self._thread = None
        if self._dispatcher_thread and self._dispatcher_thread is not current:
            self._dispatcher_thread.join(timeout=1)
        self._dispatcher_thread = None
        with self._lock:
            self._data = None
            self._subscribers.clear()

    def _data_producer(self):
        """Background thread that continuously receives data from the device."""
        while self._running:
            try:
                data = self._client.recv_data()
                with self._lock:
                    self._data = data
            except Exception as e:
                with self._lock:
                    self._data = None
                if self._is_connected is not None and not self._is_connected():
                    logger.error("Subscription stopped: %s", e)
                    self.stop()
                    break
                logger.error("Error receiving data: %s", e)
            time.sleep(self._interval_sec)

    def _data_dispatcher(self):
        """Background thread that dispatches received data to all subscribers."""
        while self._running:
            with self._lock:
                data = self._data
                subscribers_copy = self._subscribers.copy()
            if data:
                for sub_id, (callback, args, kwargs) in subscribers_copy.items():
                    if not self._running:
                        break
                    if callback:
                        try:
                            callback(data, *args, **kwargs)
                        except Exception as e:
                            logger.error("Error in callback %s: %s", sub_id, e)
            time.sleep(self._interval_sec)

    def subscribe(
        self,
        callback: Optional[Callable] = None,
        *args,
        interval_ms: int | None = None,
        **kwargs,
    ):
        """Register a callback to receive device data updates.

        Args:
            callback: Callable invoked with received data.
            interval_ms: Optional polling interval in milliseconds.

        Returns:
            Subscription ID.
        """
        if self._is_connected is not None and not self._is_connected():
            raise RuntimeError("Device is not connected")

        with self._lock:
            if interval_ms is not None:
                self._interval_sec = interval_ms / 1000.0
            self._sub_id_counter += 1
            sub_id = self._sub_id_counter
            self._subscribers[sub_id] = (callback, args, kwargs)
        if not self._running:
            self.start()
        return sub_id

    def unsubscribe(self, sub_id):
        """Remove a previously registered subscription.

        Args:
            sub_id: Subscription ID returned by ``subscribe``.

        Returns:
            True if the subscription existed and was removed.
        """
        with self._lock:
            if sub_id not in self._subscribers:
                return False
            del self._subscribers[sub_id]
            should_stop = not self._subscribers
        if should_stop:
            self.stop()
        return True
