# Phase D — Durable Autonomous Execution

Phase D turns Phase C autonomous operations into a restart-safe execution system.

## D1 — Durable workflow runs
Workflow runs are persisted in PostgreSQL with tenant/workspace scope, checkpoints, deterministic idempotency keys, and explicit durable statuses.

## D2 — Worker ownership
Workflow-run mutations are protected by PostgreSQL worker leases and monotonically increasing epochs. A stale worker cannot mutate a run after another worker takes ownership.

## D3 — Checkpoint and recovery
Running/recovering executions heartbeat through durable transitions. A SKIP LOCKED sweeper detects abandoned runs, increments recovery counters, and moves them back into the recovery state. Checkpoints are the resume boundary.

## D4 — Side-effect safety
The side-effect ledger makes an idempotency key unique and records the request/result lifecycle. Repeated preparation returns the existing ledger entry instead of creating a second effect.

## D5 — Durable approvals
Approval state, expiry, actor attribution, and the original event payload survive process restart. Approval resume is fenced by the current worker epoch.

## D6 — Unified durable execution
DurableAutonomousExecutionEngine joins workflow matching, policy evaluation, persistent runs, worker fencing, approval gates, recovery state, and side-effect preparation.

The engine deliberately does not call provider APIs. The final capability/action callback is owned by the OIS Kernel boundary.

## Safety invariants

1. Tenant/workspace scope is preserved.
2. A workflow event has one durable idempotency identity.
3. Only the current worker epoch may mutate an owned run.
4. Checkpoints precede recovery/resume.
5. Side effects require unique idempotency keys.
6. Approval expiry is enforced by the persistent store.
7. Approved events retain their original source and payload.
8. Recovery is bounded.
9. Provider API invocation remains outside the autonomy layer.
