# Subscription And Threading

Subscription callbacks are invoked from SDK-managed background threads and
should return quickly. Exceptions raised by callbacks are logged with traceback
and do not stop the subscription loop.

EtherCAT subscriptions dispatch each received frame at most once. CANFD and
RS485 polling subscriptions store the interval per subscriber and poll at the
smallest active interval. Removing the final subscriber stops the background
thread with a bounded join.

`close()` and `unsubscribe()` are idempotent user-facing lifecycle operations.
They signal background work to stop rather than relying on fixed sleeps.
