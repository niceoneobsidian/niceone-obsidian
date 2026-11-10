# OIS Source-to-Control-to-Test Evidence Map

**Status:** Audit baseline; source mappings inspected, test execution not performed in this documentation change.  
**Repository:** `niceoneobsidian/niceone-obsidian`  
**Branch baseline:** `main` at review time.  
**Purpose:** Trace each material OIS control from authoritative source to enforcement mechanism to test evidence and remaining proof required.

## Evidence semantics

- **Source present** means the named implementation or contract exists in the inspected repository.
- **Test present** means a relevant test file or test case exists; it does not mean the test passed in this review.
- **Integrated** is a repository-declared maturity label, not proof of deployment.
- **Runtime / deployment verified** requires dated evidence from the target environment.
- A missing mapping is a gap; it is not evidence that the control is absent everywhere.

## Control traceability

| Control / risk | Authoritative source | Enforcement point | Test evidence / target | Current evidence state | Required closure evidence |
|---|---|---|---|---|---|
| Trusted tenant identity | `ois/kernel/tenant.py`; `ois/kernel/state.py`; `ois/kernel/contracts.py` | UUID normalization; trusted execution identity; transaction-local tenant context | `tests/integration/test_p0_4_4_rls_adversarial.py`; policy and tenant conformance suites | Source anchors exist; exact latest CI result not independently verified here | Tests proving missing, malformed, forged and mismatched tenant identity fail closed |
| Policy authorization | `ois/kernel/policy.py`; `ois/kernel/runtime.py` | Capability permission, tenant, risk and irreversible-side-effect checks before invocation | Kernel policy/conformance tests; `tests/integration/test_p0_4_4_rls_adversarial.py` | Source and test anchors identified; no fresh test execution | Denial tests assert capability was not invoked and denial evidence is persisted |
| Durable execution tenant scope | `ois/kernel/postgres.py`; `ois/kernel/tenant.py` | Tenant-scoped store sets `app.current_tenant_id` transaction-locally; store checks execution/command tenant | `tests/integration/test_p0_4_4_rls_adversarial.py`; PostgreSQL durable execution tests | Stronger control pattern exists for checkpoint store; deployment RLS posture still requires target-DB proof | Migration inspection, RLS enabled/forced where appropriate, role tests, pool/transaction reset tests, cross-tenant read/write denial |
| Kernel idempotency | `ois/kernel/postgres_stores.py` | `PostgresIdempotencyStore` currently keys results by invocation ID only; no tenant column or tenant-scoped transaction in this adapter | `tests/integration/test_kernel_postgres_stores.py` | Critical design gap: shared adapter is not tenant-isolated by its own interface/schema | Tenant-aware composite key and scope checks; RLS/policy; collision and cross-tenant replay tests |
| Kernel evidence ledger | `ois/kernel/postgres_stores.py` | `PostgresEvidenceLedger` currently stores execution/event IDs without tenant ownership or tenant-scoped query boundary | `tests/integration/test_kernel_postgres_stores.py` | Critical design gap: list/query boundary is execution-ID-only and not tenant-scoped | Tenant ownership in schema, tenant-scoped append/read, RLS, forged execution-ID denial and append-only cross-tenant tests |
| Source-gateway idempotency | `ois/infrastructure/source_gateway/idempotency.py` | API methods accept tenant/workspace IDs; PostgreSQL statements filter by both; schema/migration and connection role remain decisive | Source gateway idempotency tests and PostgreSQL integration tests (locate/verify before closure) | Application predicates exist; independent DB enforcement and caller binding need verification | Schema composite uniqueness, RLS, authenticated tenant context, forged tenant/workspace tests |
| Credential ownership | `ois/infrastructure/source_gateway/credentials.py` | Strict resolver checks reference tenant and stored credential owner; production secret manager must enforce ownership | `tests/integration_conformance/test_credential_resolver_conformance.py`, including `test_legacy_unowned_resolver_is_not_tenant_isolating_known_gap` | Explicit known gap remains for legacy resolver without owner metadata | Remove/disable legacy resolver in production composition; secret-manager ownership test against real adapter; cross-tenant forged-reference denial |
| Approval identity and single use | OIS approval/control-plane contracts and OPI acceptance record | Bind approval to tenant + exact plan/task/action; atomically consume once | OPI task “Verify PostgreSQL-backed approval identity and single-use consumption” | Notion task was Backlog in prior audit; implementation/test evidence not established | PostgreSQL race/replay/expiry/mismatched-action tests and persisted audit evidence |
| Correlation and recovery | `ois/integration/spine.py`; `ois/integration/durable_runtime.py`; `ois/kernel/recovery.py`; `ois/kernel/postgres.py` | Stable invocation/execution/correlation IDs; checkpoint history and bounded recovery | `tests/integration/test_kernel_postgres_stores.py`; recovery conformance and OPI crash-recovery task | Source and test anchors exist; full multi-process/runtime evidence not independently verified | Process-kill/restart, corrupted checkpoint, duplicate worker, stale lease and replay tests with retained outputs |
| Side-effect authorization and outbox | `ois/kernel/runtime.py`; `ois/kernel/postgres.py` | Policy before invocation; transactional outbox; stable downstream idempotency key | PostgreSQL side-effect and runtime integration tests | Documented implementation; production provider semantics remain external | Denial-no-effect tests, crash-after-effect-before-ack test, provider idempotency contract and reconciliation evidence |
| Observability / audit integrity | `ois/kernel/evidence.py`; `ois/kernel/postgres_stores.py`; `docs/capability-evidence-matrix.md` | Append-only events and correlation fields | Evidence ledger tests; observability contract tests | Capability matrix declares partial observability; evidence adapter has tenant gap | Tenant-scoped query tests, trace/metric/log correlation assertions, tamper/retention controls |
| Production release gates | `config/phase-gates.json`; `scripts/validate_phase_gates.py`; `.github/workflows/phase-gates.yml` | Strict ordered phase manifest and CI validator | `tests/governance/test_phase_gates.py` | Manifest says Phase 2 active; human sequence doc was stale before this change | Green validator/workflow on reviewed PR and explicit evidence bundle for each promotion |

## Priority remediation order

1. **P0 — Close tenant isolation in shared kernel stores.** Add tenant ownership to idempotency and evidence records, bind tenant identity from trusted execution context (not caller-supplied metadata), enforce tenant-scoped reads/writes and database RLS/policies, and migrate existing rows safely.
2. **P0 — Close credential ownership gap.** Production must reject ownerless credentials and must not compose the legacy non-isolating resolver. Verify the actual secret manager, not only the in-memory test double.
3. **P0 — Verify tenant enforcement end-to-end.** Add adversarial PostgreSQL tests for cross-tenant read, write, replay, evidence enumeration, credential reference forgery, connection-pool reuse and transaction-context leakage.
4. **P1 — Close approval/replay/recovery invariants.** Approval must bind to exact action identity and be single-use; replay, crash recovery and worker fencing must be verified across process boundaries.
5. **P1 — Close observability and deployment proof.** Correlate authorization, execution, evidence and side-effect outcomes; verify migrations, roles, backup/restore and rollback on target infrastructure.

## Tenant-isolation acceptance criteria

- Tenant identity originates from a trusted authenticated principal or trusted service boundary; model output and arbitrary payload fields cannot assign it.
- Every shared persistence adapter accepts an explicit immutable tenant scope or derives it from a trusted execution context.
- Reads, writes, list/count operations, uniqueness constraints and replay lookups are tenant-scoped.
- PostgreSQL RLS is enabled and validated for the production application role; tests demonstrate that missing tenant context denies access.
- Connection pooling cannot leak a previous tenant context; transaction-local settings are cleared at transaction end and verified under pool reuse.
- Cross-tenant access attempts are denied for checkpoints, idempotency results, evidence, outbox records, source idempotency and credentials.
- Existing records are backfilled with verified ownership; ambiguous rows are quarantined, not guessed.
- Migration is reversible or has a documented restore strategy; no destructive cleanup before reconciliation.
- All adversarial tests pass against the target PostgreSQL version and production-equivalent role configuration.
- Evidence bundle records commit SHA, migration version, DB version/role, test command, result, timestamp and reviewer.

## Release interpretation

Tenant-isolation is a **production release blocker now**, even though the formal ordered manifest places the Security / Tenant Isolation phase after earlier integration phases. Preparatory remediation and adversarial tests should begin immediately. The formal phase cannot be promoted out of order; production approval must remain denied until the tenant boundary is verified.

## Scope and limitations

This is a source-backed mapping based on repository files and existing test anchors. It is not a fresh CI run, penetration test, database migration, deployment test or independent security certification. It deliberately does not mark any test as passing unless a dated result is linked.
