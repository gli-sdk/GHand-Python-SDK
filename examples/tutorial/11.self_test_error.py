"""Query and print the device self-test error information.

Run: python examples/tutorial/11.self_test_error.py
"""


from ghand import ProductType
from ghand.ghand import CommType, ErrorCode, GHand
from ghand.types import JointError, MotorCheckError, SelfTestError, SensorError


def _describe_flags(enum_type, code: int) -> str:
    """Render a per-channel bit-mask error byte as flag names."""
    names = [
        flag.name
        for flag in enum_type
        if flag != enum_type.NONE and code & flag
    ]
    return ", ".join(names) if names else f"unknown (0x{code:02X})"


def _describe_enum(enum_type, code: int) -> str:
    try:
        return enum_type(code).name
    except ValueError:
        return f"unknown (0x{code:02X})"


def _describe_summary(summary: SelfTestError) -> str:
    names = [
        flag.name
        for flag in SelfTestError
        if flag != SelfTestError.NONE and summary & flag
    ]
    return ", ".join(names) if names else "NONE"


def _fmt_channel_errors(errors, describe_code) -> str:
    """Format 13-channel errors as readable text.

    Args:
        errors: List of MotorDiagnosticError entries.
        describe_code: Callable mapping an error byte to its description.
    """
    if not errors:
        return "none"
    parts = []
    for e in errors:
        parts.append(
            f"slot={e.motor_index} "
            f"joint={e.joint_id.name if e.joint_id is not None else 'unknown'} "
            f"code=0x{e.error_code:02X} ({describe_code(e.error_code)})"
        )
    return "; ".join(parts)


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
    print(
        f"  {'summary':<10} 0x{int(info.summary):02X}  "
        f"({_describe_summary(info.summary)})"
    )
    print(
        f"  {'sensor':<10} "
        f"{_fmt_channel_errors(info.sensor, lambda c: _describe_flags(SensorError, c))}"
    )
    print(
        f"  {'joint':<10} "
        f"{_fmt_channel_errors(info.joint, lambda c: _describe_flags(JointError, c))}"
    )
    print(
        f"  {'motor':<10} "
        f"{_fmt_channel_errors(info.motor, lambda c: _describe_enum(MotorCheckError, c))}"
    )

    hand.close()


if __name__ == "__main__":
    main()
