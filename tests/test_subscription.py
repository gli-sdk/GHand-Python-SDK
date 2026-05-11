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


def test_subscription_periods_are_configurable():
    sm = SubscriptionManager(
        client=FakeClient(),
        recv_period_s=0.02,
        dispatch_period_s=0.03,
    )

    assert sm.recv_period_s == pytest.approx(0.02)
    assert sm.dispatch_period_s == pytest.approx(0.03)

    sm.configure_periods(recv_period_s=0.01, dispatch_period_s=0.015)

    assert sm.recv_period_s == pytest.approx(0.01)
    assert sm.dispatch_period_s == pytest.approx(0.015)


def test_subscription_periods_must_be_positive():
    with pytest.raises(ValueError):
        SubscriptionManager(client=FakeClient(), recv_period_s=0.0)
    with pytest.raises(ValueError):
        SubscriptionManager(client=FakeClient(), dispatch_period_s=-0.01)
