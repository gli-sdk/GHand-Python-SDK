import sys
import types
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

sys.modules.setdefault("pysoem", types.ModuleType("pysoem"))
sys.modules.setdefault("netifaces", types.ModuleType("netifaces"))

from ghand.comm import canfd_comm
from ghand.comm import ethercat_client
from ghand._config import load_product_config
from ghand.comm.canfd_comm import CanfdComm
from ghand.comm.ethercat_comm import EthercatComm
from ghand.ghand import GHand
from ghand.types import (
    CtrlMode,
    ErrorCode,
    JointCommand,
    JointData,
    JointId,
    ProductConfig,
    ProductType,
    State,
    TactileRegionConfig,
    TactileSensorId,
)


class FakeTransport:
    def __init__(self):
        self._dev_handle = 0
        self._chn_handle = 0
        self.closed = False
        self.open_calls = 0

    def open(self):
        self.open_calls += 1
        self._dev_handle = 111
        self._chn_handle = 222
        self.closed = False
        return True

    def close(self):
        self.closed = True
        self._dev_handle = 0
        self._chn_handle = 0
        return True


def test_canfd_connect_closes_transport_when_handshake_fails(monkeypatch):
    monkeypatch.setattr(canfd_comm, "CanfdTransport", FakeTransport)
    comm = CanfdComm(config=object())
    comm._CONNECT_RETRIES = 1
    monkeypatch.setattr(comm, "_establish_connection", lambda: False)

    assert comm.connect("fake-adapter") is False

    assert comm._connected is False
    assert comm._transport.closed is True
    assert comm._transport._dev_handle == 0
    assert comm._transport._chn_handle == 0


def test_canfd_connect_retries_after_handshake_failure(monkeypatch):
    monkeypatch.setattr(canfd_comm, "CanfdTransport", FakeTransport)
    comm = CanfdComm(config=object())
    comm._CONNECT_RETRIES = 2
    comm._CONNECT_RETRY_DELAY_SEC = 0
    comm._MIN_REOPEN_INTERVAL_SEC = 0

    handshake_results = iter([False, True])
    monkeypatch.setattr(comm, "_establish_connection", lambda: next(handshake_results))

    assert comm.connect("fake-adapter") is True

    assert comm._connected is True
    assert comm._transport.open_calls == 2


def test_canfd_disconnect_waits_after_delete_before_close(monkeypatch):
    comm = CanfdComm(config=object())
    comm._transport = FakeTransport()
    comm._transport.open()
    comm._connected = True
    comm._DELETE_CONNECTION_SETTLE_SEC = 0.123
    events = []

    monkeypatch.setattr(comm, "_delete_connection", lambda: events.append("delete"))
    monkeypatch.setattr(
        canfd_comm.time,
        "sleep",
        lambda delay: events.append(("sleep", delay)),
    )

    close = comm._transport.close

    def close_with_event():
        events.append("close")
        return close()

    comm._transport.close = close_with_event

    assert comm.disconnect() is True

    assert events == ["delete", ("sleep", 0.123), "close"]


class FakeComm:
    def __init__(self):
        self.disconnect_called = False
        self.connected = False

    def search_adapters(self):
        return ["fake-adapter"]

    def connect(self, _adapter):
        self.connected = True
        return True

    def disconnect(self):
        self.disconnect_called = True
        self.connected = False
        return True

    def is_connected(self):
        return self.connected


def test_ghand_open_disconnects_when_product_verification_fails():
    hand = GHand.__new__(GHand)
    hand._opened = False
    hand._comm = FakeComm()
    hand._resolve_product_type = lambda: False

    assert GHand.open(hand, "auto") is False

    assert hand._opened is False
    assert hand._comm.disconnect_called is True


class FakeAutoComm:
    def __init__(self):
        self.connect_calls = []
        self.disconnect_calls = 0
        self.connected = False

    def search_adapters(self):
        return ["bad-adapter", "good-adapter"]

    def connect(self, adapter):
        self.connect_calls.append(adapter)
        self.connected = True
        return True

    def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False
        return True

    def is_connected(self):
        return self.connected


def test_ghand_auto_open_continues_after_product_verification_failure():
    hand = GHand.__new__(GHand)
    hand._opened = False
    hand._comm = FakeAutoComm()
    verification_results = iter([False, True])
    hand._resolve_product_type = lambda: next(verification_results)

    assert GHand.open(hand, "auto") is True

    assert hand._comm.connect_calls == ["bad-adapter", "good-adapter"]
    assert hand._comm.disconnect_calls == 1
    assert hand._opened is True
    assert hand.is_connected() is True


def test_ghand_is_connected_resets_stale_opened_state():
    hand = GHand.__new__(GHand)
    hand._opened = True
    hand._comm = FakeComm()
    hand._comm.connected = False

    assert GHand.is_connected(hand) is False

    assert hand._opened is False


def test_ghand_close_disconnects_when_comm_is_connected_but_opened_is_false():
    hand = GHand.__new__(GHand)
    hand._opened = False
    hand._comm = FakeComm()
    hand._comm.connected = True

    assert GHand.close(hand) is True

    assert hand._comm.disconnect_called is True
    assert hand._opened is False


class FakeEthercatClientForComm:
    def __init__(self):
        self.connect_calls = 0
        self.run_calls = 0
        self.disconnect_calls = 0
        self.input_size = 10

    def connect(self, _adapter):
        self.connect_calls += 1
        return True

    def run(self, _expected_input_size, _expected_output_size):
        self.run_calls += 1
        return self.run_calls == 2

    def disconnect(self):
        self.disconnect_calls += 1


def make_g5_like_config() -> ProductConfig:
    valid_joints = list(JointId)
    joint_limits = {
        JointId.THUMB_PIP: (0.0, 66.0),
        JointId.THUMB_MCP: (0.0, 50.0),
        JointId.THUMB_SWING: (20.0, 90.0),
        JointId.THUMB_ROTATION: (-10.0, 60.0),
        JointId.FF_PIP: (0.0, 80.0),
        JointId.FF_MCP: (0.0, 90.0),
        JointId.FF_SWING: (-10.0, 10.0),
        JointId.MF_PIP: (0.0, 90.0),
        JointId.MF_MCP: (0.0, 90.0),
        JointId.RF_PIP: (0.0, 90.0),
        JointId.RF_MCP: (0.0, 90.0),
        JointId.LF_PIP: (0.0, 74.0),
        JointId.LF_MCP: (0.0, 90.0),
    }
    tactile_regions = [
        TactileRegionConfig(TactileSensorId.THUMB, 52),
        TactileRegionConfig(TactileSensorId.FF, 31),
        TactileRegionConfig(TactileSensorId.MF, 31),
        TactileRegionConfig(TactileSensorId.RF, 31),
        TactileRegionConfig(TactileSensorId.LF, 31),
    ]
    return ProductConfig(
        name="XIAOYAO-Hand",
        model="G5-test",
        valid_joints=valid_joints,
        joint_limits=joint_limits,
        has_tactile=True,
        tactile_regions=tactile_regions,
    )


def test_ethercat_comm_retries_full_connect_when_run_fails(monkeypatch):
    comm = EthercatComm.__new__(EthercatComm)
    comm._client = FakeEthercatClientForComm()
    comm._expected_tpdo_size = 10
    comm._expected_tpdo_sizes = (10,)
    comm._expected_rpdo_size = 8
    comm._tpdo_layouts = {10: make_g5_like_config()}
    comm._CONNECT_RETRIES = 2
    comm._CONNECT_RETRY_DELAY_SEC = 0

    assert comm.connect("fake-adapter") is True

    assert comm._client.connect_calls == 2
    assert comm._client.run_calls == 2
    assert comm._client.disconnect_calls == 1


class FakeEthercatClientWithInputSize:
    def __init__(self, input_size):
        self.input_size = input_size
        self.output_size = 80
        self.run_expected_input_size = None
        self.run_expected_output_size = None

    def connect(self, _adapter):
        return True

    def run(self, expected_input_size, expected_output_size):
        self.run_expected_input_size = expected_input_size
        self.run_expected_output_size = expected_output_size
        return True

    def disconnect(self):
        return None


class FakeEthercatClientForSend:
    def __init__(self):
        self.sent = []

    def send_data(self, data):
        self.sent.append(data)


class FakeEthercatClientForRecv:
    def __init__(self, data):
        self.data = data

    def recv_data(self):
        return self.data


def test_ethercat_comm_selects_compat_636_tpdo_layout():
    config = make_g5_like_config()
    comm = EthercatComm.__new__(EthercatComm)
    comm._client = FakeEthercatClientWithInputSize(636)
    comm._CONNECT_RETRIES = 1
    comm._CONNECT_RETRY_DELAY_SEC = 0
    comm.update_config(config)

    assert comm.connect("fake-adapter") is True

    assert comm._client.run_expected_input_size == (636, 708)
    assert comm._client.run_expected_output_size == 80
    assert comm._expected_tpdo_size == 636
    assert [region.count for region in comm.config.tactile_regions] == [28, 31, 31, 31, 31]


def test_ethercat_comm_keeps_default_708_tpdo_layout():
    config = make_g5_like_config()
    comm = EthercatComm.__new__(EthercatComm)
    comm._client = FakeEthercatClientWithInputSize(708)
    comm._CONNECT_RETRIES = 1
    comm._CONNECT_RETRY_DELAY_SEC = 0
    comm.update_config(config)

    assert comm.connect("fake-adapter") is True

    assert comm._expected_tpdo_size == 708
    assert [region.count for region in comm.config.tactile_regions] == [52, 31, 31, 31, 31]


def test_ethercat_l1_accepts_extended_pdo_sizes_and_packs_per_joint_commands():
    config = load_product_config(ProductType.L1)
    comm = EthercatComm.__new__(EthercatComm)
    comm._client = FakeEthercatClientForSend()
    comm.update_config(config)

    assert comm._expected_tpdo_sizes == (92, 1302)
    assert comm._expected_rpdo_size == 36

    comm.move_joints(
        [JointCommand(id=JointId.FF_MCP, angle=12.3, speed=-4, torque=5)],
        CtrlMode.SPEED,
    )

    data = comm._client.sent[-1]
    assert len(data) == 36
    assert data[0:6] == bytes.fromhex("02 00 00 00 00 00")
    assert data[12:18] == bytes.fromhex("02 00 7b 00 fc 05")

    comm.stop()
    assert comm._client.sent[-1][0:6] == bytes.fromhex("00 01 00 00 00 00")


def test_ethercat_l1_extended_tpdo_parses_joint_prefix():
    config = load_product_config(ProductType.L1)
    data = bytearray(1302)
    offset = 4
    for joint_id in config.valid_joints:
        if joint_id == JointId.FF_MCP:
            data[offset:offset + 6] = bytes.fromhex("01 00 78 00 fc 05")
        else:
            data[offset:offset + 6] = bytes.fromhex("00 00 00 00 00 00")
        offset += 6

    comm = EthercatComm.__new__(EthercatComm)
    comm._client = FakeEthercatClientForRecv(bytes(data))
    comm.update_config(config)

    joints = comm.get_joints()
    ff_mcp = next(joint for joint in joints if joint.id == JointId.FF_MCP)

    assert isinstance(ff_mcp, JointData)
    assert ff_mcp.state == State.RUNNING
    assert ff_mcp.error == ErrorCode.NORMAL
    assert ff_mcp.angle == 12.0
    assert ff_mcp.speed == -4
    assert ff_mcp.torque == 5


class FakeMasterOpenRaises:
    def __init__(self):
        self.in_op = False
        self.do_check_state = False
        self.close_calls = 0

    def open(self, _adapter):
        raise RuntimeError("open failed")

    def close(self):
        self.close_calls += 1


def test_ethercat_client_cleans_up_and_rebuilds_master_when_open_raises(monkeypatch):
    masters = []

    def master_factory():
        master = FakeMasterOpenRaises()
        masters.append(master)
        return master

    monkeypatch.setattr(ethercat_client.pysoem, "Master", master_factory, raising=False)

    client = ethercat_client.EthercatClient()
    release_calls = []
    monkeypatch.setattr(client, "_acquire_lock", lambda _adapter: True)
    monkeypatch.setattr(client, "_release_lock", lambda: release_calls.append(True))

    assert client.connect("fake-adapter") is False

    assert masters[0].close_calls == 1
    assert client._master is masters[1]
    assert client._connected is False
    assert client._slave is None
    assert release_calls == [True]
