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

`GHandError`, `CommunicationError`, and `HandStateError` are available as the
stable SDK exception hierarchy for new code. Existing methods continue to raise
`RuntimeError` where that was already part of the V2.2 behavior.

`GHand.get_diagnostics()` exposes the latest SDK error in a broader
machine-readable diagnostics structure.

## Device error bitfields

`HandState` keeps the protocol bytes and also exposes typed `IntFlag` views:

```python
from ghand import HandCriticalError, HandFault, HandWarning

state = hand.get_hand_info()
if state.warnings & HandWarning.FAN_ABNORMAL:
    print("Fan warning")
if state.faults & HandFault.POSITION_SENSOR_ABNORMAL:
    print("Affected joint slots:", state.fault_indices(HandFault.POSITION_SENSOR_ABNORMAL))
if state.critical_errors & HandCriticalError.TEMPERATURE_TOO_HIGH:
    print("Critical temperature")
```

The original `error_warn`, `error_fault`, and `error_critical` byte fields remain
available for protocol-level access. `state.active_errors()` returns readable
descriptions for all active and reserved bits.

Fault indices are `0..12`. For the first five categories they follow the protocol's
active-joint order; for `ZEROING_MOTOR_COMMUNICATION` they mean `Motor0..Motor12`.
