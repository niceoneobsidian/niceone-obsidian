# Tenant Isolation Remediation Plan

**Severity:** Critical / P0 release blocker for multi-tenant production  
**Status:** Remediation plan; no source-code or database changes are included in this document-only change.

## Why this is P0

The inspected code has a tenant-scoped checkpoint store, but the separate Kernel PostgreSQL idempotency and evidence adapters are not equivalently tenant-scoped. The idempotency table is keyed by invocation ID without tenant ownership; the evidence ledger stores event/execution identity without tenant ownership and exposes list operations without a tenant predicate. The production composition wires these adapters beside a tenant-scoped checkpoint store, so the checkpoint boundary alone does not establish end-to-end tenant isolation.

The credential conformance suite explicitly documents a legacy resolver mode without owner metadata as a known cross-tenant credential-resolution gap. Production must use an owner-enforcing secret manager and must not enable that legacy mode.

## Work packages

### P0.1 — Define trusted tenant context
- Identify the authenticated principal/service boundary that supplies tenant identity.
- Bind tenant identity once at request admission; make it immutable for the invocation lifecycle.
- Do not accept tenant identity from LLM-generated plans, tool arguments or mutable metadata.
- Define fail-closed behavior for absent, malformed or conflicting tenant context.

**Exit evidence:** identity propagation contract, negative tests, and an explicit owner for the authentication-to-runtime handoff.

### P0.2 — Tenant-scope Kernel idempotency
- Add tenant ownership to idempotency schema and adapter protocol.
- Scope lookup, insert, replay and uniqueness to tenant plus invocation identity; assess whether workspace scope is also required by the contract.
- Add RLS/policy enforcement and indexes/constraints consistent with the tenancy model.
- Provide a migration/backfill plan for existing records. Never infer ownership from invocation ID alone.

**Exit evidence:** two-tenant tests prove same invocation identifier cannot expose or replay another tenant's result; direct SQL under the production role is also isolated.

### P0.3 — Tenant-scope evidence ledger
- Add tenant ownership to evidence schema and event model or trusted append context.
- Scope append, list, count and all retrieval/query paths to tenant.
- Preserve append-only semantics while enforcing tenant-scoped RLS.
- Ensure execution ID alone is never treated as authorization to enumerate evidence.

**Exit evidence:** cross-tenant evidence read/append/list/count tests fail closed; append-only and correlation tests remain green.

### P0.4 — Outbox, checkpoint and source-store consistency
- Audit all shared tables, including side-effect outbox, source gateway idempotency, approvals, correlation indexes and worker leases.
- Verify every adapter's tenant context and RLS policy, not only its Python query predicates.
- Ensure tenant/workspace scoping and uniqueness are consistent across stores.
- Verify connection pool reuse and transaction-local tenant reset.

**Exit evidence:** complete inventory of shared tables, policy DDL, grants, RLS tests and pool-reuse tests.

### P0.5 — Credential resolver closure
- Make strict ownership the only supported production path.
- Reject ownerless credentials and forged tenant references.
- Verify provider secret manager binds secret IDs to tenant/workspace ownership.
- Remove the legacy resolver from production composition; retain any compatibility mode only in isolated test fixtures if necessary.

**Exit evidence:** real secret-manager adapter tests, negative forged-reference test, and proof no production wiring uses the legacy resolver.

### P0.6 — Adversarial verification and migration safety
- Test Tenant A attempting Tenant B checkpoint, result, evidence, outbox, approval, source-idempotency and credential operations.
- Test missing tenant GUC, wrong tenant GUC, pooled connection reuse, concurrent replay, rollback and migration backfill.
- Include RLS bypass-role review; application tests alone are insufficient if the application role can bypass RLS.
- Rehearse migration and rollback on a production-equivalent PostgreSQL version and role.

**Exit evidence:** dated test run, migration checksum/version, DB version, application role, complete logs/artifacts, reviewer sign-off and unresolved-risk disposition.

## Release gates

- No multi-tenant production canary while any P0 work package is open.
- No claim of multi-tenant safe based solely on the tenant-scoped checkpoint store or a passing contract validator.
- No data deletion or ownership backfill by guesswork. Quarantine ambiguous legacy rows.
- The ordered phase manifest remains authoritative for formal promotion. Tenant remediation begins now as a release-blocking cross-cutting requirement; it does not authorize skipping prior phases.
- Production approval requires all P0 evidence plus security-owner review and a tested rollback/restore plan.

## Source and test anchors

- `ois/kernel/postgres.py` — tenant-scoped checkpoint store and transaction-local tenant context.
- `ois/kernel/postgres_stores.py` — shared Kernel idempotency and evidence adapters requiring tenant-scope remediation.
- `ois/kernel/tenant.py` — tenant normalization and transaction-local context helper.
- `ois/infrastructure/source_gateway/credentials.py` — credential reference ownership checks and legacy-mode caveat.
- `tests/integration/test_kernel_postgres_stores.py` — PostgreSQL adapter integration tests; extend with cross-tenant adversarial cases.
- `tests/integration/test_p0_4_4_rls_adversarial.py` — RLS adversarial test anchor; verify actual current coverage and CI result.
- `tests/integration_conformance/test_credential_resolver_conformance.py` — strict ownership and explicit legacy known-gap test.
- `docs/integrations/ocif-governed-execution.md` — existing statement that evidence/idempotency tenant isolation is a rollout blocker.

## Non-goals

This plan does not authorize schema changes, data migrations, production configuration changes, secret rotation, deployment, or removal of legacy data. Those require implementation review and a separate approved migration/change set.
