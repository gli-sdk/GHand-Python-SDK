# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

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
        self._stop_event = threading.Event()
        self._running = False
        self._thread = None
        self._dispatcher_thread = None
        self._client = client
        self._is_connected = is_connected
        self._data = None
        self._data_seq = 0
        self._dispatched_seq = 0
        self._sub_id_counter = 0
        self._subscribers = {}
        self._interval_sec = self._DEFAULT_INTERVAL_SEC

    def start(self):
        """Start the background producer and dispatcher threads."""
        with self._lock:
            self._start_locked()

    def _start_locked(self) -> None:
        if self._running:
            return
        stop_event = threading.Event()
        producer = threading.Thread(
            target=self._data_producer, args=(stop_event,), daemon=True
        )
        dispatcher = threading.Thread(
            target=self._data_dispatcher, args=(stop_event,), daemon=True
        )
        self._stop_event = stop_event
        self._thread = producer
        self._dispatcher_thread = dispatcher
        self._running = True
        producer.start()
        dispatcher.start()

    def stop(self):
        """Stop the background threads and clear subscription state."""
        with self._lock:
            threads = self._stop_locked(clear_subscribers=True)
        self._join_threads(threads)

    def _stop_locked(self, *, clear_subscribers: bool) -> tuple:
        self._stop_event.set()
        self._running = False
        threads = (self._thread, self._dispatcher_thread)
        self._thread = None
        self._dispatcher_thread = None
        self._data = None
        self._data_seq = 0
        self._dispatched_seq = 0
        if clear_subscribers:
            self._subscribers.clear()
            self._interval_sec = self._DEFAULT_INTERVAL_SEC
        return threads

    @staticmethod
    def _join_threads(threads: tuple) -> None:
        current = threading.current_thread()
        for name, thread in zip(("producer", "dispatcher"), threads):
            if thread is None or thread is current:
                continue
            thread.join(timeout=1)
            if thread.is_alive():
                logger.warning("Subscription %s thread did not stop within timeout", name)

    def _request_stop_from_worker(self, stop_event: threading.Event) -> None:
        """Signal worker shutdown without joining from inside a worker thread."""
        stop_event.set()
        with self._lock:
            if self._stop_event is stop_event:
                self._running = False

    def _recompute_interval_locked(self) -> None:
        intervals = [
            item[3] for item in self._subscribers.values() if item[3] is not None
        ]
        self._interval_sec = min(intervals) if intervals else self._DEFAULT_INTERVAL_SEC

    def _data_producer(self, stop_event: threading.Event):
        """Background thread that continuously receives data from the device."""
        while not stop_event.is_set():
            try:
                data = self._client.recv_data()
                if stop_event.is_set():
                    break
                with self._lock:
                    if self._stop_event is not stop_event:
                        break
                    self._data = data
                    self._data_seq += 1
            except Exception as e:
                with self._lock:
                    if self._stop_event is stop_event:
                        self._data = None
                if self._is_connected is not None and not self._is_connected():
                    logger.error("Subscription stopped: %s", e)
                    self._request_stop_from_worker(stop_event)
                    break
                logger.error("Error receiving data: %s", e)
            time.sleep(self._interval_sec)

    def _data_dispatcher(self, stop_event: threading.Event):
        """Background thread that dispatches received data to all subscribers."""
        while not stop_event.is_set():
            with self._lock:
                if self._stop_event is not stop_event:
                    break
                data = self._data
                data_seq = self._data_seq
                subscribers_copy = self._subscribers.copy()
                if data_seq == self._dispatched_seq:
                    data = None
                else:
                    self._dispatched_seq = data_seq
            if data:
                for sub_id, (callback, args, kwargs, _) in subscribers_copy.items():
                    if stop_event.is_set():
                        break
                    if callback:
                        try:
                            callback(data, *args, **kwargs)
                        except Exception:
                            logger.exception("Error in callback %s", sub_id)
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
            interval_sec = (
                interval_ms / 1000.0 if interval_ms is not None else None
            )
            self._sub_id_counter += 1
            sub_id = self._sub_id_counter
            self._subscribers[sub_id] = (callback, args, kwargs, interval_sec)
            self._recompute_interval_locked()
            self._start_locked()
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
            self._recompute_interval_locked()
            threads = self._stop_locked(clear_subscribers=False) if not self._subscribers else ()
        self._join_threads(threads)
        return True
