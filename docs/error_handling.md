# Error Handling

Most existing public APIs keep their V2.2-compatible return values. Methods
that return `False` update `GHand.get_last_result()` with a machine-readable
`SdkError` and message.

Use:

```python
result = hand.move_joints(joints)
if not result:
    last = hand.get_last_result()
    print(last.code, last.message)
```

Existing methods continue to raise
`RuntimeError` where that was already part of the V2.2 behavior.

`GHand.get_diagnostics()` exposes the latest SDK error in a broader
machine-readable diagnostics structure.

## Device error bitfields

`HandData.error_warn`, `HandData.error_fault`, and `HandData.error_critical`
store typed `IntFlag` values. Each `HandFault` member identifies one fault
on a specific joint or motor:

```python
from ghand import HandCriticalError, HandFault, HandWarning

state = hand.get_hand_info()
if state.error_warn & HandWarning.FAN_ABNORMAL:
    print("Fan warning")
if state.error_warn & HandWarning.SELF_TEST_ERROR:
    print("Self-test warning")
if state.error_fault & HandFault.POSITION_SENSOR_ABNORMAL_THUMB2:
    print("Thumb2 position sensor abnormal")
if state.error_critical & HandCriticalError.TEMPERATURE_TOO_HIGH:
    print("Critical temperature")
```

For protocol-level access, use `state.error_warn.to_bytes(6, "little")`,
`state.error_fault.to_bytes(12, "little")`, and
`state.error_critical.to_bytes(6, "little")`.

Fault member names use the protocol's joint names (`THUMB2` through `LF3`)
and motor names (`MOTOR0` through `MOTOR12`). Bits 78..95 are reserved and
remain preserved in the bitfield without named members.
