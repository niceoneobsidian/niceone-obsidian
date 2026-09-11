# DE-03 durable execution invariants

DE-03 makes PostgreSQL the shared coordination substrate for durable execution.

## Guarantees

- A live execution has one current worker owner.
- Ownership is represented by a monotonically increasing `lease_epoch`.
- Every fenced runtime mutation validates execution ID, worker ID, epoch, active state, and expiry.
- Expired workers cannot mutate state after another worker takes ownership.
- Checkpoint persistence is fenced by the lease row lock and current epoch.
- Completion persistence is fenced through the same checkpoint boundary.
- Completed invocation results use first-writer-wins persistence keyed by logical invocation ID and carry worker fencing metadata.
- Side-effect outbox claim and completion can be fenced by `PostgreSQLSideEffectFencer`.
- Fencing rejection is recorded as `execution.fencing_rejected` evidence with worker and epoch metadata.
- Checkpoints survive process restart and retain a durable revision.
- A worker crash before completion leaves the execution recoverable after lease expiry.

## Verification matrix

| Gate | Implementation | Verification |
| --- | --- | --- |
| Fenced checkpoint write | `PostgreSQLCheckpointStore.save_fenced()` | stale-worker checkpoint test |
| Fenced completion | `PostgreSQLCheckpointStore.complete_fenced()` | runtime completion path |
| Fenced idempotency | `PostgreSQLIdempotencyStore.put_fenced()` | stale-worker idempotency test |
| Fenced side-effect completion | `PostgreSQLSideEffectFencer.complete()` | stale side-effect rejection test |
| Stale-worker mutation | epoch/lease row lock | stale-worker checkpoint/idempotency tests |
| Concurrent takeover | serialized initial claim + `FOR UPDATE` | concurrent claim test |
| Crash/recovery | checkpoint + epoch N→N+1 | recovery test |
| Fencing evidence | `execution.fencing_rejected` | evidence test |

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

## PostgreSQL concurrency basis

Lease acquisition uses a unique execution key plus row locking so concurrent first claims serialize before ownership is evaluated. Fenced durable mutations hold the current lease row lock while committing their mutation. This follows PostgreSQL's documented row-locking and `ON CONFLICT` concurrency semantics.

The production activation gate remains separate: CI evidence proves repository conformance; it does not itself authorize production deployment.
