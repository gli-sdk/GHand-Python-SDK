# Diagnostics

`GHand.get_diagnostics()` returns a structured snapshot that can be consumed by
applications, tests, and field tooling without parsing log text.

```python
from ghand import CommType, GHand, ProductType

hand = GHand(ProductType.GHand5, CommType.ETHERCAT)
diag = hand.get_diagnostics()

print(diag.connection.connected)
print(diag.connection.comm_type)
print(diag.subscription.active_subscriptions)
print(diag.error.last_sdk_error)
print(diag.error.last_error_message)
```

## Fields

- `connection`: connection state, communication type, and device identifier.
- `identity`: configured product type and cached identity fields.
- `subscription`: active subscription count and frame counters where available.
- `error`: the latest SDK operation result code and message.
- `transport`: transport counter fields reserved for protocol instrumentation.

The diagnostics API is intentionally independent from logging. Logs are useful
for humans, while diagnostics are stable machine-readable state.

## Notes

For EtherCAT subscriptions, received and dispatched frame counts are reported
from the internal subscription manager. CAN-FD and RS-485 currently report the
active callback count; deeper packet, timeout, retry, and reconnect counters are
kept as zero until the protocol transports expose those measurements.
