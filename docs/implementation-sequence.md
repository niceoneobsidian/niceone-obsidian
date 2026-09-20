# Implementation sequence

The repository is governed by one strictly ordered delivery sequence. The sequence is executable through [`config/phase-gates.json`](../config/phase-gates.json) and validated by [`scripts/validate_phase_gates.py`](../scripts/validate_phase_gates.py).

## Promotion rules

1. Only one phase may be `active`.
2. Phase 1 starts as the active phase.
3. A phase must be marked `complete` before the next phase can become `active`.
4. All later phases remain `planned`; skipping ahead is invalid.
5. Every phase must provide exit evidence and named required checks.
6. A phase promotion is a reviewed pull request that updates the manifest, adds or updates its evidence, and keeps the validator green.
7. Architecture, issue closure, branch age, or a passing unit test cannot substitute for phase evidence.

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

## Current state

**Phase 1: Repository Integrity is active.** No later phase is authorized to be represented as complete or active until the preceding phase has been promoted through the manifest.

## Evidence standard

Evidence must be reproducible from repository contents, CI results, integration/runtime results, security results, or deployment/rollback records. Documentation alone describes intent; it does not satisfy an exit gate.

## Change control

Phase promotions must be narrow, reviewable pull requests against `main`. Do not merge unrelated feature branches solely because they are available. Superseded work remains candidate material until it is reconciled against the active phase contract.
