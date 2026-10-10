# Production Readiness Evidence Gate

## Purpose

This gate turns the readiness requirements into explicit, reproducible checks. It is a release gate, not a declaration that the repository is already production-ready. A green workflow is necessary but not sufficient: staging evidence and live GitHub administration settings remain external controls.

The captured pre-gate baseline and its known failures are documented in [production-readiness-baseline.md](production-readiness-baseline.md). In particular, the baseline's full-history Gitleaks scan fails on seven credential-shaped findings in a historical `.env.example`; these remain blockers until verified and dispositioned without exposing values.

## Automated evidence

The `.github/workflows/production-readiness-evidence.yml` workflow runs on pull requests to `main`, pushes to `main`, and manual dispatch.

| Gate | Automated evidence | Pass condition |
|---|---|---|
| Dependency reproducibility | `uv lock --check` and `uv sync --locked` | Lockfile matches project metadata and the locked environment installs cleanly. |
| Security and credentials | Full-history Gitleaks scan; Bandit; dependency scan | No unexplained secret findings; no unresolved blocking security-lint findings. Any historical finding is investigated and genuine credentials are revoked/rotated. |
| Required CI | Ruff lint and format, mypy, full pytest suite | Every required job passes on the candidate commit. |
| Migration integrity | Explicit governance test plus real PostgreSQL migration integration tests | Migration filenames are valid, versions are unique and contiguous, files are non-empty, all migrations apply, and the migration history/checksums are consistent. |
| Interfaces and dependency boundaries | Type checks, focused governed vertical-slice tests, and full suite | No ignored failure. Extend contract tests whenever a provider, registry, policy, secret, or execution boundary changes. |
| Durable execution and recovery | PostgreSQL service side-effect tests and full `tests/integration` suite | Concurrency, worker lease takeover, stale-epoch fencing, idempotency, outbox exclusivity, retry, migration, and restart/recovery scenarios pass against PostgreSQL, not only an in-memory fake. |
| Representative end-to-end workflow | Governed vertical-slice tests plus the full repository suite | Demonstrate intent → identity/policy authorization → capability selection → Kernel/provider execution → validation → persisted evidence and terminal state. Denied permission and provider/authentication failure cases must remain denied and must not silently fall back. |
| Deployment, observability and rollback | Contract-document checks in CI; manual staging evidence below | Automated documentation checks do not count as a deployment. Staging deploy, telemetry inspection, recovery drill, and rollback must be run and recorded separately. |

## Security response protocol

1. Review every Gitleaks finding, including findings in historical commits and example/config files.
2. Treat a detector hit as an unverified finding, not proof that a credential is live.
3. Treat credential-shaped values in tracked examples as potentially exposed until verified by the issuing provider or credential owner. If a real credential was committed, revoke/rotate it, inspect available access logs, remove exposed active values/history as appropriate, and record remediation without copying the secret into this document or a PR comment.
4. Keep narrowly scoped, documented false-positive allowlists only after review. Never globally disable a detector or allowlist a broad path merely to turn CI green.
5. Verify GitHub secret scanning and push protection in repository settings; repository code cannot prove these settings are enabled.
6. Confirm the `main` ruleset requires the readiness gate and other critical CI checks. A successful workflow that is not required by branch rules is advisory, not an enforcement gate.

## Required staging evidence (manual, environment-specific)

Attach sanitized links or artifacts for the exact target release commit:

- [ ] Build provenance: source commit, immutable artifact digest, lockfile identifier, and SBOM.
- [ ] Migration rehearsal: clean database upgrade, repeatability/compatibility check, backup/restore result, and documented rollback constraints.
- [ ] Deploy to a non-production environment using the release procedure and least-privilege runtime credentials.
- [ ] Readiness/liveness and dependency health pass after deploy.
- [ ] One representative workflow completes and produces correlated execution/evidence IDs.
- [ ] Authorization matrix: allowed request succeeds; missing identity, denied permission, cross-tenant access, and revoked/expired capability fail closed.
- [ ] Provider failure injection: missing credentials, authentication rejection, timeout, rate limit, and malformed response are recorded; forbidden fallback does not occur.
- [ ] Durable recovery: run competing workers, expire a lease, attempt stale-epoch writes, replay duplicate requests, restart a worker mid-step, and inspect partially completed side effects.
- [ ] External side-effect semantics: record whether the downstream provider supports idempotency keys and reconciliation. A transactional outbox alone cannot make a third-party side effect exactly-once across a crash between the external action and local acknowledgement.
- [ ] Observability: inspect traces, metrics, and structured logs for a run; verify correlation and ensure no secret values or unnecessary personal data are emitted.
- [ ] Rollback to a previously verified immutable artifact; re-run health and workflow checks. State explicitly whether the database schema is backward compatible.
- [ ] Record operator, timestamp, environment, commit, artifact digest, migration version, results, exceptions, and evidence URLs.

Do not run destructive failure injection or rollback against production without a tested recovery plan and explicit authorization. Use disposable staging data and non-production credentials.

## Current evidence status

This file records the acceptance contract, not completed staging runs. Until the workflow has run successfully on the candidate commit and the staging evidence above is attached, the status remains **NOT PRODUCTION VERIFIED**. A green CI run alone cannot establish live deployment, credential rotation, repository settings, or rollback success. Skipped or unavailable required checks are blockers, not passes.

## Release decision

Promote only when all automated jobs are green, all secret findings are resolved or narrowly explained with evidence, the representative end-to-end path passes, and staging deployment/recovery/rollback evidence has been reviewed. The full-history secret-scan failure documented in the baseline must not be silently ignored.
