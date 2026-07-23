import sys
import types
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

sys.modules.setdefault("pysoem", types.ModuleType("pysoem"))
sys.modules.setdefault("netifaces", types.ModuleType("netifaces"))

from ghand._config import find_config_by_name, load_product_config
from ghand.comm.canfd_comm import CanfdComm
from ghand.comm.canfd_transport import pack_arbitration
from ghand.comm.modbus_codec import (
    get_joint_input_span,
    get_modbus_profile,
    parse_hand_type,
    parse_joints,
)
from ghand.comm.rs485_comm import Rs485Comm
from ghand.types import CtrlMode, ErrorCode, JointCommand, JointId, ProductType, State


class FakeResult:
    def __init__(self, registers=None):
        self.registers = registers or []

    def isError(self):
        return False


class FakeModbusClient:
    def __init__(self):
        self.single_writes = []
        self.multi_writes = []

    def write_register(self, address, value, device_id=None):
        self.single_writes.append((address, value, device_id))
        return FakeResult()

    def write_registers(self, address, values, device_id=None):
        self.multi_writes.append((address, list(values), device_id))
        return FakeResult()


class FakeCanfdHandshakeTransport:
    def __init__(self, response_func_code=0x02, response_data=b""):
        self.sent_frames = []
        self._response_sent = False
        self.response_func_code = response_func_code
        self.response_data = response_data
        self.read_calls = []

    def send_frame(self, can_id, data):
        self.sent_frames.append((can_id, data))
        return True

    def recv_frame(self, timeout_ms=50):
        if self._response_sent:
            return None
        self._response_sent = True
        can_id = pack_arbitration(0x31, 0x0A, ack=1, func_code=self.response_func_code)
        return can_id, self.response_data

    def read_registers(self, src_id, dst_id, addr, count, func_code=0x03, timeout_ms=500):
        self.read_calls.append((src_id, dst_id, addr, count, func_code, timeout_ms))
        return b"L1"


def test_g5_profile_keeps_existing_register_map():
    config = load_product_config(ProductType.G5)
    profile = get_modbus_profile(config)

    assert profile.name == "g5"
    assert profile.joint_control_addresses[JointId.THUMB_MCP] == 0x0011
    assert profile.joint_control_addresses[JointId.FF_MCP] == 0x001B
    assert profile.tactile_control_address == 0x002B
    assert get_joint_input_span(config.valid_joints, profile) == (0x1023, 54)


def test_l1_profile_loads_protocol_register_map():
    config = load_product_config(ProductType.L1)
    profile = get_modbus_profile(config)

    assert config.name == "GHand Lite 1"
    assert config.modbus_profile == "l1"
    assert profile.name == "l1"
    assert profile.joint_input_addresses[JointId.THUMB_TMC_FE] == 0x1023
    assert profile.joint_input_addresses[JointId.THUMB_TMC_AA] == 0x1026
    assert profile.joint_input_addresses[JointId.THUMB_TMC_PS] == 0x1029
    assert profile.joint_input_addresses[JointId.LF_MCP] == 0x1041
    assert profile.joint_control_addresses[JointId.THUMB_TMC_FE] == 0x0010
    assert profile.joint_control_addresses[JointId.THUMB_TMC_AA] == 0x0013
    assert profile.joint_control_addresses[JointId.THUMB_TMC_PS] == 0x0016
    assert profile.joint_control_addresses[JointId.LF_MCP] == 0x002E
    assert profile.tactile_control_address == 0x0031
    assert profile.canfd_connection_timer_address == 0x0037
    assert profile.canfd_connection_timer_registers == 2
    assert get_joint_input_span(config.valid_joints, profile) == (0x1023, 33)
    assert config.joint_limits[JointId.THUMB_TMC_AA] == (0.0, 30.0)
    assert config.joint_limits[JointId.THUMB_TMC_PS] == (0.0, 90.0)
    assert config.joint_limits[JointId.FF_MCP] == (0.0, 90.0)
    assert config.joint_limits[JointId.MF_MCP] == (0.0, 90.0)
    assert config.joint_limits[JointId.RF_MCP] == (0.0, 90.0)
    assert config.joint_limits[JointId.LF_MCP] == (0.0, 90.0)
    assert JointId.THUMB_TMC_FE not in config.joint_limits
    assert JointId.THUMB_MCP not in config.valid_joints
    assert JointId.FF_PIP not in config.joint_limits
    assert JointId.MF_PIP not in config.joint_limits
    assert JointId.RF_PIP not in config.joint_limits
    assert JointId.LF_PIP not in config.joint_limits


def test_canfd_g5_connection_uses_legacy_timer_register():
    comm = CanfdComm(load_product_config(ProductType.G5))
    comm._transport = FakeCanfdHandshakeTransport()

    assert comm._establish_connection() is True

    _, data = comm._transport.sent_frames[0]
    assert data == bytes.fromhex("00 31 00 01 00 00")


def test_canfd_l1_connection_uses_two_timer_registers():
    comm = CanfdComm(load_product_config(ProductType.L1))
    comm._transport = FakeCanfdHandshakeTransport()

    assert comm._establish_connection() is True

    _, data = comm._transport.sent_frames[0]
    assert data == bytes.fromhex("00 37 00 02 00 00 00 00")


def test_canfd_l1_connection_accepts_existing_usable_connection():
    comm = CanfdComm(load_product_config(ProductType.L1))
    comm._transport = FakeCanfdHandshakeTransport(
        response_func_code=0x82,
        response_data=b"\x03",
    )

    assert comm._establish_connection() is True

    assert comm._transport.read_calls == [(0x0A, 0x31, 0x1000, 1, 0x04, 500)]


def test_l1_config_can_be_found_by_device_name():
    config = find_config_by_name("GHand Lite 1")

    assert config is not None
    assert config.name == "GHand Lite 1"
    assert config.modbus_profile == "l1"

    alias_config = find_config_by_name("GHand Lite 1")
    assert alias_config is not None
    assert alias_config.name == "GHand Lite 1"


def test_l1_hand_type_uses_low_byte():
    assert parse_hand_type(bytes.fromhex("c001")) == 1
    assert parse_hand_type(bytes.fromhex("c002")) == 2


def test_l1_parse_joints_uses_l1_register_order():
    config = load_product_config(ProductType.L1)
    profile = get_modbus_profile(config)
    start, count = get_joint_input_span(config.valid_joints, profile)
    registers = [0] * count

    thumb_offset = profile.joint_input_addresses[JointId.THUMB_TMC_FE] - start
    registers[thumb_offset] = 0x0100
    registers[thumb_offset + 1] = 1234
    registers[thumb_offset + 2] = 0xFB07

    lf_offset = profile.joint_input_addresses[JointId.LF_MCP] - start
    registers[lf_offset] = 0x0000
    registers[lf_offset + 1] = 321
    registers[lf_offset + 2] = 0x0405

    joints = parse_joints(registers, config.valid_joints, profile, start)

    assert joints[0].id == JointId.THUMB_TMC_FE
    assert joints[0].state == State.RUNNING
    assert joints[0].angle == 123.4
    assert joints[0].speed == -5
    assert joints[0].torque == 7
    assert joints[-1].id == JointId.LF_MCP
    assert joints[-1].angle == 32.1


def test_parse_joints_tolerates_unknown_state_and_error_values():
    config = load_product_config(ProductType.L1)
    profile = get_modbus_profile(config)
    start, count = get_joint_input_span(config.valid_joints, profile)
    registers = [0] * count

    offset = profile.joint_input_addresses[JointId.THUMB_TMC_FE] - start
    registers[offset] = 0x1111
    registers[offset + 1] = 123
    registers[offset + 2] = 0x0405

    joints = parse_joints(registers, config.valid_joints, profile, start)

    assert joints[0].state == State.ABNORMAL_RUNNING
    assert joints[0].error == ErrorCode.UNKNOWN_ERROR


def test_rs485_g5_move_joints_keeps_shared_mode_layout():
    config = load_product_config(ProductType.G5)
    comm = Rs485Comm(config)
    comm._client = FakeModbusClient()

    comm.move_joints(
        [JointCommand(id=JointId.FF_MCP, angle=12.3, speed=4, torque=5)],
        CtrlMode.POSITION,
    )

    assert comm._client.single_writes == [(0x0010, 0x0000, 0x31)]
    assert comm._client.multi_writes == [(0x001B, [123, 0x0405], 0x31)]


def test_rs485_l1_move_joints_uses_three_register_layout():
    config = load_product_config(ProductType.L1)
    comm = Rs485Comm(config)
    comm._client = FakeModbusClient()

    comm.move_joints(
        [JointCommand(id=JointId.FF_MCP, angle=12.3, speed=-4, torque=5)],
        CtrlMode.SPEED,
    )

    assert comm._client.single_writes == []
    assert comm._client.multi_writes == [(0x001C, [0x0200, 123, 0xFC05], 0x31)]


def test_rs485_tactile_control_register_is_profile_specific():
    g5 = Rs485Comm(load_product_config(ProductType.G5))
    g5._client = FakeModbusClient()
    assert g5.open_tactile() is True
    assert g5._client.single_writes == [(0x002B, 0x0100, 0x31)]

    l1 = Rs485Comm(load_product_config(ProductType.L1))
    l1._client = FakeModbusClient()
    assert l1.open_tactile() is True
    assert l1._client.single_writes == [(0x0031, 0x0100, 0x31)]
