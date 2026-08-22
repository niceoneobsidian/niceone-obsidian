# OIS Free-Tier Governance

GitHub server-side rulesets are unavailable for this private repository under the current plan. OIS therefore treats the limitation explicitly rather than claiming that `main` is protected.

## Mandatory engineering policy

1. Develop on a dedicated branch.
2. Open a pull request for changes intended for `main`.
3. Require the governance/CI workflow to pass before treating a change as merge-ready.
4. Run the deterministic governance gate locally before publishing changes.
5. Never classify server-side branch protection as verified without a live direct-push rejection test.
6. Preserve governance failures as audit evidence without leaving test markers on `main`.

## Evidence boundary

This gate is an executable local/CI control. It is not equivalent to GitHub server-side branch protection. Audit and readiness reports must retain that distinction.

## Upgrade path

If the repository later moves to a plan supporting enforceable rulesets, enable protection for `main` and repeat both boundary tests: direct push must be rejected, while a PR with required CI must be mergeable. Only then may server-side protection be marked verified.
