"""Offline raw-status regression tests; no device/client is constructed."""
import struct
from types import SimpleNamespace
import unittest

from ghand._product_config import ProductConfig, TactileRegionConfig
from ghand.comm.ethercat_comm import EtherCATComm
from ghand.comm.ethercat_protocol import compute_tpdo_size
from ghand.types import ProductType, TactileData, TactileSensorId


class TactileRawStatusTests(unittest.TestCase):
    def fixture(self, state, error):
        ids = [TactileSensorId[name] for name in ("THUMB", "FF", "MF", "RF", "LF")]
        counts = [38, 31, 31, 31, 31]
        config = ProductConfig(has_tactile=True, product_type=ProductType.GHand5,
                               tactile_regions=[TactileRegionConfig(i, n) for i, n in zip(ids, counts)])
        packet = bytes(compute_tpdo_size(0, None, ProductType.GHand5)) + bytes([state, error])
        for n in counts:
            packet += struct.pack("<hHH", -10, 20, 30) + struct.pack("<bbB", -2, 3, 4) * n
        comm = SimpleNamespace(_config=config, _expected_tpdo_size=len(packet),
                               _recv_tpdo_data=lambda: packet)
        return comm, packet

    def check_values(self, values, state, error):
        self.assertEqual(len(values), 5)
        for sensor, info in values.items():
            self.assertEqual(getattr(info, "raw_state", None), state)
            self.assertEqual(getattr(info, "error", None), error)
            self.assertEqual(info.state, bool(state & (1 << sensor.value)))
            self.assertEqual(info.resultant_force, [-1., 2., 3.])
            count = 38 if sensor == TactileSensorId.THUMB else 31
            self.assertEqual(info.distributed_force, [-0.2, 0.3, 0.4] * count)

    def test_poll_retains_packet_status_and_error(self):
        for state, error in ((31, 0), (5, 128)):
            with self.subTest(state=state, error=error):
                comm, _ = self.fixture(state, error)
                self.check_values(EtherCATComm.get_tactile_data(comm), state, error)

    def test_callback_retains_packet_status_and_error(self):
        for state, error in ((31, 0), (5, 128)):
            with self.subTest(state=state, error=error):
                comm, packet = self.fixture(state, error)
                callbacks, received = [], []
                comm.subscribe = lambda callback, **kwargs: callbacks.append(callback)
                EtherCATComm.subscribe_device_data(comm, received.append, include_tactile=True)
                callbacks[0](packet)
                self.check_values(received[0].tactile, state, error)

    def test_unsupplied_status_is_unknown_not_success(self):
        info = TactileData()
        self.assertTrue(hasattr(info, "raw_state"))
        self.assertTrue(hasattr(info, "error"))
        self.assertIsNone(info.raw_state)
        self.assertIsNone(info.error)


if __name__ == "__main__":
    unittest.main()
