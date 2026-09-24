# OIS Kernel Hardening — Integration Status

## Implemented on branch

`feat/ois-kernel-production-integration`

- Hardened multi-tenant PostgreSQL state/evidence/DLQ/artifact schema.
- RLS SELECT and INSERT `WITH CHECK` isolation.
- Immutable UPDATE/DELETE triggers for evidence, DLQ and registry.
- Tenant-bound cryptographic promotion verification.
- Redis lease ownership token with monotonic fencing counter.
- Append-only evidence sequence with transaction-scoped advisory locking and event-hash chaining.
- LangGraph supervisor execution boundary with HITL interrupt; durable resume remains gated on a configured persistent checkpointer.
- Failure classification into recovery scenarios.
- Cryptographically sealed DLQ containment.
- Promotion negative tests for unsigned and cross-tenant-bound signatures.

## Corrections applied

1. The artifact registry now has `tenant_id`; the original policy referenced a missing column.
2. Tenant context is set through parameterized `set_config`, not SQL interpolation.
3. RLS write isolation uses `WITH CHECK`.
4. Promotion signatures bind tenant, workflow, version and provenance.
5. Recovery is classified rather than sending every exception to RC-04.
6. Evidence contains an ordered previous-hash chain.
7. Redis fencing tokens are monotonic, not merely random nonces.
8. Evidence sequence allocation is serialized per tenant/thread and stores a complete event hash.
9. Promotion verifies the canonical manifest hash before checking the promotion signature.
10. Production secrets are supplied externally; no production secret is embedded.
11. The implementation status does not claim staging or production verification from mocks.

## Verification boundary

The repository now contains implementation, but production activation remains gated by live evidence:

`Structure → Register → Contract → Audit → Evidence → Kernel → Activate`

Required next gates:

- Live PostgreSQL RLS adversarial test.
- Live Redis lease expiry/split-brain fencing test.
- Full RC-01 through RC-12 behavioural matrix.
- Configure and verify a persistent PostgreSQL checkpointer for restart-safe HITL resume.
- Checkpoint corruption/recovery tests against the actual checkpointer implementation.
- OpenTelemetry exporter/collector verification.
- Real artifact registration and signature provenance flow.
- CI execution and dependency compatibility verification.
- Least-privilege database role verification.
- Staging deployment and rollback evidence.

Architecture documents and existing repository foundations remain authoritative for the broader OIS system; this change specifically hardens the production kernel path without claiming unverified integrations are complete.
