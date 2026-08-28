# DE-03 durable execution invariants

DE-03 makes PostgreSQL the shared coordination substrate for durable execution.

## Guarantees

- A live execution has one current worker owner.
- Ownership is represented by a monotonically increasing `lease_epoch`.
- Every fenced runtime mutation validates execution ID, worker ID, epoch, active state, and expiry.
- An expired worker cannot mutate state after another worker takes ownership.
- Completed invocation results use first-writer-wins persistence keyed by logical invocation ID.
- Checkpoints survive process restart and retain a durable revision.
- A worker crash before completion leaves the execution recoverable after lease expiry.

## Deliberate boundary

Fencing prevents stale workers from corrupting durable OIS state. It cannot make an arbitrary external side effect exactly-once by itself. External capabilities must use the stable invocation ID (or an equivalent provider-side idempotency key) when their side effects require exactly-once behavior.

## Recovery sequence

1. Worker A claims execution `E` at epoch `N`.
2. A checkpoints progress and begins a task.
3. A crashes or loses its lease.
4. The lease expires.
5. Worker B claims `E` at epoch `N+1`.
6. B restores the checkpoint and retries only incomplete work.
7. Any stale write from A is rejected by the epoch fence.
8. A terminal result is persisted once under the logical invocation ID.

The production activation gate remains separate: CI evidence proves repository conformance; it does not itself authorize production deployment.