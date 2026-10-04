# Phase B — Source Fabric

Phase B turns authenticated provider adapters into one governed, lifecycle-aware
source fabric. It composes the existing API Source Socket and Source Gateway;
it does not create a parallel persistence or authentication stack.

## Builds 7–14

| Build | Capability | Boundary |
|---|---|---|
| 7 | Source Registry & Lifecycle | tenant/workspace-scoped registration, enable/pause/degrade/disable |
| 8 | Polling & Scheduling | bounded concurrent polling with interval scheduling |
| 9 | Webhook/Event Ingestion | verified webhook delivery through SourceGateway |
| 10 | Cursor/Incremental Sync | versioned tenant-scoped checkpoints |
| 11 | Rate Limits + Retry/Backoff | token admission plus bounded exponential retry |
| 12 | Evidence + Provenance | immutable raw evidence with request/source provenance |
| 13 | Health + Observability | latency, failure streaks, health state and lifecycle degradation |
| 14 | Unified Source Fabric | one orchestration surface over all of the above |

## Runtime path

```text
Control Plane
     |
     v
Source Registry / Lifecycle
     |
     v
Unified Source Fabric
     |
     +--------------------+
     |                    |
     v                    v
Polling Scheduler      Webhook Gateway
     |                    |
     +---------+----------+
               |
               v
        Source API Socket
               |
               v
          Source Adapter
               |
               v
         Source Gateway
          /    |     \\
         v     v      v
   Rate Limit  Auth  Idempotency
               |
               v
      Raw Evidence + Outbox
               |
               +--> Provenance
               +--> Cursor checkpoint
               +--> Health telemetry
```

## Build 7 — Source Registry & Lifecycle

Every source is identified by `(tenant_id, workspace_id, source_id)`. The registry
stores provider, acquisition mode, configuration, credential reference, polling
interval, capabilities, and explicit lifecycle state.

Lifecycle transitions are constrained:

```text
REGISTERED -> ENABLED -> PAUSED
                    \-> DEGRADED -> ENABLED
                    \-> DISABLED
PAUSED -------------> ENABLED
PAUSED -------------> DISABLED
DEGRADED -----------> PAUSED / DISABLED
DISABLED -----------> REGISTERED
```

Credential material never belongs in the registry record.

Production uses the PostgreSQL registry boundary. SQLite remains the deterministic
reference implementation used by tests.

## Build 8 — Polling & Scheduling

`PollingEngine` owns bounded concurrency and scheduling. A polling adapter owns
its cursor semantics. The scheduler never mutates a cursor directly.

A failed poll is observable and can be retried by `SourceFabric.poll_with_retry`
using a bounded exponential backoff policy.

## Build 9 — Webhook/Event Ingestion

`WebhookGateway` enforces:

1. bounded request size,
2. timestamp freshness,
3. HMAC-SHA256 verification,
4. replay/delivery-key protection,
5. JSON parsing only after security admission,
6. SourceGateway durable acceptance.

A failed durable write releases the replay reservation so the provider can retry.

## Build 10 — Cursor / Incremental Sync

`SQLiteCursorStore` provides tenant/workspace/source scoped checkpoints with
optimistic version checks. A stale expected version is rejected instead of
silently overwriting another worker's checkpoint.

Production deployments should bind the same contract to PostgreSQL.

## Build 11 — Rate Limits + Retry / Backoff

Rate admission remains before idempotency consumption. `RateLimitManager` provides
tenant/workspace/source token buckets. `RetryController` provides bounded attempts,
exponential delay, a maximum delay, and controlled jitter.

The retry layer decides when to retry; the scheduler owns sleeping.

## Build 12 — Evidence + Provenance

Every accepted source observation crosses `SourceGateway`. The gateway creates:

- deterministic evidence identity,
- canonical SHA-256 payload hash,
- immutable raw evidence,
- durable outbox event,
- optional `SourceProvenance` containing provider, endpoint, operation,
  request ID, resource ID, cursor, and observation time.

No downstream component should bypass this acceptance boundary.

## Build 13 — Health + Observability

`SourceHealthRegistry` records:

- healthy/degraded state,
- check time,
- latency,
- consecutive failure count,
- latest error.

`SourceFabric` automatically moves an enabled source to `DEGRADED` after a
failed poll or health check, and restores it to `ENABLED` after a successful
operation.

## Build 14 — Unified Source Fabric

`SourceFabric` is the single application orchestration boundary for Phase B.
It coordinates registration, lifecycle, polling, webhook delivery, cursor
access, provenance-bearing observations, retries, and health state while keeping
credentials, evidence, and durable events inside their existing governed
boundaries.

## Security and reliability invariants

1. Authentication remains outside generic source adapters.
2. Tenant/workspace scope is preserved through every source-control and ingestion boundary.
3. Disabled and paused sources cannot execute through the fabric.
4. Polling checkpoints are advanced only by the cursor boundary.
5. Webhooks are rejected before JSON parsing when security admission fails.
6. Rate admission occurs before idempotency claims.
7. Raw evidence and outbox publication remain the durable acceptance boundary.
8. Provenance never contains access tokens or client secrets.
9. Retry is bounded and cannot create an unbounded failure loop.
10. PostgreSQL is the production persistence target; SQLite implementations are reference/test boundaries.