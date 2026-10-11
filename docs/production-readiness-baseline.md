# OIS Production Readiness Baseline

**Snapshot date:** 2026-10-10  
**Repository:** `niceoneobsidian/niceone-obsidian`  
**Baseline branch:** `main`  
**Baseline commit:** `2d3f3bace0c79eea43909228f395872379585a73`  
**Commit subject:** `feat(kernel): durable Ollama live vertical slice (#224)`

This is a time-bounded baseline snapshot, not a production-readiness attestation. Re-capture it whenever `main` moves and before a release decision. The checks below are historical evidence associated with the baseline commit, not evidence that the current pull-request head has passed.

## Baseline evidence

| Check | Observed result | Evidence |
|---|---|---|
| Full unit/default test workflow | **PASS** — 71 passed, 10 skipped | [Run Tests](https://github.com/niceoneobsidian/niceone-obsidian/actions/runs/37876986347) |
| PostgreSQL integration workflow | **PASS** — 41 passed, 10 skipped | [Integration Tests](https://github.com/niceoneobsidian/niceone-obsidian/actions/runs/37876986431) |
| Mypy | **PASS** — no issues in 360 source files | [Mypy Type Check](https://github.com/niceoneobsidian/niceone-obsidian/actions/runs/37876986434) |
| Ruff | **PASS** | [Ruff](https://github.com/niceoneobsidian/niceone-obsidian/actions/runs/37876986372) |
| Bandit | **PASS** | [Bandit](https://github.com/niceoneobsidian/niceone-obsidian/actions/runs/37876986436) |
| Dependency vulnerability scan | **PASS** | [OSV-Scanner](https://github.com/niceoneobsidian/niceone-obsidian/actions/runs/37876986981) |
| Kernel conformance | **PASS** | [Kernel Conformance](https://github.com/niceoneobsidian/niceone-obsidian/actions/runs/37944660751) |
| Full-history secret detection | **FAIL** — 7 findings | [Latest Gitleaks run](https://github.com/niceoneobsidian/niceone-obsidian/actions/runs/38044595061) |

The skipped tests are recorded as skipped, not passed. Review the skip reasons and confirm each is appropriate for the release target; any required sandbox, live-provider, or staging test remains a separate evidence obligation.

## Known release blocker: historical secret detections

The full-history Gitleaks scan reports seven detections in `.env.example` at historical commit `646df0859e6a8d6b8bac04098b68a09ce1800393` (reported lines 87, 116, 131, 132, 225, 240, and 257). Detectors identify GitHub, Google, Meta, and API-key-like patterns. Secret values are intentionally not copied into this report.

These findings are **unverified**, not automatically classified as either real credentials or false positives. Because the values are long and credential-shaped, do not suppress the findings or merge on the assumption that they are examples. The credential owners must verify the values against the issuing providers. If any value was ever valid, revoke or rotate it, inspect access logs where available, and record sanitized remediation evidence. Only then may a narrow, reviewed false-positive allowlist be considered for confirmed non-secret placeholders.

This finding predates PR #229 and is therefore a baseline failure, not a regression introduced by the readiness-gate branch. The readiness gate must continue to fail until the finding is resolved or formally dispositioned with evidence.

## Branch protection evidence

The branch API response for `main` reported `protected: true`, while the returned protection details reported enforcement off and no required status-check contexts. A separate read of the branch-protection endpoint returned HTTP 403, so the complete administrator-level configuration could not be independently verified from this session.

**Required follow-up:** a repository administrator must inspect Settings → Rules → Rulesets / Branch protection and confirm that PR review, required CI checks, stale-review dismissal or equivalent update policy, and no-force-push/no-branch-deletion protections are actually enforced. A workflow file or this document cannot enforce server-side GitHub settings.

## Migration and durability inventory

At the baseline commit, `migrations/` contains 16 numbered SQL files, `001` through `016`. The baseline PostgreSQL integration workflow passed its 41 tests, including migration recording/checksum, worker fencing, idempotency, outbox exclusivity, failed-effect retry, and stale-processing recovery scenarios.

Sequential filenames alone do not prove that every future migration is valid. PR #229 adds explicit filename, numeric-contiguity, and non-empty-file checks and expands its dedicated readiness job to run the full `tests/integration` suite as well as the durable side-effect tests against a PostgreSQL service. These new PR-head checks must pass before the gate can be accepted.

## Open change set at capture time

The repository search returned these open pull requests on 2026-10-10:

- [#229 — Production readiness evidence gate](https://github.com/niceoneobsidian/niceone-obsidian/pull/229)
- [#228 — Opt-in multi-provider LLM gateway](https://github.com/niceoneobsidian/niceone-obsidian/pull/228)
- [#227 — Production migration runner and blocked-workload gate](https://github.com/niceoneobsidian/niceone-obsidian/pull/227)
- [#218 — Secret management plane](https://github.com/niceoneobsidian/niceone-obsidian/pull/218)
- [#217 — Developer credential control plane](https://github.com/niceoneobsidian/niceone-obsidian/pull/217)

Do not combine their results into one baseline without testing the exact candidate merge commit. Each PR may change source, dependencies, migrations, workflows, or the evidence contract.

## Baseline decision

**Status: NOT RELEASE-READY.** The unit, PostgreSQL integration, type-check, lint, Bandit, and dependency-scan evidence is encouraging, but the historical secret-scan failure and unverified branch enforcement are release blockers. Staging deployment, fault injection, runtime observability, provider credential verification/rotation, and rollback evidence have not been established by these CI results.
