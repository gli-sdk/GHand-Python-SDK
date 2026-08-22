"""Query and print the device self-test error information.

Run: python examples/tutorial/11.self_test_error.py
"""


from ghand import ProductType
from ghand.ghand import CommType, ErrorCode, GHand
from ghand.types import MotorCheckError, SelfTestError, TactileCheckError, ZeroingError


def _fmt_motor_errors(errors, describe_code=None) -> str:
    """Format 13-channel motor errors as readable text.

    Args:
        errors: List of MotorDiagnosticError entries.
        describe_code: Optional callable mapping an error byte to its
            human-readable description.
    """
    if not errors:
        return "none"
    parts = []
    for e in errors:
        desc = describe_code(e.error_code) if describe_code else ""
        tail = f" ({desc})" if desc else ""
        parts.append(
            f"motor={e.motor_index} "
            f"joint={e.joint_id.name if e.joint_id is not None else 'unknown'} "
            f"code=0x{e.error_code:02X}{tail}"
        )
    return "; ".join(parts)


def _describe_enum(enum_type, code: int) -> str:
    try:
        return enum_type(code).name
    except ValueError:
        return f"unknown (0x{code:02X})"


def _describe_tactile(code: int) -> str:
    names = [
        flag.name
        for flag in TactileCheckError
        if flag != TactileCheckError.NONE and code & flag
    ]
    return ", ".join(names) if names else f"unknown (0x{code:02X})"


def _fmt_single_code(summary, flag, code, description) -> str:
    """Format a single-value error field. Show 'none' if not queried."""
    if not (summary & flag):
        return "none"
    return f"0x{code:02X}" if code == 0 else f"0x{code:02X} ({description})"


def main():
    hand = GHand(product_type=ProductType.GHand5, comm_type=CommType.ETHERCAT)
    connected = hand.open("auto")
    if not connected:
        print("Connection failed")
        return

    hand_info = hand.get_hand_info()
    if hand_info.error != ErrorCode.SELF_TEST_ERROR:
        print(f"No self-test error (device error={hand_info.error.name})")
        hand.close()
        return

    info = hand.get_self_test_error_info()

    print("Self-test failed! Error details:")
    print(f"  {'summary':<16} 0x{int(info.summary):02X}  ({info.summary.name})")
    print(f"  {'version':<16} 0x{int(info.version):02X}")
    print(f"  {'position_sensor':<16} {_fmt_motor_errors(info.position_sensor, lambda c: 'position sensor abnormal' if c else '')}")
    print(f"  {'tactile_sensor':<16} {_fmt_motor_errors(info.tactile_sensor, _describe_tactile)}")
    print(f"  {'temperature':<16} {_fmt_single_code(info.summary, SelfTestError.TEMPERATURE_SENSOR, info.temperature, 'temperature sensor abnormal')}")
    print(f"  {'fan':<16} {_fmt_single_code(info.summary, SelfTestError.FAN, info.fan, 'fan abnormal')}")
    print(f"  {'zeroing':<16} {_fmt_motor_errors(info.zeroing, lambda c: _describe_enum(ZeroingError, c))}")
    print(f"  {'motor':<16} {_fmt_motor_errors(info.motor, lambda c: _describe_enum(MotorCheckError, c))}")

    hand.close()


if __name__ == "__main__":
    main()
