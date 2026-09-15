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
