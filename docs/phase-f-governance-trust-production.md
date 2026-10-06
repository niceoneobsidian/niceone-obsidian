# Phase F — OIS Governance, Trust & Production Control

Phase F places a fail-closed trust boundary around autonomous execution. Phase D durable
execution remains the system of record for execution state; Phase E planning remains the
source of plans. Governance decides whether an identified agent may perform a capability
action and records why.

## Control model

`identity → tenant boundary → capability grant → policy/version → action limits/budget →
decision provenance → audit → durable execution`

The governance layer never executes a capability directly.

## Implemented controls

- Explainability: every authorization decision has a rationale and deterministic input digest.
- Decision provenance: decision records bind tenant, workspace, execution, actor, action, capability,
  policy version fields, outcome, and rationale.
- Audit trails: allow/deny decisions emit immutable-style audit records.
- Policy versioning: policy records are tenant-scoped and content-hashed.
- Agent identity: agents are explicitly identified, tenant-scoped, role-bound, and enable/disableable.
- Capability authorization: grants are tenant + agent + capability scoped and may expire.
- Tenant isolation: PostgreSQL RLS is enabled on Phase F tables.
- Security boundaries: missing identity/grant/limit/budget fails closed.
- Budget controls: estimated action cost is checked before authorization.
- Autonomous-action limits: per-tenant/action bounded counters prevent unlimited autonomous actions.
- Compliance evidence: evidence records carry control IDs and content digests.
- SLO/SLI definitions: tenant-scoped SLO records provide durable metric targets.

## Production control

Production deployment must apply migrations through the repository migration process,
not application startup. Rollback uses the previously verified immutable application artifact;
database rollback is a separate, explicitly reviewed migration operation.

Disaster recovery requires PostgreSQL backups, restore verification, and recovery evidence.
Production promotion should require passing repository tests, security scans, migration checks,
and an evidence bundle covering authorization, tenant isolation, durable execution, and rollback.

## Operational dashboard contract

The production dashboard should expose, at minimum:

- execution success/failure rate
- authorization allow/deny rate
- policy decision latency
- stale-worker/fencing rejections
- recovery/replan rate
- approval wait time
- budget consumption
- action-limit rejections
- tenant-isolation violations
- SLO attainment

Each metric must carry tenant, execution, and correlation dimensions where applicable.

## Red-team / fault-injection gates

The Phase F conformance suite must exercise:

1. cross-tenant identity and capability grant rejection;
2. missing/expired grants;
3. action-limit exhaustion;
4. budget exhaustion;
5. policy-version mismatch;
6. audit/provenance correlation;
7. stale worker attempting a governed mutation;
8. crash after authorization but before durable execution;
9. crash after side-effect completion;
10. restore-from-backup verification before production promotion.

Phase F is complete only when these controls are backed by executable tests and deployment
evidence, not documentation alone.
