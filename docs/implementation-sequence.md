# Implementation sequence

The repository is governed by one strictly ordered delivery sequence. The sequence is executable through [`config/phase-gates.json`](../config/phase-gates.json) and validated by [`scripts/validate_phase_gates.py`](../scripts/validate_phase_gates.py). The JSON manifest is the machine-readable source of truth for phase identity, order, status, exit evidence and required checks. This document explains the contract and must remain synchronized with that manifest.

## Promotion rules

1. Only one phase may be `active`.
2. Phase 1 was the initial active phase; it is now complete in the current manifest.
3. A phase must be marked `complete` before the next phase can become `active`.
4. All later phases remain `planned`; skipping ahead is invalid.
5. Every phase must provide exit evidence and named required checks.
6. A phase promotion is a reviewed pull request that updates the manifest, adds or updates its evidence, and keeps the validator green.
7. Architecture, issue closure, branch age, or a passing unit test cannot substitute for phase evidence.
8. Documentation must report the current manifest state; it must not independently declare a phase active or complete.

## Phase contract

| Phase | Name | Exit condition |
| ---: | --- | --- |
| 1 | Repository Integrity | Coherent tree, required automation, and integrity checks pass |
| 2 | Kernel Conformance | Kernel contracts and conformance suite pass |
| 3 | Recovery Conformance | Bounded recovery transitions and recovery suite pass |
| 4 | Real PostgreSQL + Redis | Real service integrations, migrations, transactions, and idempotency are evidenced |
| 5 | Supervisor + Agent + Tool E2E | Governed end-to-end execution and tool effects are evidenced |
| 6 | Security / Tenant Isolation | Authorization and cross-tenant isolation are enforced and tested |
| 7 | Observability | Traces, metrics, and logs correlate with execution evidence |
| 8 | Real External APIs | External contracts, credentials, and side effects are governed |
| 9 | Production Canary | Reversible canary and rollback evidence exists |
| 10 | Measured Optimization | Optimization is supported by measurements and regression bounds |
| 11 | Controlled Evolution | Versioned, reviewed, observable, and reversible change is enforced |

## Current state — synchronized to the manifest

| Phase | Name | Current manifest state |
| ---: | --- | --- |
| 1 | Repository Integrity | **Complete** |
| 2 | Kernel Conformance | **Active** |
| 3–11 | Subsequent phases | **Planned** |

Phase 2 is the only active phase. Phase 1 is complete. The previous prose claiming Phase 1 was still active was stale and contradicted the manifest; this revision corrects that drift. The manifest itself is unchanged by this documentation update.

## Cross-cutting security release blocker

The formal phase order remains strict: Phase 6 cannot be promoted before Phases 3–5. However, known tenant-isolation defects are production release blockers now and must be remediated in parallel with the ordered work. The sequence is not permission to deploy a multi-tenant system before Phase 6 evidence is complete.

In particular, the shared Kernel PostgreSQL idempotency and evidence adapters require tenant-scoped ownership and query boundaries, and the legacy credential resolver's ownerless mode is explicitly non-isolating. See [the source-to-control-to-test evidence map](architecture/ois-source-control-test-evidence-map.md) and [the tenant-isolation remediation plan](security/tenant-isolation-remediation-plan.md). Remediation work does not change the active phase or authorize skipping a gate.

## Evidence standard

Evidence must be reproducible from repository contents, CI results, integration/runtime results, security results, or deployment/rollback records. Documentation alone describes intent; it does not satisfy an exit gate. A test file's existence is not a passing test result. A passing contract validator is not a production-readiness certificate.

## Change control

Phase promotions must be narrow, reviewable pull requests against `main`. Do not merge unrelated feature branches solely because they are available. Superseded work remains candidate material until it is reconciled against the active phase contract. Any update to the phase manifest must update this document in the same reviewed change.
