# OIS Repository Governance

## Verified GitHub ruleset boundary

The repository has an active GitHub ruleset named `main`. The live ruleset currently requires the `Run Tests` and `License Compliance Scan` status checks for governed merges, disallows non-fast-forward updates, and defines pull-request rules.

A live direct-push probe to `main` was executed on 2026-09-20. The push was **accepted** by GitHub, proving that the current ruleset does **not** enforce a direct-push rejection boundary for this repository.

The probe artifact was immediately removed from `main`. Therefore:

- **Ruleset exists:** VERIFIED
- **Ruleset active:** VERIFIED
- **Required merge checks:** VERIFIED from the live ruleset definition
- **Direct push rejection:** NOT ENFORCED / FAILED LIVE TEST
- **Main branch fully PR-only:** NOT VERIFIED

Do not describe `main` as PR-only or branch-protected until a server-side configuration change causes a fresh direct-push test to be rejected.

## Mandatory engineering policy

1. Develop on a dedicated branch.
2. Open a pull request for changes intended for `main`.
3. Require the configured CI/status checks to pass before treating a change as merge-ready.
4. Run the deterministic governance gate locally before publishing changes.
5. Treat server-side enforcement as verified only from live GitHub behavior.
6. Preserve governance failures as audit evidence without leaving test markers on `main`.

## Runner policy

The canonical default for general repository CI is **GitHub-hosted `ubuntu-latest`**.

The repository must not route ordinary CI to `self-hosted`, macOS, or ARM64 runners solely to avoid hosted-runner minute consumption. Self-hosted execution is permitted only for a separately justified workload with an explicit trust boundary, required labels, and documented security/maintenance ownership.

No workflow should silently fall back from a trusted runner class to an untrusted runner class.

PR #131 therefore remains unmerged until the runner policy is reflected by the workflows and independently verified by CI.

## Evidence boundary

Repository governance documentation must distinguish policy declarations from observed GitHub enforcement. A green local governance test does not prove server-side branch protection.

## Upgrade path

If server-side enforcement is changed so that direct pushes to `main` are rejected, repeat both boundary tests:

1. direct push is rejected;
2. a compliant PR with the required checks is mergeable.

Only then may the direct-push protection boundary be marked verified.
