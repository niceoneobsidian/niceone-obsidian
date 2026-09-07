# P0.4.4–P0.4.6 Runtime Conformance

## Implemented

### P0.4.4 — Tenant/RLS isolation

- `migrations/002_tenant_rls.sql` enables and **FORCE**s PostgreSQL row-level security on durable execution, idempotency, and side-effect-outbox tables.
- Tenant identity is bound with `set_config(..., true)` so the PostgreSQL setting is transaction-local.
- `PostgresDurableExecutionStore` can be constructed with a tenant scope and binds that scope before every transaction.
- `create_tenant_pool()` installs a connection reset hook to remove sticky session state before a pooled connection is reused.
- The adversarial suite covers cross-tenant reads, cross-tenant writes, parameterized injection payloads, and pool pollution.

### P0.4.5 — Worker crash recovery

- Redis Streams consumer groups provide durable pending-entry tracking.
- Normal processing ACKs only after the handler completes successfully.
- Recovery uses `XAUTOCLAIM` to atomically transfer stale pending entries to a recovery consumer.
- Recovered work is ACKed and deleted only after successful handler completion.
- Delivery is explicitly **at-least-once**; external side effects must remain idempotent through the existing OIS idempotency boundary.

### P0.4.6 — gVisor runtime conformance

- Sandbox conformance checks require an explicitly declared gVisor runtime or a gVisor kernel signature.
- Raw packet socket creation and root filesystem remount attempts must be denied.
- Kubernetes sandbox contract disables privilege escalation, privileged mode, service-account token mounting, host namespaces, all Linux capabilities, and uses `RuntimeDefault` seccomp.
- Sandbox egress/ingress is deny-by-default in the supplied NetworkPolicy.

## Verification status

**Implemented:** code, migration, tests, CI wiring, and Kubernetes contract.

**CI-verifiable:** PostgreSQL and Redis suites when the GitHub service containers are available.

**Environment-dependent:** gVisor conformance requires a real gVisor-backed Linux runner. The suite is intentionally not treated as passing merely because the test process can set an environment variable.

**Production gate remaining:** run the migration with the production database role model, prove that application roles do not own protected tables, execute live PostgreSQL/Redis tests, and execute the sandbox suite on the actual gVisor runtime. Only then should P0.4.4–P0.4.6 be promoted from IMPLEMENTED to VERIFIED/PRODUCTION-READY.
