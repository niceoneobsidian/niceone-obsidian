# OIS Durable Execution v1 — PostgreSQL

This branch promotes Durable Execution v1 from the local SQLite reference backend to the production persistence model specified for OIS.

## Persistence model

- PostgreSQL is the authoritative execution-state store.
- Redis remains coordination/cache infrastructure; it is not the execution source of truth.
- Execution checkpoints contain canonical JSON state plus a SHA-256 integrity hash.
- Terminal invocation results are persisted with `INSERT ... ON CONFLICT DO NOTHING`.
- Failed/interrupted invocations are not recorded as successful idempotent completions.

## Side-effect boundary

Consequential operations use a transactional outbox:

```text
Policy / authorization
        ↓
Execution state + side-effect intent
        ↓
ONE PostgreSQL transaction
        ↓
Outbox committed
        ↓
Worker claims intent
        ↓
External system receives the SAME idempotency key
        ↓
Validate result
        ↓
Mark outbox completed
```

A worker crash after the external operation but before acknowledgement can cause redelivery. The same idempotency key is therefore mandatory at the external provider boundary. OIS does **not** claim exactly-once external effects when the downstream provider does not support idempotency.

## Recovery

Outbox rows are leased through `locked_at`. Stale `PROCESSING` rows are eligible for recovery after five minutes. `FOR UPDATE SKIP LOCKED` allows multiple workers to claim work without duplicate database claims.

## Bootstrap

Production deployments should apply `migrations/001_durable_execution.sql` through the normal migration system. `PostgresDurableExecutionStore.initialize()` is provided for development/test bootstrap.

Set `OIS_POSTGRES_TEST_DSN` to run the PostgreSQL integration tests:

```bash
OIS_POSTGRES_TEST_DSN='postgresql://...' pytest test_durable_postgres_side_effects.py -q
```

## Production gate

This implementation is **implemented but not production-verified** until the PostgreSQL integration suite, local OIS CI, failure-injection tests, and deployment migration have all passed against the target PostgreSQL version.
