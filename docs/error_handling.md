# Error Handling

Check API return values and handle communication exceptions at the application
boundary. For example, after connecting the device and building `joints`:

```python
try:
    if not hand.move_joints(joints):
        print("Joint command was not sent")
except RuntimeError as exc:
    print(f"Device operation failed: {exc}")
```

Communication exceptions from `move_joints()` propagate to the caller; depending
on the transport, these can also include I/O or timeout exceptions. A successful
return indicates command transmission, not completed motion. Read
`get_hand_info()` and `get_joints()` to confirm device state.

SDK 3.1.0 removed `get_last_result()`, `get_diagnostics()`, `OperationResult`,
`SdkError`, and `Diagnostics`. Use API return values, exceptions, device feedback,
and [SDK logging](logging.md) for diagnostics.

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
