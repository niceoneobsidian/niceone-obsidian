# Adoption Readiness Evidence

Updated after repository hardening PR #136.

| # | Gate | Status | Evidence / next action |
|---|---|---|---|
| 1 | Full-history secret scan | PENDING EXECUTION | `.github/workflows/gitleaks.yml` uses `fetch-depth: 0`; run the workflow manually and retain the successful full-history result. |
| 2 | Immutable GitHub Actions pins | IMPLEMENTED | All inspected workflow action references use full commit SHAs on this branch. |
| 3 | Dependency lockfile | IN PROGRESS | Added `.github/workflows/dependency-lock.yml`; manually dispatch it with `write_lock=true` to generate and commit `uv.lock`. uv 0.12.17 is pinned in the lock-generation workflow. |
| 4 | Crash recovery / fault injection | PARTIAL | Existing PostgreSQL rollback, stale-outbox recovery, and recovery-policy tests are present. A real injected DB/network fault run in a staging environment is still required. |
| 5 | Persistence concurrency / idempotency | IMPLEMENTED AT TEST LEVEL | Existing PostgreSQL tests cover concurrent idempotency claims, atomic outbox staging, exclusive outbox claims, replay suppression, and transaction rollback. |
| 6 | Database-level fencing / state-transition protection | GAP | PostgreSQL execution state has row locking and application transition validation, but there is no worker lease/epoch/fencing contract in the PostgreSQL schema or runtime yet. |
| 7 | SBOM + attestation execution | WORKFLOW READY | SBOM generation, artifact upload, and source-archive provenance attestation are configured. A successful manual workflow run and artifact/attestation inspection are still required. |
| 8 | Deployment / rollback verification | PARTIAL | Versioned deployment, canary rollback, approval, and evidence controls have automated tests. Real staging/production deployment and rollback evidence remains environment-specific. |
| 9 | Mac runner validation | PENDING EXECUTION | Mac-only diagnostic workflows are present and general CI remains on `ubuntu-latest`. Dispatch the diagnostic on the Mac runner and retain its successful output. |

## Current branch

`chore/adoption-readiness-hardening`

This branch is intentionally limited to evidence-enabling CI hardening and verification workflows. It does not claim production readiness where external infrastructure or credentials are required.
