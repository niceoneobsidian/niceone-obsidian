# Rollback guide

Rollback is a controlled change, not an assumption that every database change can be reversed. Prefer forward-compatible migrations and an explicit recovery plan.

## Rollback triggers

Consider rollback or traffic withdrawal when there is:

- Unauthorized or unexpected external activity.
- Evidence corruption or inability to append evidence.
- Invalid persisted state transitions.
- Material increase in failed executions or recovery loops.
- Data loss, migration failure, or irreconcilable schema mismatch.
- Health or readiness failure after deployment.

## Procedure

1. Declare the incident and record the deployed commit.
2. Stop new consequential executions or place the system in a safe drain mode.
3. Preserve logs, traces, database evidence, and configuration metadata.
4. Decide between application rollback, traffic withdrawal, or forward fix.
5. Do not blindly reverse migrations that may destroy data.
6. Restore the last known-good application version only if its schema contract remains compatible.
7. If data repair is required, use a reviewed, append-only repair process with a recorded authorization.
8. Verify health, readiness, authorization, idempotency, state transitions, and evidence integrity.
9. Re-enable traffic gradually and monitor recovery metrics.
10. Document impact, cause, actions, and follow-up tests.

## Recovery invariants

- No retry may create an unbounded side effect.
- Duplicate delivery must remain safe.
- Evidence must not be silently rewritten.
- Terminal states must not be reopened without an explicit, audited recovery path.
- Operators must be able to identify what was attempted, authorized, executed, validated, and recovered.
