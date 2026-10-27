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

`HandData.error_warn` and `HandData.error_critical` store typed `IntFlag` values.
`HandData.error_fault` stores a `HandFaultData` object with the complete fault bitfield:

```python
from ghand import HandCriticalError, HandFault, HandWarning

state = hand.get_hand_info()
if state.error_warn & HandWarning.FAN_ABNORMAL:
    print("Fan warning")
if state.error_warn & HandWarning.SELF_TEST_ERROR:
    print("Self-test warning")
if state.error_fault.categories & HandFault.POSITION_SENSOR_ABNORMAL:
    print("Affected joint slots:", state.error_fault.indices(HandFault.POSITION_SENSOR_ABNORMAL))
if state.error_critical & HandCriticalError.TEMPERATURE_TOO_HIGH:
    print("Critical temperature")
```

For protocol-level access, use `state.error_warn.to_bytes(6, "little")`,
`state.error_fault.value.to_bytes(12, "little")`, and
`state.error_critical.to_bytes(6, "little")`. `state.active_errors()` returns readable
descriptions for all active and reserved bits.

Fault indices are `0..12`. For the first five categories they follow the protocol's
active-joint order; for `ZEROING_MOTOR_COMMUNICATION` they mean `Motor0..Motor12`.
