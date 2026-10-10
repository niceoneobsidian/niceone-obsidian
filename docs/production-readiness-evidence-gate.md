# Production Readiness Evidence Gate

## Purpose

This gate turns the six readiness requirements into explicit, reproducible checks. It is a release gate, not a declaration that the repository is already production-ready. A green workflow is necessary but not sufficient: staging evidence and live GitHub administration settings remain external controls.

## Automated evidence

The `.github/workflows/production-readiness-evidence.yml` workflow runs on pull requests to `main`, pushes to `main`, and manual dispatch.

| Gate | Automated evidence | Pass condition |
|---|---|---|
| Security and credentials | Full-history Gitleaks scan; Bandit; locked dependencies | No unexplained secret findings; no unresolved blocking security-lint findings. Any historical finding is investigated and genuine credentials are revoked/rotated. |
| Required CI | Ruff lint and format, mypy, full pytest suite | Every job passes on the candidate commit. |
| Interfaces and dependency boundaries | Type checks and full suite | No ignored failure. Add/extend contract tests whenever a provider, registry, policy, secret, or execution boundary changes. |
| Durable execution and recovery | PostgreSQL service plus tests marked `integration` and the PostgreSQL side-effect suite | Transaction, idempotency, outbox, restart/recovery and failure cases pass against PostgreSQL, not only an in-memory fake. |
| Representative end-to-end workflow | Existing repository suite must cover the governed execution vertical slice | Demonstrate objective/intent → policy/authorization → capability selection → execution → validation → persisted evidence and terminal state. If this path is not exercised by tests, the gate is not satisfied by unit tests alone. |
| Deployment, observability and rollback | Contract-document checks in CI; manual staging evidence below | Automated documentation checks do not count as a deployment. Staging deploy, telemetry inspection, recovery drill and rollback must be run and recorded separately. |

## Security response protocol

1. Review every Gitleaks finding, including findings in historical commits and example/config files.
2. Treat a detector hit as an unverified finding, not proof that a credential is live.
3. If a real credential was committed, revoke/rotate it at the issuing provider, remove the exposed value from active files/history as appropriate, and record the incident/remediation without copying the secret into this document or a PR comment.
4. Keep narrowly scoped, documented false-positive allowlists only after review. Never globally disable a detector or allowlist a broad path merely to turn CI green.
5. Verify GitHub secret scanning and push protection in repository settings; repository code cannot prove these settings are enabled.

## Required staging evidence (manual, environment-specific)

Attach sanitized links or artifacts for the target release commit:

- [ ] Build provenance: source commit, immutable artifact digest, lockfile identifier and SBOM.
- [ ] Migration rehearsal: clean database upgrade, repeatability/compatibility check, backup/restore result and documented rollback constraints.
- [ ] Deploy to a non-production environment using the release procedure.
- [ ] Readiness/liveness and dependency health pass after deploy.
- [ ] One representative workflow completes and produces correlated execution/evidence IDs.
- [ ] Failure injection: terminate a worker during processing, interrupt database connectivity, and verify bounded retries/recovery without unauthorized or duplicate external effects.
- [ ] Observability: inspect traces, metrics and structured logs for a run; verify correlation and ensure no secret values or unnecessary personal data are emitted.
- [ ] Rollback to a previously verified immutable artifact; re-run health and workflow checks. State explicitly whether the database schema is backward compatible.
- [ ] Record operator, timestamp, environment, commit, artifact digest, results, exceptions and evidence URLs.

Do not run destructive failure injection or rollback against production without a tested recovery plan and explicit authorization. Use disposable staging data and non-production credentials.

## Current evidence status

This file records the acceptance contract, not completed runs. Until the workflow has run successfully on the candidate commit and staging evidence above is attached, the status remains **NOT PRODUCTION VERIFIED**. A green CI run alone cannot establish live deployment, credential rotation, repository settings, or rollback success.

## Release decision

Promote only when all automated jobs are green, all secret findings are resolved or narrowly explained, the representative end-to-end path passes, and staging deployment/recovery/rollback evidence has been reviewed. Any skipped or unavailable required check is a blocker, not a pass.
