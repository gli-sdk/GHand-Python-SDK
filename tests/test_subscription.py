import threading
import time

import pytest

from xiaoyao.subscription import SubscriptionManager


class FakeClient:
    def recv_data(self):
        time.sleep(0.01)
        return {"data": 1}


class FailingClient:
    def __init__(self, fail_after=0):
        self._calls = 0
        self._fail_after = fail_after

    def recv_data(self):
        self._calls += 1
        if self._calls > self._fail_after:
            raise RuntimeError("recv_data failed")
        return {"data": self._calls}


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

    assert sm._thread is not None
    assert sm._dispatcher_thread is not None
    # Allow a small buffer for background noise
    assert threading.active_count() <= threads_before + 2 + 1

    sm.stop()


def test_data_producer_clears_data_after_consecutive_errors():
    client = FailingClient(fail_after=2)
    sm = SubscriptionManager(client=client)
    received = []
    sm.subscribe(lambda data: received.append(data))
    sm.start()

    time.sleep(2)

    assert client._calls >= 3
    assert sm._data is None

    sm.stop()
