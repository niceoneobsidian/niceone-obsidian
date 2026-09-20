# Migrations and recovery

## Migration principles

- Every migration is reviewed as an operational change.
- Migrations must be idempotent where the repository contract requires replay.
- Destructive changes require an explicit backup and restore plan.
- Schema changes must preserve authorization, idempotency, state-transition, and evidence invariants.
- Migration output must not expose credentials or sensitive payloads.

## Local validation

Run the migration integration tests with disposable PostgreSQL resources:

```bash
pytest tests/integration/test_migrations.py -q
pytest tests/integration/test_migration_idempotency.py -q
```

Use the current repository test names if they change. Never validate migrations against production first.

## Recovery model

The execution state machine is authoritative for legal transitions. Recovery must make a bounded decision: retry, rollback, replan, or escalate. It must not loop indefinitely or silently change terminal state.

A recovery implementation should record:

- Execution identity and attempt number.
- Previous and next state.
- Authorization and capability version.
- Failure classification.
- Recovery decision and reason.
- Idempotency key or duplicate-detection result.
- Evidence append result.
- Operator or automated policy decision.

## Incident recovery

When persistence or evidence writes fail, fail closed for consequential actions, preserve the original failure, and follow [the rollback guide](rollback.md). Do not delete or rewrite evidence to make a recovery appear successful.
